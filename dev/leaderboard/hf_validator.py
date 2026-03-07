"""Backward-compatible HF validator module aliases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dev.leaderboard.hf_submission_validator import (
    HFSubmissionValidator,
)
from dev.leaderboard.hf_submission_validator import (
    SubmissionHFValidationError as _SubmissionHFValidationError,
)
from dev.leaderboard.hf_submission_validator import (
    validate_hf_discussion_open as _validate_hf_discussion_open,
)
from dev.leaderboard.hf_submission_validator import (
    validate_hf_submission_record as _validate_hf_submission_record,
)

if TYPE_CHECKING:
    from pathlib import Path

SubmissionHFValidationError = _SubmissionHFValidationError


def validate_hf_discussion_open(repo: str, hf_pr_id: int, token: str | None = None) -> None:
    """Validate that an HF discussion is currently open."""
    _validate_hf_discussion_open(repo, hf_pr_id, token=token)


def validate_hf_payload(record: Any, token: str | None = None) -> None:
    """Validate payload artifacts for one submission record."""
    HFSubmissionValidator(token=token).validate_payload(record)


def validate_hf_submission_record(record: Any, token: str | None = None) -> None:
    """Validate discussion and payload invariants for one record."""
    _validate_hf_submission_record(record, token=token)


def _validate_task_dir(task_dir: Path) -> None:
    """Validate one extracted task directory (compat helper)."""
    HFSubmissionValidator()._validate_task_dir(task_dir)
