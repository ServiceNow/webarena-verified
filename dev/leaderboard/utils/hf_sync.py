"""HF leaderboard sync implementation used by invoke entry points."""

from __future__ import annotations

import json
import logging
import os
import re
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


def _now_utc_z() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _generation_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


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


def _status_comment_content(status: str, message: str) -> str:
    return f"{STATUS_COMMENT_MARKER}\nLeaderboard sync status: **{status}**\n\n{message}\n"


def _upsert_status_comment(api: HfApi, hf_repo: str, hf_pr_id: int, token: str, status: str, message: str) -> None:
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
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            handle.write(f"count={count}\n")
            handle.write("matrix<<EOF\n")
            handle.write(f"{matrix_json}\n")
            handle.write("EOF\n")
    print(f"Discovered {count} matching open HF submission PR(s)")
    print(f"count={count}")
    print(f"matrix={matrix_json}")


def run_hf_sync() -> None:
    """Sync and process open HF dataset pull requests into control-plane records."""
    settings = get_hf_sync_settings()

    generation_id = _generation_id()

    LOGGER.info("Starting HF sync for repo=%s", settings.leaderboard_hf_repo)
    api = HfApi(token=settings.hf_token)
    discussions = _get_open_submission_prs(api, settings.leaderboard_hf_repo)

    existing = _load_existing_records()

    total_candidates = len(discussions)
    accepted = 0
    rejected = 0
    skipped = 0
    pending_retry = 0

    for discussion in discussions:
        hf_pr_id = int(discussion.num)
        hf_pr_url = discussion.url
        key = (settings.leaderboard_hf_repo, hf_pr_id)
        previous = existing.get(key)
        now_utc = _now_utc_z()

        candidate = SubmissionRecord(
            submission_id=previous.submission_id
            if previous
            else _submission_id(settings.leaderboard_hf_repo, hf_pr_id),
            status=SubmissionStatus.PENDING,
            hf_repo=settings.leaderboard_hf_repo,
            hf_pr_id=hf_pr_id,
            hf_pr_url=hf_pr_url,
            created_at_utc=previous.created_at_utc if previous else now_utc,
            updated_at_utc=now_utc,
            github_pr_url=previous.github_pr_url if previous else None,
            processed_at_utc=None,
            result_reason=None,
        )

        try:
            validate_hf_submission_record(candidate, token=settings.hf_token)
            new_status = SubmissionStatus.ACCEPTED
            result_reason = None
            accepted += 1
        except SubmissionHFValidationError as exc:
            new_status = _classify_validation_failure(exc)
            result_reason = str(exc)
            if new_status == SubmissionStatus.PENDING:
                pending_retry += 1
            else:
                rejected += 1

        updated_record = SubmissionRecord(
            submission_id=candidate.submission_id,
            status=new_status,
            hf_repo=candidate.hf_repo,
            hf_pr_id=candidate.hf_pr_id,
            hf_pr_url=candidate.hf_pr_url,
            created_at_utc=candidate.created_at_utc,
            updated_at_utc=now_utc,
            github_pr_url=candidate.github_pr_url,
            processed_at_utc=now_utc if new_status != SubmissionStatus.PENDING else None,
            result_reason=result_reason,
        )

        if previous and previous.model_dump(mode="json") == updated_record.model_dump(mode="json"):
            skipped += 1
            continue

        if previous:
            previous_path = _record_path(previous)
            if previous_path.exists():
                previous_path.unlink()
        _write_record(updated_record)

    LOGGER.info(
        "HF sync completed: total=%s accepted=%s rejected=%s skipped=%s pending_retry=%s generation_id=%s",
        total_candidates,
        accepted,
        rejected,
        skipped,
        pending_retry,
        generation_id,
    )

    # Key/value output contract for workflow usage.
    print(f"total_candidates={total_candidates}")
    print(f"accepted={accepted}")
    print(f"rejected={rejected}")
    print(f"skipped={skipped}")
    print(f"pending_retry={pending_retry}")
    print(f"generation_id={generation_id}")


def run_hf_single_pr(hf_pr_id: int, expected_head_sha: str | None = None, merge_accepted: bool = True) -> None:
    """Process exactly one HF dataset PR and write/update its control-plane record."""
    settings = get_hf_sync_settings()
    now_utc = _now_utc_z()
    api = HfApi(token=settings.hf_token)
    key = (settings.leaderboard_hf_repo, hf_pr_id)
    existing = _load_existing_records()
    previous = existing.get(key)

    details = api.get_discussion_details(
        repo_id=settings.leaderboard_hf_repo,
        discussion_num=hf_pr_id,
        repo_type="dataset",
        token=settings.hf_token,
    )
    if details.status != "open":
        LOGGER.info("Skipping HF PR %s because it is not open (status=%s)", hf_pr_id, details.status)
        return
    if not SUBMISSION_TITLE_PATTERN.match(details.title or ""):
        LOGGER.info("Skipping HF PR %s because title does not match submission pattern", hf_pr_id)
        return

    start_sha = _latest_head_sha(details)
    if not start_sha:
        LOGGER.info("Skipping HF PR %s because no commit SHA was found", hf_pr_id)
        return
    if expected_head_sha and expected_head_sha != start_sha:
        LOGGER.info(
            "Skipping HF PR %s because head SHA changed since discover (expected=%s current=%s)",
            hf_pr_id,
            expected_head_sha,
            start_sha,
        )
        return

    initial_head_sha = getattr(previous, "initial_head_sha", start_sha) if previous else start_sha
    if previous and initial_head_sha != start_sha:
        status = SubmissionStatus.REJECTED
        reason = (
            f"PR mutated after initial lock. locked_initial_head_sha={initial_head_sha} current_head_sha={start_sha}. "
            "Open a new PR for a new submission."
        )
        updated = SubmissionRecord(
            submission_id=previous.submission_id,
            status=status,
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
        previous_path = _record_path(previous)
        if previous_path.exists():
            previous_path.unlink()
        _write_record(updated)
        _upsert_status_comment(
            api,
            settings.leaderboard_hf_repo,
            hf_pr_id,
            settings.hf_token,
            status="REJECTED_MUTATED_PR",
            message=reason,
        )
        return

    _upsert_status_comment(
        api,
        settings.leaderboard_hf_repo,
        hf_pr_id,
        settings.hf_token,
        status="PROCESSING",
        message=f"Processing started for head SHA `{start_sha}`.",
    )

    candidate = SubmissionRecord(
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

    try:
        validate_hf_submission_record(candidate, token=settings.hf_token)
        new_status = SubmissionStatus.ACCEPTED
        result_reason = None
    except SubmissionHFValidationError as exc:
        new_status = _classify_validation_failure(exc)
        result_reason = str(exc)

    if new_status == SubmissionStatus.ACCEPTED:
        final_details = api.get_discussion_details(
            repo_id=settings.leaderboard_hf_repo,
            discussion_num=hf_pr_id,
            repo_type="dataset",
            token=settings.hf_token,
        )
        final_sha = _latest_head_sha(final_details)
        if final_details.status != "open" or final_sha != start_sha:
            new_status = SubmissionStatus.REJECTED
            result_reason = (
                "Submission became stale before finalize (PR closed or head SHA changed). "
                "Open a new PR for a new submission."
            )

    updated = SubmissionRecord(
        submission_id=candidate.submission_id,
        status=new_status,
        hf_repo=candidate.hf_repo,
        hf_pr_id=candidate.hf_pr_id,
        hf_pr_url=candidate.hf_pr_url,
        created_at_utc=candidate.created_at_utc,
        updated_at_utc=now_utc,
        github_pr_url=candidate.github_pr_url,
        processed_at_utc=now_utc if new_status != SubmissionStatus.PENDING else None,
        result_reason=result_reason,
        initial_head_sha=initial_head_sha,
        processed_head_sha=start_sha,
    )

    if previous:
        previous_path = _record_path(previous)
        if previous_path.exists():
            previous_path.unlink()
    _write_record(updated)

    if new_status == SubmissionStatus.ACCEPTED:
        _upsert_status_comment(
            api,
            settings.leaderboard_hf_repo,
            hf_pr_id,
            settings.hf_token,
            status="PASS",
            message=f"Validation passed for head SHA `{start_sha}`.",
        )
        if merge_accepted:
            api.merge_pull_request(
                repo_id=settings.leaderboard_hf_repo,
                discussion_num=hf_pr_id,
                repo_type="dataset",
                token=settings.hf_token,
                comment=(
                    "Leaderboard sync passed validation. "
                    "Merging submission PR."
                ),
            )
        return

    final_reason = result_reason or "Validation failed."
    _upsert_status_comment(
        api,
        settings.leaderboard_hf_repo,
        hf_pr_id,
        settings.hf_token,
        status="FAILED",
        message=final_reason,
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
