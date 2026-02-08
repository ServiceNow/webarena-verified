from pathlib import Path

import pytest

import dev.leaderboard.hf_submission_validator as hf_validator
from dev.leaderboard.constants import (
    HF_SUBMISSION_ARCHIVE_FILE,
    HF_SUBMISSION_SHA256_FILE,
    TASK_MISSING_SENTINEL_FILE,
)
from dev.leaderboard.models import SubmissionRecord


def _record() -> SubmissionRecord:
    return SubmissionRecord.model_validate(
        {
            "submission_id": "sub-123",
            "status": "pending",
            "hf_repo": "org/repo",
            "hf_pr_id": 42,
            "hf_pr_url": "https://huggingface.co/datasets/org/repo/discussions/42",
            "created_at_utc": "2026-02-07T12:00:00Z",
            "updated_at_utc": "2026-02-07T12:05:00Z",
            "processed_at_utc": None,
            "result_reason": None,
        }
    )


def test_validate_hf_discussion_open_rejects_closed_status(monkeypatch):
    monkeypatch.setattr(hf_validator, "http_get_json", lambda url, token=None: {"status": "closed"})

    with pytest.raises(hf_validator.SubmissionHFValidationError, match="must be open"):
        hf_validator.validate_hf_discussion_open("org/repo", 42)


def test_validate_task_dir_rejects_missing_plus_files(tmp_path: Path):
    task_dir = tmp_path / "1"
    task_dir.mkdir()
    (task_dir / TASK_MISSING_SENTINEL_FILE).write_text("")
    (task_dir / "network.har").write_text("{}")

    with pytest.raises(hf_validator.SubmissionHFValidationError, match="cannot coexist"):
        hf_validator._validate_task_dir(task_dir)


def test_validate_hf_payload_rejects_checksum_mismatch(monkeypatch):
    record = _record()

    def fake_get_bytes(url: str) -> bytes:
        if url.endswith(f"{HF_SUBMISSION_ARCHIVE_FILE}?download=true"):
            return b"payload-bytes"
        if url.endswith(f"{HF_SUBMISSION_SHA256_FILE}?download=true"):
            return ("0" * 64).encode("utf-8")
        return b"{}"

    monkeypatch.setattr(hf_validator, "_http_get_bytes", fake_get_bytes)

    with pytest.raises(hf_validator.SubmissionHFValidationError, match="checksum mismatch"):
        hf_validator.validate_hf_payload(record)
