import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from leaderboard.scripts import hf_reconcile


def _write_control_record(
    root: Path,
    *,
    submission_id: int,
    status: str,
    head_sha: str,
    pr_url: str | None = None,
) -> None:
    payload = {
        "submission_id": submission_id,
        "submission_uid": f"hf:org/dataset:pr-{submission_id}@{head_sha}",
        "hf_repo": "org/dataset",
        "hf_pr_number": submission_id,
        "hf_head_sha": head_sha,
        "hf_pr_url": pr_url,
        "status": status,
        "status_history": [],
        "processed_event_ids": [],
        "retry_count": 0,
    }
    target = root / "submission_control" / f"{submission_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")


def test_reconcile_processes_recent_refs_and_retryable_control_records(tmp_path: Path, monkeypatch) -> None:
    class FakeHfApi:
        def __init__(self, token=None) -> None:
            self.token = token

        def list_repo_refs(self, repo_id: str, repo_type: str):
            assert repo_id == "org/dataset"
            assert repo_type == "dataset"
            return SimpleNamespace(
                pull_requests=[
                    SimpleNamespace(ref="refs/pr/1", target_commit="sha-1"),
                    SimpleNamespace(ref="refs/pr/5", target_commit="sha-5"),
                ]
            )

    ingest_calls: list[dict] = []

    def fake_ingest(**kwargs):
        payload = json.loads(Path(kwargs["event_path"]).read_text(encoding="utf-8"))
        ingest_calls.append(payload["client_payload"])
        return SimpleNamespace()

    monkeypatch.setattr(hf_reconcile, "HfApi", FakeHfApi)
    monkeypatch.setattr(hf_reconcile, "ingest_hf_submission", fake_ingest)

    _write_control_record(
        tmp_path,
        submission_id=42,
        status="failed_retryable",
        head_sha="sha-42",
        pr_url="https://hf.example/discussions/42",
    )

    reconciled = hf_reconcile.reconcile_hf_submissions(
        repo_root=tmp_path,
        hf_repo="org/dataset",
        hf_token="hf-token",
        evaluator_version="v1",
        max_recent_refs=1,
    )

    assert reconciled == [5, 42]
    assert [call["hf_pr_number"] for call in ingest_calls] == [5, 42]
    assert ingest_calls[0]["hf_pr_url"] == "https://huggingface.co/datasets/org/dataset/discussions/5"
    assert ingest_calls[1]["hf_pr_url"] == "https://hf.example/discussions/42"


def test_reconcile_uses_control_sha_when_hf_ref_is_missing(tmp_path: Path, monkeypatch) -> None:
    class FakeHfApi:
        def __init__(self, token=None) -> None:
            self.token = token

        def list_repo_refs(self, repo_id: str, repo_type: str):
            assert repo_id == "org/dataset"
            assert repo_type == "dataset"
            return SimpleNamespace(pull_requests=[])

    captured_payloads: list[dict] = []

    def fake_ingest(**kwargs):
        payload = json.loads(Path(kwargs["event_path"]).read_text(encoding="utf-8"))
        captured_payloads.append(payload["client_payload"])
        return SimpleNamespace()

    monkeypatch.setattr(hf_reconcile, "HfApi", FakeHfApi)
    monkeypatch.setattr(hf_reconcile, "ingest_hf_submission", fake_ingest)

    _write_control_record(
        tmp_path,
        submission_id=7,
        status="accepted_pending_publish",
        head_sha="sha-control",
    )

    reconciled = hf_reconcile.reconcile_hf_submissions(
        repo_root=tmp_path,
        hf_repo="org/dataset",
        hf_token="hf-token",
        evaluator_version="v1",
    )

    assert reconciled == [7]
    assert captured_payloads[0]["hf_head_sha"] == "sha-control"
    assert captured_payloads[0]["event_id"] == "reconcile-7-sha-control"


def test_reconcile_fails_fast_on_missing_required_inputs(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError, match=r"Missing required reconcile input\(s\): hf_repo, hf_token, evaluator_version"
    ):
        hf_reconcile.reconcile_hf_submissions(
            repo_root=tmp_path,
            hf_repo="",
            hf_token="",
            evaluator_version="",
        )


def test_reconcile_fails_fast_on_invalid_max_recent_refs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_recent_refs must be >= 1"):
        hf_reconcile.reconcile_hf_submissions(
            repo_root=tmp_path,
            hf_repo="org/dataset",
            hf_token="hf-token",
            evaluator_version="v1",
            max_recent_refs=0,
        )
