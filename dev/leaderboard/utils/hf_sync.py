"""HF leaderboard sync implementation used by invoke entry points."""

from __future__ import annotations

import json
import logging
import re
from enum import StrEnum
from datetime import UTC, datetime
from pathlib import Path

from huggingface_hub import HfApi
from huggingface_hub.community import DiscussionComment, DiscussionCommit
from huggingface_hub.utils import HfHubHTTPError

from dev.leaderboard import constants
from dev.leaderboard.hf_submission_validator import SubmissionHFValidationError, validate_hf_submission_record
from dev.leaderboard.models import SubmissionRecord, SubmissionStatus
from dev.leaderboard.settings import get_hf_sync_settings

LOGGER = logging.getLogger(__name__)
SUBMISSION_TITLE_PATTERN = re.compile(rf"^{re.escape(constants.HF_SUBMISSION_DISCUSSION_TITLE_PREFIX)}.+$")
STATUS_COMMENT_MARKER = "<!-- leaderboard-hf-sync-status -->"


class SyncCommentStatus(StrEnum):
    PROCESSING = "PROCESSING"
    REJECTED_MUTATED_PR = "REJECTED_MUTATED_PR"
    PASS = "PASS"
    FAILED = "FAILED"


def _now_utc_z() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize_repo(repo: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")


def _submission_id(repo: str, hf_pr_id: int) -> str:
    return f"{_sanitize_repo(repo)}-pr-{hf_pr_id}"


def _status_dir(status: SubmissionStatus) -> Path:
    return constants.LEADERBOARD_SUBMISSIONS_ROOT / status.value


def _record_path(record: SubmissionRecord) -> Path:
    return _status_dir(record.status) / f"{record.submission_id}.json"


def _write_record(record: SubmissionRecord) -> None:
    path = _record_path(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(record.model_dump(mode='json'), indent=2, sort_keys=True)}\n", encoding="utf-8")


def _load_existing_records() -> dict[tuple[str, int], SubmissionRecord]:
    records: dict[tuple[str, int], SubmissionRecord] = {}
    if not constants.LEADERBOARD_SUBMISSIONS_ROOT.exists():
        return records

    for status_dir in constants.LEADERBOARD_SUBMISSIONS_ROOT.iterdir():
        if not status_dir.is_dir():
            continue
        for record_file in status_dir.glob("*.json"):
            try:
                payload = json.loads(record_file.read_text(encoding="utf-8"))
                record = SubmissionRecord.model_validate(payload)
            except Exception as exc:
                raise RuntimeError(f"Unreadable submission record '{record_file}': {exc}") from exc
            records[(record.hf_repo, record.hf_pr_id)] = record
    return records


def _classify_validation_failure(exc: SubmissionHFValidationError) -> SubmissionStatus:
    """Classify fail-closed/network-style validation failures as pending for retry."""
    message = str(exc).lower()
    if any(marker in message for marker in constants.HF_SYNC_TRANSIENT_ERROR_MARKERS):
        return SubmissionStatus.PENDING
    return SubmissionStatus.REJECTED


def _latest_head_sha(details) -> str | None:
    head_sha: str | None = None
    for event in details.events:
        if isinstance(event, DiscussionCommit):
            head_sha = event.oid
    return head_sha


def _status_comment_content(status: SyncCommentStatus, message: str) -> str:
    return f"{STATUS_COMMENT_MARKER}\nLeaderboard sync status: **{status.value}**\n\n{message}\n"


def _upsert_status_comment(
    api: HfApi,
    hf_repo: str,
    hf_pr_id: int,
    token: str,
    status: SyncCommentStatus,
    message: str,
) -> None:
    details = api.get_discussion_details(repo_id=hf_repo, discussion_num=hf_pr_id, repo_type="dataset", token=token)
    content = _status_comment_content(status=status, message=message)
    existing_comment: DiscussionComment | None = None
    for event in details.events:
        if isinstance(event, DiscussionComment) and not event.hidden and STATUS_COMMENT_MARKER in (event.content or ""):
            existing_comment = event
    if existing_comment is None:
        api.comment_discussion(
            repo_id=hf_repo,
            discussion_num=hf_pr_id,
            comment=content,
            repo_type="dataset",
            token=token,
        )
        return
    api.edit_discussion_comment(
        repo_id=hf_repo,
        discussion_num=hf_pr_id,
        comment_id=existing_comment.id,
        new_content=content,
        repo_type="dataset",
        token=token,
    )


def _get_open_submission_prs(api: HfApi, hf_repo: str) -> list:
    """Return open HF dataset PR discussions that match submission title contract."""
    try:
        discussions = list(
            api.get_repo_discussions(
                repo_id=hf_repo,
                repo_type="dataset",
                discussion_type="pull_request",
                discussion_status="open",
            )
        )
    except HfHubHTTPError as exc:
        raise RuntimeError(f"Unable to list open HF pull requests for '{hf_repo}': {exc}") from exc

    filtered = [d for d in discussions if SUBMISSION_TITLE_PATTERN.match(d.title or "")]
    LOGGER.info("Found %s open submission PR discussion(s) after title filtering", len(filtered))
    return filtered


def discover_submission_prs(hf_repo: str, token: str) -> dict[str, object]:
    """Discover open submission PRs and return workflow-ready structured data."""
    api = HfApi(token=token)
    discussions = _get_open_submission_prs(api, hf_repo)
    include: list[dict[str, str | int]] = []

    for discussion in discussions:
        hf_pr_id = int(discussion.num)
        details = api.get_discussion_details(
            repo_id=hf_repo,
            discussion_num=hf_pr_id,
            repo_type="dataset",
            token=token,
        )
        head_sha = _latest_head_sha(details) or ""
        include.append(
            {
                "hf_pr_id": hf_pr_id,
                "hf_head_sha": head_sha,
            }
        )

    return {
        "count": len(include),
        "matrix": {"include": include},
    }


def run_discover_hf_submission_prs() -> None:
    """Discover open submission HF PRs and emit matrix/count outputs for CI."""
    settings = get_hf_sync_settings()
    discovered = discover_submission_prs(settings.leaderboard_hf_repo, settings.hf_token)
    count = str(discovered["count"])
    matrix_json = json.dumps(discovered["matrix"], separators=(",", ":"))
    output_path = settings.github_output
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            handle.write(f"count={count}\n")
            handle.write("matrix<<EOF\n")
            handle.write(f"{matrix_json}\n")
            handle.write("EOF\n")
    print(f"Discovered {count} matching open HF submission PR(s)")
    print(f"count={count}")
    print(f"matrix={matrix_json}")


def _load_single_pr_context(
    api: HfApi,
    *,
    hf_repo: str,
    hf_pr_id: int,
    token: str,
    expected_head_sha: str | None,
):
    details = api.get_discussion_details(
        repo_id=hf_repo,
        discussion_num=hf_pr_id,
        repo_type="dataset",
        token=token,
    )
    if details.status != "open":
        LOGGER.info("Skipping HF PR %s because it is not open (status=%s)", hf_pr_id, details.status)
        return None, None

    start_sha = _latest_head_sha(details)
    if not start_sha:
        LOGGER.info("Skipping HF PR %s because no commit SHA was found", hf_pr_id)
        return None, None
    if expected_head_sha and expected_head_sha != start_sha:
        LOGGER.info(
            "Skipping HF PR %s because head SHA changed since discover (expected=%s current=%s)",
            hf_pr_id,
            expected_head_sha,
            start_sha,
        )
        return None, None
    return details, start_sha


def _persist_submission_record(previous: SubmissionRecord | None, updated: SubmissionRecord) -> None:
    if previous:
        previous_path = _record_path(previous)
        if previous_path.exists():
            previous_path.unlink()
    _write_record(updated)


def _reject_mutated_pr(
    *,
    api: HfApi,
    settings,
    previous: SubmissionRecord,
    details,
    hf_pr_id: int,
    now_utc: str,
    initial_head_sha: str,
    start_sha: str,
) -> None:
    reason = (
        f"PR mutated after initial lock. locked_initial_head_sha={initial_head_sha} current_head_sha={start_sha}. "
        "Open a new PR for a new submission."
    )
    updated = SubmissionRecord(
        submission_id=previous.submission_id,
        status=SubmissionStatus.REJECTED,
        hf_repo=settings.leaderboard_hf_repo,
        hf_pr_id=hf_pr_id,
        hf_pr_url=details.url,
        created_at_utc=previous.created_at_utc,
        updated_at_utc=now_utc,
        github_pr_url=previous.github_pr_url,
        processed_at_utc=now_utc,
        result_reason=reason,
        initial_head_sha=initial_head_sha,
        processed_head_sha=start_sha,
    )
    _persist_submission_record(previous, updated)
    _upsert_status_comment(
        api,
        settings.leaderboard_hf_repo,
        hf_pr_id,
        settings.hf_token,
        status=SyncCommentStatus.REJECTED_MUTATED_PR,
        message=reason,
    )


def _build_candidate_record(
    *,
    settings,
    previous: SubmissionRecord | None,
    details,
    hf_pr_id: int,
    now_utc: str,
    start_sha: str,
    initial_head_sha: str,
) -> SubmissionRecord:
    return SubmissionRecord(
        submission_id=previous.submission_id if previous else _submission_id(settings.leaderboard_hf_repo, hf_pr_id),
        status=SubmissionStatus.PENDING,
        hf_repo=settings.leaderboard_hf_repo,
        hf_pr_id=hf_pr_id,
        hf_pr_url=details.url,
        created_at_utc=previous.created_at_utc if previous else now_utc,
        updated_at_utc=now_utc,
        github_pr_url=previous.github_pr_url if previous else None,
        processed_at_utc=None,
        result_reason=None,
        initial_head_sha=initial_head_sha,
        processed_head_sha=start_sha,
    )


def _validate_candidate(candidate: SubmissionRecord, token: str) -> tuple[SubmissionStatus, str | None]:
    try:
        validate_hf_submission_record(candidate, token=token)
        return SubmissionStatus.ACCEPTED, None
    except SubmissionHFValidationError as exc:
        return _classify_validation_failure(exc), str(exc)


def _apply_stale_guard(
    *,
    api: HfApi,
    settings,
    hf_pr_id: int,
    start_sha: str,
    status: SubmissionStatus,
    reason: str | None,
) -> tuple[SubmissionStatus, str | None]:
    if status != SubmissionStatus.ACCEPTED:
        return status, reason

    final_details = api.get_discussion_details(
        repo_id=settings.leaderboard_hf_repo,
        discussion_num=hf_pr_id,
        repo_type="dataset",
        token=settings.hf_token,
    )
    final_sha = _latest_head_sha(final_details)
    if final_details.status != "open" or final_sha != start_sha:
        return (
            SubmissionStatus.REJECTED,
            "Submission became stale before finalize (PR closed or head SHA changed). Open a new PR for a new submission.",
        )
    return status, reason


def _build_updated_record(
    *,
    candidate: SubmissionRecord,
    status: SubmissionStatus,
    reason: str | None,
    now_utc: str,
    start_sha: str,
    initial_head_sha: str,
) -> SubmissionRecord:
    return SubmissionRecord(
        submission_id=candidate.submission_id,
        status=status,
        hf_repo=candidate.hf_repo,
        hf_pr_id=candidate.hf_pr_id,
        hf_pr_url=candidate.hf_pr_url,
        created_at_utc=candidate.created_at_utc,
        updated_at_utc=now_utc,
        github_pr_url=candidate.github_pr_url,
        processed_at_utc=now_utc if status != SubmissionStatus.PENDING else None,
        result_reason=reason,
        initial_head_sha=initial_head_sha,
        processed_head_sha=start_sha,
    )


def _publish_final_status(
    *,
    api: HfApi,
    settings,
    hf_pr_id: int,
    start_sha: str,
    status: SubmissionStatus,
    reason: str | None,
    merge_accepted: bool,
) -> None:
    if status == SubmissionStatus.ACCEPTED:
        _upsert_status_comment(
            api,
        settings.leaderboard_hf_repo,
        hf_pr_id,
        settings.hf_token,
        status=SyncCommentStatus.PASS,
        message=f"Validation passed for head SHA `{start_sha}`.",
    )
        if merge_accepted:
            api.merge_pull_request(
                repo_id=settings.leaderboard_hf_repo,
                discussion_num=hf_pr_id,
                repo_type="dataset",
                token=settings.hf_token,
                comment="Leaderboard sync passed validation. Merging submission PR.",
            )
        return

    _upsert_status_comment(
        api,
        settings.leaderboard_hf_repo,
        hf_pr_id,
        settings.hf_token,
        status=SyncCommentStatus.FAILED,
        message=reason or "Validation failed.",
    )


def run_hf_single_pr(hf_pr_id: int, expected_head_sha: str | None = None, merge_accepted: bool = True) -> None:
    """Process exactly one HF dataset PR and write/update its control-plane record."""
    settings = get_hf_sync_settings()
    now_utc = _now_utc_z()
    api = HfApi(token=settings.hf_token)
    key = (settings.leaderboard_hf_repo, hf_pr_id)
    existing = _load_existing_records()
    previous = existing.get(key)

    details, start_sha = _load_single_pr_context(
        api,
        hf_repo=settings.leaderboard_hf_repo,
        hf_pr_id=hf_pr_id,
        token=settings.hf_token,
        expected_head_sha=expected_head_sha,
    )
    if details is None or start_sha is None:
        return

    initial_head_sha = getattr(previous, "initial_head_sha", start_sha) if previous else start_sha
    if previous and initial_head_sha != start_sha:
        _reject_mutated_pr(
            api=api,
            settings=settings,
            previous=previous,
            details=details,
            hf_pr_id=hf_pr_id,
            now_utc=now_utc,
            initial_head_sha=initial_head_sha,
            start_sha=start_sha,
        )
        return

    _upsert_status_comment(
        api,
        settings.leaderboard_hf_repo,
        hf_pr_id,
        settings.hf_token,
        status=SyncCommentStatus.PROCESSING,
        message=f"Processing started for head SHA `{start_sha}`.",
    )

    candidate = _build_candidate_record(
        settings=settings,
        previous=previous,
        details=details,
        hf_pr_id=hf_pr_id,
        now_utc=now_utc,
        start_sha=start_sha,
        initial_head_sha=initial_head_sha,
    )
    new_status, result_reason = _validate_candidate(candidate, settings.hf_token)
    new_status, result_reason = _apply_stale_guard(
        api=api,
        settings=settings,
        hf_pr_id=hf_pr_id,
        start_sha=start_sha,
        status=new_status,
        reason=result_reason,
    )

    updated = _build_updated_record(
        candidate=candidate,
        status=new_status,
        reason=result_reason,
        now_utc=now_utc,
        start_sha=start_sha,
        initial_head_sha=initial_head_sha,
    )
    _persist_submission_record(previous, updated)

    _publish_final_status(
        api=api,
        settings=settings,
        hf_pr_id=hf_pr_id,
        start_sha=start_sha,
        status=new_status,
        reason=result_reason,
        merge_accepted=merge_accepted,
    )


def build_submissions_json(output_path: Path | None = None) -> Path:
    """Build deterministic submissions.json from control-plane records."""
    destination = output_path or Path(".tmp-gh-pages/submissions.json")
    root = constants.LEADERBOARD_SUBMISSIONS_ROOT
    records: list[dict] = []
    if root.exists():
        for path in sorted(root.glob("*/*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(payload)

    output = {
        "generated_at_utc": _now_utc_z(),
        "count": len(records),
        "records": records,
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOGGER.info("Built submissions JSON at %s with %s record(s)", destination, len(records))
    return destination
