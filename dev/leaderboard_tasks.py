"""Invoke tasks for leaderboard control-plane and publish operations."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import TYPE_CHECKING

from invoke import task

from dev.leaderboard.hf_sync import run_hf_sync
from dev.leaderboard.publish import publish_from_processed
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


@task(name="hf-sync")
def hf_sync(
    _ctx: Context,
    hf_repo: str,
    submissions_root: str = str(DEFAULT_SUBMISSIONS_ROOT),
    hf_token: str = "",
    merge_accepted: bool = True,
) -> None:
    """Poll HF PRs, validate payloads, and transition submission control records."""
    result = run_hf_sync(
        hf_repo=hf_repo,
        submissions_root=Path(submissions_root),
        hf_token=hf_token or None,
        merge_accepted=merge_accepted,
    )
    print(f"total_candidates={result.total_candidates}")
    print(f"accepted={result.accepted}")
    print(f"rejected={result.rejected}")
    print(f"skipped={result.skipped}")
    print(f"pending_retry={result.pending_retry}")
    print(f"generation_id={result.generation_id}")


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


@task(name="publish-from-processed")
def publish_from_processed_task(
    _ctx: Context,
    gh_pages_root: str,
    processed_dir: str = "leaderboard/data/submissions/processed",
    staging_dir: str = ".tmp/leaderboard-publish-staging",
    generation_id: str = "",
    generated_at_utc: str = "",
    dry_run: bool = False,
) -> None:
    """Generate and publish leaderboard files from processed submission records."""
    manifest = publish_from_processed(
        gh_pages_root=Path(gh_pages_root),
        processed_dir=Path(processed_dir),
        staging_dir=Path(staging_dir),
        generation_id=generation_id or None,
        generated_at_utc=generated_at_utc or None,
        dry_run=dry_run,
    )
    print(f"generation_id={manifest.generation_id}")
    print(f"full_file={manifest.full_file}")
    print(f"hard_file={manifest.hard_file}")
