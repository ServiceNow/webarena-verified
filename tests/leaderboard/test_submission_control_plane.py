import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dev.leaderboard.submission_control_plane import (
    DuplicateSubmissionIDError,
    InvalidSubmissionTransitionError,
    PathStatusMismatchError,
    process_pending_submission,
    read_pending_submission,
    read_processed_submission,
    validate_submission_control_plane,
    write_pending_submission,
)
from webarena_verified.types.leaderboard import SubmissionRecord, SubmissionStatus


def _pending_record_payload(submission_id: str = "sub-123") -> dict:
    return {
        "submission_id": submission_id,
        "status": "pending",
        "hf_repo": "org/repo",
        "hf_pr_id": 42,
        "hf_pr_url": "https://huggingface.co/datasets/org/repo/discussions/42",
        "created_at_utc": "2026-02-07T12:00:00Z",
        "updated_at_utc": "2026-02-07T12:05:00Z",
        "processed_at_utc": None,
        "result_reason": None,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SubmissionRecord.model_validate(payload).model_dump_json(indent=2) + "\n", encoding="utf-8")


def test_pending_path_status_mismatch_fails(tmp_path: Path):
    root = tmp_path / "submissions"
    bad_payload = _pending_record_payload()
    bad_payload["status"] = "accepted"
    bad_payload["processed_at_utc"] = "2026-02-07T13:00:00Z"

    path = root / "pending" / "sub-123.json"
    _write_json(path, bad_payload)

    with pytest.raises(PathStatusMismatchError, match="path/status mismatch"):
        read_pending_submission(root, "sub-123")


def test_invalid_transition_rejects_pending_terminal_status(tmp_path: Path):
    root = tmp_path / "submissions"
    pending_path = root / "pending" / "sub-123.json"
    _write_json(pending_path, _pending_record_payload())

    with pytest.raises(InvalidSubmissionTransitionError, match="invalid terminal status"):
        process_pending_submission(
            submissions_root=root,
            submission_id="sub-123",
            terminal_status=SubmissionStatus.PENDING,
            processed_at_utc="2026-02-07T13:00:00Z",
        )


def test_rejected_transition_requires_result_reason(tmp_path: Path):
    root = tmp_path / "submissions"
    pending_path = root / "pending" / "sub-123.json"
    _write_json(pending_path, _pending_record_payload())

    with pytest.raises(ValidationError, match="result_reason is required"):
        process_pending_submission(
            submissions_root=root,
            submission_id="sub-123",
            terminal_status=SubmissionStatus.REJECTED,
            processed_at_utc="2026-02-07T13:00:00Z",
            result_reason=None,
        )


def test_processed_record_requires_processed_at_utc(tmp_path: Path):
    root = tmp_path / "submissions"
    invalid_processed = _pending_record_payload()
    invalid_processed["status"] = "accepted"
    invalid_processed["processed_at_utc"] = None

    path = root / "processed" / "sub-123.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(invalid_processed, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="processed_at_utc is required"):
        read_processed_submission(root, "sub-123")


def test_duplicate_processed_submission_id_blocks_transition(tmp_path: Path):
    root = tmp_path / "submissions"
    pending_path = root / "pending" / "sub-123.json"
    _write_json(pending_path, _pending_record_payload())

    processed_payload = _pending_record_payload()
    processed_payload["status"] = "accepted"
    processed_payload["processed_at_utc"] = "2026-02-07T13:00:00Z"
    _write_json(root / "processed" / "sub-123.json", processed_payload)

    with pytest.raises(DuplicateSubmissionIDError, match="already exists in processed"):
        process_pending_submission(
            submissions_root=root,
            submission_id="sub-123",
            terminal_status=SubmissionStatus.ACCEPTED,
            processed_at_utc="2026-02-07T13:30:00Z",
        )


def test_write_pending_rejects_existing_processed_duplicate(tmp_path: Path):
    root = tmp_path / "submissions"
    processed_payload = _pending_record_payload()
    processed_payload["status"] = "accepted"
    processed_payload["processed_at_utc"] = "2026-02-07T13:00:00Z"
    _write_json(root / "processed" / "sub-123.json", processed_payload)

    record = SubmissionRecord.model_validate(_pending_record_payload())
    with pytest.raises(DuplicateSubmissionIDError, match="already exists in processed"):
        write_pending_submission(root, record)


def test_validate_submission_control_plane_checks_all_json_files(tmp_path: Path):
    root = tmp_path / "submissions"
    _write_json(root / "pending" / "sub-1.json", _pending_record_payload("sub-1"))

    processed_payload = _pending_record_payload("sub-2")
    processed_payload["status"] = "accepted"
    processed_payload["processed_at_utc"] = "2026-02-07T13:00:00Z"
    _write_json(root / "processed" / "sub-2.json", processed_payload)

    checked = validate_submission_control_plane(root)
    assert [path.name for path in checked] == ["sub-1.json", "sub-2.json"]


def test_validate_submission_control_plane_rejects_duplicate_ids_across_dirs(tmp_path: Path):
    root = tmp_path / "submissions"
    _write_json(root / "pending" / "sub-1.json", _pending_record_payload("sub-1"))

    processed_payload = _pending_record_payload("sub-1")
    processed_payload["status"] = "accepted"
    processed_payload["processed_at_utc"] = "2026-02-07T13:00:00Z"
    _write_json(root / "processed" / "sub-1.json", processed_payload)

    with pytest.raises(DuplicateSubmissionIDError, match="duplicate submission_id"):
        validate_submission_control_plane(root)
