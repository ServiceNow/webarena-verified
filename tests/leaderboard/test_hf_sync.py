import json
from pathlib import Path

import pytest

from dev.leaderboard import hf_sync
from dev.leaderboard.hf_validator import SubmissionHFValidationError
from dev.leaderboard.submission_control_plane import read_pending_submission, read_processed_submission
from webarena_verified.types.leaderboard import SubmissionRecord


def _write_processed(root: Path, submission_id: str) -> None:
    record = SubmissionRecord.model_validate(
        {
            "submission_id": submission_id,
            "status": "accepted",
            "hf_repo": "org/repo",
            "hf_pr_id": 42,
            "hf_pr_url": "https://huggingface.co/datasets/org/repo/discussions/42",
            "created_at_utc": "2026-02-07T12:00:00Z",
            "updated_at_utc": "2026-02-07T12:10:00Z",
            "processed_at_utc": "2026-02-07T12:10:00Z",
            "result_reason": None,
        }
    )
    path = root / "processed" / f"{submission_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


def test_run_hf_sync_accepts_and_processes_submission(tmp_path: Path, monkeypatch):
    root = tmp_path / "submissions"

    monkeypatch.setattr(hf_sync, "list_open_hf_discussions", lambda hf_repo, hf_token=None: [{"num": 12}, {"num": 13}])
    monkeypatch.setattr(
        hf_sync,
        "_candidate_from_discussion",
        lambda hf_repo, discussion, hf_token=None: (
            hf_sync.HFCandidate(
                hf_repo=hf_repo,
                hf_pr_id=discussion["num"],
                hf_pr_url=f"https://huggingface.co/datasets/{hf_repo}/discussions/{discussion['num']}",
                submission_id="sub-1",
            )
            if discussion["num"] == 12
            else None
        ),
    )
    monkeypatch.setattr(hf_sync, "validate_hf_submission_record", lambda record, token=None: None)
    monkeypatch.setattr(hf_sync, "merge_hf_pr", lambda hf_repo, hf_pr_id, hf_token: None)

    result = hf_sync.run_hf_sync("org/repo", submissions_root=root, hf_token="token")

    processed = read_processed_submission(root, "sub-1")
    assert processed.status.value == "accepted"
    assert result.total_candidates == 2
    assert result.accepted == 1
    assert result.skipped == 1


def test_run_hf_sync_rejects_when_validation_fails(tmp_path: Path, monkeypatch):
    root = tmp_path / "submissions"

    monkeypatch.setattr(hf_sync, "list_open_hf_discussions", lambda hf_repo, hf_token=None: [{"num": 12}])
    monkeypatch.setattr(
        hf_sync,
        "_candidate_from_discussion",
        lambda hf_repo, discussion, hf_token=None: hf_sync.HFCandidate(
            hf_repo=hf_repo,
            hf_pr_id=discussion["num"],
            hf_pr_url=f"https://huggingface.co/datasets/{hf_repo}/discussions/{discussion['num']}",
            submission_id="sub-2",
        ),
    )

    def fail_validation(record, token=None):
        raise SubmissionHFValidationError("bad payload")

    monkeypatch.setattr(hf_sync, "validate_hf_submission_record", fail_validation)

    result = hf_sync.run_hf_sync("org/repo", submissions_root=root, hf_token="token")

    processed = read_processed_submission(root, "sub-2")
    assert processed.status.value == "rejected"
    assert "hf-validation-failed" in (processed.result_reason or "")
    assert result.rejected == 1


def test_run_hf_sync_keeps_pending_for_merge_retry(tmp_path: Path, monkeypatch):
    root = tmp_path / "submissions"

    monkeypatch.setattr(hf_sync, "list_open_hf_discussions", lambda hf_repo, hf_token=None: [{"num": 12}])
    monkeypatch.setattr(
        hf_sync,
        "_candidate_from_discussion",
        lambda hf_repo, discussion, hf_token=None: hf_sync.HFCandidate(
            hf_repo=hf_repo,
            hf_pr_id=discussion["num"],
            hf_pr_url=f"https://huggingface.co/datasets/{hf_repo}/discussions/{discussion['num']}",
            submission_id="sub-3",
        ),
    )
    monkeypatch.setattr(hf_sync, "validate_hf_submission_record", lambda record, token=None: None)

    def fail_merge(hf_repo: str, hf_pr_id: int, hf_token: str):
        raise hf_sync.HFSyncError("merge failed")

    monkeypatch.setattr(hf_sync, "merge_hf_pr", fail_merge)

    result = hf_sync.run_hf_sync("org/repo", submissions_root=root, hf_token="token")

    pending = read_pending_submission(root, "sub-3")
    assert pending.status.value == "pending"
    with pytest.raises(FileNotFoundError):
        read_processed_submission(root, "sub-3")
    assert result.pending_retry == 1


def test_run_hf_sync_skips_already_processed_submission(tmp_path: Path, monkeypatch):
    root = tmp_path / "submissions"
    _write_processed(root, "sub-4")

    monkeypatch.setattr(hf_sync, "list_open_hf_discussions", lambda hf_repo, hf_token=None: [{"num": 12}])
    monkeypatch.setattr(
        hf_sync,
        "_candidate_from_discussion",
        lambda hf_repo, discussion, hf_token=None: hf_sync.HFCandidate(
            hf_repo=hf_repo,
            hf_pr_id=discussion["num"],
            hf_pr_url=f"https://huggingface.co/datasets/{hf_repo}/discussions/{discussion['num']}",
            submission_id="sub-4",
        ),
    )

    result = hf_sync.run_hf_sync("org/repo", submissions_root=root, hf_token="token")

    assert result.skipped == 1
    processed = read_processed_submission(root, "sub-4")
    assert json.loads((root / "processed" / "sub-4.json").read_text())["submission_id"] == processed.submission_id
