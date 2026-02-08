import io
import tarfile
from pathlib import Path

import pytest

import dev.leaderboard.hf_submission_validator as hf_validator
from dev.leaderboard.constants import TASK_MISSING_SENTINEL_FILE
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


def _valid_payload_archive_bytes() -> bytes:
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as tar:
        dir_info = tarfile.TarInfo(name="1")
        dir_info.type = tarfile.DIRTYPE
        tar.addfile(dir_info)
        missing_info = tarfile.TarInfo(name=f"1/{TASK_MISSING_SENTINEL_FILE}")
        missing_info.size = 0
        tar.addfile(missing_info, io.BytesIO(b""))
    return data.getvalue()


def test_validate_hf_payload_rejects_metadata_submission_id_mismatch(monkeypatch):
    record = _record()

    def fake_download_required_payload_files(record: SubmissionRecord, artifacts, token: str | None = None) -> dict[str, bytes]:
        del record, token
        return {
            artifacts.archive_file: _valid_payload_archive_bytes(),
            artifacts.metadata_file: b'{"submission_id":"different-submission","name":"team/model","leaderboard":"hard","reference":"https://example.com","created_at_utc":"2026-02-07T12:00:00Z"}',
        }

    monkeypatch.setattr(hf_validator, "_download_required_payload_files", fake_download_required_payload_files)
    monkeypatch.setattr(hf_validator, "_validate_submission_root_inputs_exact", lambda *args, **kwargs: None)

    with pytest.raises(hf_validator.SubmissionHFValidationError, match="submission_id does not match"):
        hf_validator.validate_hf_payload(record)
