import json
from pathlib import Path

import pytest

from leaderboard.scripts import hf_ingest
from webarena_verified.submission.models import EvaluationSummaryPayload, SubmissionMode


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _dispatch_event(*, head_sha: str = "sha-1") -> dict:
    return {
        "client_payload": {
            "event_id": "evt-1",
            "event_scope": "schedule",
            "event_action": "sync_submissions",
            "hf_repo": "org/dataset",
            "hf_pr_number": 42,
            "hf_head_sha": head_sha,
            "hf_pr_url": "https://huggingface.co/datasets/org/dataset/discussions/42",
        }
    }


def _summary() -> EvaluationSummaryPayload:
    return EvaluationSummaryPayload.model_validate(
        {
            "timestamp": "2026-03-08T10:00:00Z",
            "webarena_verified_version": "1.0.0",
            "webarena_verified_evaluator_checksum": "x",
            "webarena_verified_data_checksum": "y",
            "summary": {
                "overall": {
                    "total": 1,
                    "success_count": 1,
                    "failure_count": 0,
                    "error_count": 0,
                    "failed_or_error_count": 0,
                },
                "per_site": {},
            },
            "scores": {
                "overall": 1.0,
                "shopping": 1.0,
                "shopping_admin": 0.0,
                "gitlab": 0.0,
                "map": 0.0,
                "reddit": 0.0,
                "multisite": 0.0,
                "gitlab_reddit": 0.0,
            },
        }
    )


def _write_submission_tree(root: Path, *, submission_uid: str) -> None:
    submission_dir = root / "submissions" / submission_uid
    task_dir = submission_dir / "101"
    task_dir.mkdir(parents=True)
    (task_dir / "agent_response.json").write_text('{"ok":true}', encoding="utf-8")
    (task_dir / "network.har").write_text('{"log":{"entries":[]}}', encoding="utf-8")

    submission = {
        "submission_uid": submission_uid,
        "name": "TeamX-ModelY",
        "model": "gpt-4.1-mini",
        "reference": "https://example.com/paper",
        "contact_email": "team@example.com",
        "submitted_tasks": 1,
        "task_network_filename": "network.har",
    }
    _write_json(submission_dir / "submission.json", submission)

    files = []
    for rel in ["101/agent_response.json", "101/network.har", "submission.json"]:
        p = submission_dir / rel
        files.append(
            {
                "path": rel,
                "sha256": __import__("hashlib").sha256(p.read_bytes()).hexdigest(),
                "size_bytes": p.stat().st_size,
            }
        )
    manifest = {
        "schema_version": "1.0",
        "created_at_utc": "2026-03-08T10:00:00Z",
        "files": files,
    }
    _write_json(submission_dir / "manifest.json", manifest)

    digest = __import__("hashlib").sha256()
    for rel in ["101/agent_response.json", "101/network.har", "submission.json"]:
        p = submission_dir / rel
        digest.update(rel.encode("utf-8"))
        digest.update(b"\n")
        digest.update(p.read_bytes())
        digest.update(b"\n")

    internal = {
        "schema_version": "1.0",
        "submission_uid": submission_uid,
        "submission_mode": "both",
        "source_sha": None,
        "generated_at_utc": "2026-03-08T10:00:00Z",
        "manifest_sha256": __import__("hashlib").sha256((submission_dir / "manifest.json").read_bytes()).hexdigest(),
        "submission_package_checksum": digest.hexdigest(),
        "submission_package_checksum_algo": "sha256",
    }
    _write_json(submission_dir / "_internal.json", internal)


def test_hf_ingest_updates_leaderboard_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    submission_uid = "018f6f54-7e58-7f23-9d16-f4f8072b4f61"
    snapshot_root = tmp_path / "snapshot"
    _write_submission_tree(snapshot_root, submission_uid=submission_uid)

    event_path = tmp_path / "event.json"
    _write_json(event_path, _dispatch_event())

    monkeypatch.setattr(hf_ingest, "snapshot_download", lambda **_kwargs: str(snapshot_root))

    class FakeEvaluator:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def evaluate_submission(self, **_kwargs):
            return {
                SubmissionMode.FULL: _summary(),
                SubmissionMode.HARD: _summary(),
            }

    monkeypatch.setattr(hf_ingest, "SubmissionEvaluator", FakeEvaluator)

    result = hf_ingest.ingest_hf_submission(
        repo_root=tmp_path,
        event_path=event_path,
        hf_repo_expected="org/dataset",
        hf_token="hf-token",
        evaluator_version="v1",
    )

    assert result.submission_uid == submission_uid
    assert result.leaderboard_latest_path.endswith("leaderboard/latest.json")
    assert Path(result.full_artifact_path).name == "full.json"
    assert Path(result.hard_artifact_path).name == "hard.json"


def test_hf_ingest_rejects_repo_mismatch(tmp_path: Path) -> None:
    event_path = tmp_path / "event.json"
    _write_json(event_path, _dispatch_event())

    with pytest.raises(ValueError, match="does not match"):
        hf_ingest.ingest_hf_submission(
            repo_root=tmp_path,
            event_path=event_path,
            hf_repo_expected="different/repo",
            hf_token="hf-token",
            evaluator_version="v1",
        )


def test_hf_ingest_resolves_submission_uid_from_pr_diff_when_snapshot_has_multiple(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected_uid = "018f6f54-7e58-7f23-9d16-f4f8072b4f61"
    other_uid = "018f6f54-7e58-7f23-9d16-f4f8072b4f62"
    snapshot_root = tmp_path / "snapshot"
    _write_submission_tree(snapshot_root, submission_uid=selected_uid)
    _write_submission_tree(snapshot_root, submission_uid=other_uid)

    event_path = tmp_path / "event.json"
    _write_json(event_path, _dispatch_event())

    monkeypatch.setattr(hf_ingest, "snapshot_download", lambda **_kwargs: str(snapshot_root))

    class FakeDetails:
        diff = "\n".join(
            [
                f"diff --git a/submissions/{selected_uid}/submission.json b/submissions/{selected_uid}/submission.json",
                "index 1111111..2222222 100644",
            ]
        )

    class FakeHfApi:
        def __init__(self, token=None) -> None:
            del token

        def get_discussion_details(self, **_kwargs):
            return FakeDetails()

    class FakeEvaluator:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def evaluate_submission(self, **_kwargs):
            return {
                SubmissionMode.FULL: _summary(),
                SubmissionMode.HARD: _summary(),
            }

    monkeypatch.setattr(hf_ingest, "HfApi", FakeHfApi)
    monkeypatch.setattr(hf_ingest, "SubmissionEvaluator", FakeEvaluator)

    result = hf_ingest.ingest_hf_submission(
        repo_root=tmp_path,
        event_path=event_path,
        hf_repo_expected="org/dataset",
        hf_token="hf-token",
        evaluator_version="v1",
    )

    assert result.submission_uid == selected_uid
