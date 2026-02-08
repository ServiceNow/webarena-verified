"""Helpers for submission control-plane storage and processing.

This module owns the file-level invariants for:
- ``leaderboard/data/submissions/pending/<id>.json``
- ``leaderboard/data/submissions/processed/<id>.json``
"""

from __future__ import annotations

import json
from pathlib import Path

from dev.utils.file_lock import guarded_file_lock, guarded_file_locks
from webarena_verified.types.leaderboard import SubmissionRecord, SubmissionStatus

DEFAULT_SUBMISSIONS_ROOT = Path("leaderboard/data/submissions")
_PENDING_DIR = "pending"
_PROCESSED_DIR = "processed"


class SubmissionControlPlaneError(ValueError):
    """Base error for control-plane invariants."""


class PathStatusMismatchError(SubmissionControlPlaneError):
    """Raised when a file path and record status disagree."""


class InvalidSubmissionTransitionError(SubmissionControlPlaneError):
    """Raised when a requested status transition is not allowed."""


class DuplicateSubmissionIDError(SubmissionControlPlaneError):
    """Raised when a processed submission id already exists."""


def pending_submission_path(submissions_root: Path, submission_id: str) -> Path:
    """Build the pending file path for a submission id.

    Example:
        ``pending_submission_path(Path("leaderboard/data/submissions"), "sub-1")``
        returns ``leaderboard/data/submissions/pending/sub-1.json``.
    """
    return submissions_root / _PENDING_DIR / f"{submission_id}.json"


def processed_submission_path(submissions_root: Path, submission_id: str) -> Path:
    """Build the processed file path for a submission id.

    Example:
        ``processed_submission_path(Path("leaderboard/data/submissions"), "sub-1")``
        returns ``leaderboard/data/submissions/processed/sub-1.json``.
    """
    return submissions_root / _PROCESSED_DIR / f"{submission_id}.json"


def _expected_statuses_for_path(path: Path) -> set[SubmissionStatus]:
    """Return allowed statuses for a control-plane file path.

    Example:
        ``pending/sub-1.json`` -> ``{SubmissionStatus.PENDING}``
        ``processed/sub-1.json`` -> ``{SubmissionStatus.ACCEPTED, SubmissionStatus.REJECTED}``
    """
    parent = path.parent.name
    if parent == _PENDING_DIR:
        return {SubmissionStatus.PENDING}
    if parent == _PROCESSED_DIR:
        return {SubmissionStatus.ACCEPTED, SubmissionStatus.REJECTED}
    msg = f"unsupported submission record path: {path}"
    raise SubmissionControlPlaneError(msg)


def _enforce_path_invariants(path: Path, record: SubmissionRecord) -> None:
    """Enforce file-name and path/status invariants for one record.

    Example:
        A file at ``.../pending/sub-1.json`` must contain:
        - ``submission_id == "sub-1"``
        - ``status == "pending"``
    """
    if path.stem != record.submission_id:
        msg = f"file name '{path.name}' does not match submission_id '{record.submission_id}'"
        raise SubmissionControlPlaneError(msg)

    expected = _expected_statuses_for_path(path)
    if record.status not in expected:
        expected_values = sorted(status.value for status in expected)
        msg = f"path/status mismatch for {path}: expected {expected_values}, got '{record.status.value}'"
        raise PathStatusMismatchError(msg)


def load_submission_record(path: Path) -> SubmissionRecord:
    """Read and validate a submission record from disk.

    Validation includes:
    - JSON -> ``SubmissionRecord`` schema validation
    - path/file-name and status invariant checks
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    record = SubmissionRecord.model_validate(payload)
    _enforce_path_invariants(path, record)
    return record


def write_submission_record(path: Path, record: SubmissionRecord) -> None:
    """Write one submission record using an exclusive per-file lock.

    Example:
        ``write_submission_record(Path(".../pending/sub-1.json"), record)``
        performs invariant checks, acquires ``.../pending/sub-1.json.lock``,
        and writes a normalized JSON document.
    """
    with guarded_file_lock(path):
        _enforce_path_invariants(path, record)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


def read_pending_submission(submissions_root: Path, submission_id: str) -> SubmissionRecord:
    """Load a pending submission record by id.

    Raises:
        FileNotFoundError: If ``pending/<id>.json`` does not exist.
    """
    path = pending_submission_path(submissions_root, submission_id)
    if not path.exists():
        msg = f"pending submission record not found: {path}"
        raise FileNotFoundError(msg)
    return load_submission_record(path)


def read_processed_submission(submissions_root: Path, submission_id: str) -> SubmissionRecord:
    """Load a processed submission record by id.

    Raises:
        FileNotFoundError: If ``processed/<id>.json`` does not exist.
    """
    path = processed_submission_path(submissions_root, submission_id)
    if not path.exists():
        msg = f"processed submission record not found: {path}"
        raise FileNotFoundError(msg)
    return load_submission_record(path)


def write_pending_submission(submissions_root: Path, record: SubmissionRecord) -> Path:
    """Write a pending record while guarding against processed duplicates.

    Uses a multi-file lock over pending+processed paths to avoid races between
    duplicate checks and writes.
    """
    processed_path = processed_submission_path(submissions_root, record.submission_id)
    pending_path = pending_submission_path(submissions_root, record.submission_id)
    with guarded_file_locks([pending_path, processed_path]):
        if processed_path.exists():
            msg = f"submission_id '{record.submission_id}' already exists in processed records"
            raise DuplicateSubmissionIDError(msg)
        _enforce_path_invariants(pending_path, record)
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        pending_path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return pending_path


def process_pending_submission(
    submissions_root: Path,
    submission_id: str,
    terminal_status: SubmissionStatus,
    processed_at_utc: str,
    result_reason: str | None = None,
) -> SubmissionRecord:
    """Process a pending submission to accepted/rejected and move the file.

    Example transformation:
        Input:
            ``pending/sub-1.json`` with ``status="pending"`` and ``processed_at_utc=null``
        Output:
            ``processed/sub-1.json`` with terminal status and
            ``processed_at_utc=<timestamp>``
        Side effect:
            ``pending/sub-1.json`` is deleted after successful write.
    """
    if terminal_status not in {SubmissionStatus.ACCEPTED, SubmissionStatus.REJECTED}:
        msg = f"invalid terminal status '{terminal_status.value}'"
        raise InvalidSubmissionTransitionError(msg)

    pending_path = pending_submission_path(submissions_root, submission_id)
    processed_path = processed_submission_path(submissions_root, submission_id)
    with guarded_file_locks([pending_path, processed_path]):
        if processed_path.exists():
            msg = f"submission_id '{submission_id}' already exists in processed records"
            raise DuplicateSubmissionIDError(msg)

        pending_record = load_submission_record(pending_path)
        if pending_record.status != SubmissionStatus.PENDING:
            msg = (
                f"invalid transition for submission_id '{submission_id}': "
                f"{pending_record.status.value} -> {terminal_status.value}"
            )
            raise InvalidSubmissionTransitionError(msg)

        processed_record = SubmissionRecord(
            submission_id=pending_record.submission_id,
            status=terminal_status,
            hf_repo=pending_record.hf_repo,
            hf_pr_id=pending_record.hf_pr_id,
            hf_pr_url=pending_record.hf_pr_url,
            created_at_utc=pending_record.created_at_utc,
            updated_at_utc=processed_at_utc,
            github_pr_number=pending_record.github_pr_number,
            github_pr_url=pending_record.github_pr_url,
            processed_at_utc=processed_at_utc,
            result_reason=result_reason if terminal_status == SubmissionStatus.REJECTED else None,
            **(pending_record.model_extra or {}),
        )

        _enforce_path_invariants(processed_path, processed_record)
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        processed_path.write_text(processed_record.model_dump_json(indent=2) + "\n", encoding="utf-8")
        pending_path.unlink()

    return processed_record


def validate_submission_control_plane(submissions_root: Path = DEFAULT_SUBMISSIONS_ROOT) -> list[Path]:
    """Validate all pending/processed submission files and return checked paths.

    Example:
        If only two files exist:
        - ``pending/sub-1.json``
        - ``processed/sub-2.json``
        The return value contains both paths in deterministic order.
    """
    checked: list[Path] = []
    seen_ids: dict[str, Path] = {}
    for subdir in (_PENDING_DIR, _PROCESSED_DIR):
        for path in sorted((submissions_root / subdir).glob("*.json")):
            record = load_submission_record(path)
            if record.submission_id in seen_ids:
                first_path = seen_ids[record.submission_id]
                msg = (
                    f"duplicate submission_id '{record.submission_id}' detected in control-plane files: "
                    f"{first_path} and {path}"
                )
                raise DuplicateSubmissionIDError(msg)
            seen_ids[record.submission_id] = path
            checked.append(path)
    return checked
