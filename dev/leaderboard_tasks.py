"""Invoke tasks for leaderboard control-plane operations."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import TYPE_CHECKING

from invoke import task

from dev.leaderboard.submission_control_plane import (
    DEFAULT_SUBMISSIONS_ROOT,
    process_pending_submission,
    validate_submission_control_plane,
)
from dev.utils import logging_utils
from webarena_verified.types.leaderboard import SubmissionStatus

if TYPE_CHECKING:
    from invoke.context import Context


def _now_utc_z() -> str:
    return dt.datetime.now(tz=dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


@task(name="submission-validate")
def submission_validate(
    _ctx: Context,
    submissions_root: str = str(DEFAULT_SUBMISSIONS_ROOT),
) -> None:
    """Validate pending/processed submission file invariants."""
    checked = validate_submission_control_plane(Path(submissions_root))
    logging_utils.print_info(f"Validated control-plane files: {len(checked)}")
    print(f"Validated {len(checked)} submission control-plane file(s).")


@task(name="submission-process")
def submission_process(
    _ctx: Context,
    submission_id: str,
    status: str,
    processed_at_utc: str = "",
    result_reason: str = "",
    submissions_root: str = str(DEFAULT_SUBMISSIONS_ROOT),
) -> None:
    """Process one pending submission to accepted/rejected."""
    terminal_status = SubmissionStatus(status)
    final_processed_at_utc = processed_at_utc or _now_utc_z()
    final_result_reason = result_reason or None
    record = process_pending_submission(
        submissions_root=Path(submissions_root),
        submission_id=submission_id,
        terminal_status=terminal_status,
        processed_at_utc=final_processed_at_utc,
        result_reason=final_result_reason,
    )
    logging_utils.print_info(
        "Processed submission record output: "
        f"submission_id={record.submission_id}, status={record.status.value}, "
        f"processed_at_utc={record.processed_at_utc}"
    )
    print(json.dumps(record.model_dump(mode="json"), indent=2))
