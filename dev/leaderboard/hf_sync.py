"""Scheduled HF PR sync processor for leaderboard control records."""

from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib import error, parse, request

from dev.leaderboard.hf_validator import SubmissionHFValidationError, validate_hf_submission_record
from dev.leaderboard.submission_control_plane import (
    DEFAULT_SUBMISSIONS_ROOT,
    DuplicateSubmissionIDError,
    process_pending_submission,
    read_pending_submission,
    read_processed_submission,
    write_pending_submission,
)
from webarena_verified.types.leaderboard import SubmissionRecord, SubmissionStatus

if TYPE_CHECKING:
    from pathlib import Path


class HFSyncError(Exception):
    """Raised for fatal HF sync failures."""


@dataclass(frozen=True)
class HFCandidate:
    """One candidate HF discussion/PR to process."""

    hf_repo: str
    hf_pr_id: int
    hf_pr_url: str
    submission_id: str


@dataclass(frozen=True)
class HFSyncResult:
    """Aggregate sync result for reporting and workflow summaries."""

    total_candidates: int
    accepted: int
    rejected: int
    skipped: int
    pending_retry: int
    generation_id: str


def _now_utc() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


def _now_utc_z() -> str:
    return _now_utc().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_get_json(url: str, token: str | None = None) -> Any:
    req = request.Request(url)
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, token: str | None = None, payload: dict[str, Any] | None = None) -> Any:
    body = json.dumps(payload or {}).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _normalize_discussions_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("discussions", "items"):
            val = payload.get(key)
            if isinstance(val, list):
                return [item for item in val if isinstance(item, dict)]
    return []


def list_open_hf_discussions(hf_repo: str, hf_token: str | None = None) -> list[dict[str, Any]]:
    """List open dataset discussions and return pull-request discussions only."""
    repo_quoted = parse.quote(hf_repo, safe="")
    url = f"https://huggingface.co/api/datasets/{repo_quoted}/discussions?status=open"
    payload = _http_get_json(url, token=hf_token)
    discussions = _normalize_discussions_payload(payload)

    result: list[dict[str, Any]] = []
    for item in discussions:
        if item.get("isPullRequest") is True or item.get("type") in {"pull_request", "pull-request"}:
            result.append(item)
    return result


def _extract_submission_ids_from_tree_entries(entries: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    prefix = "submissions/accepted/"
    for entry in entries:
        path = entry.get("path")
        if not isinstance(path, str) or not path.startswith(prefix):
            continue
        suffix = path[len(prefix) :]
        submission_id = suffix.split("/", maxsplit=1)[0]
        if submission_id:
            ids.add(submission_id)
    return ids


def list_submission_ids_for_hf_pr(hf_repo: str, hf_pr_id: int, hf_token: str | None = None) -> set[str]:
    """Infer submission IDs from files present under refs/pr/<id> submissions/accepted/."""
    repo_quoted = parse.quote(hf_repo, safe="")
    ref = parse.quote(f"refs/pr/{hf_pr_id}", safe="")
    path = parse.quote("submissions/accepted", safe="")
    url = f"https://huggingface.co/api/datasets/{repo_quoted}/tree/{ref}/{path}?recursive=true"
    payload = _http_get_json(url, token=hf_token)

    entries: list[dict[str, Any]] = []
    if isinstance(payload, list):
        entries = [entry for entry in payload if isinstance(entry, dict)]
    elif isinstance(payload, dict):
        siblings = payload.get("siblings")
        if isinstance(siblings, list):
            entries = [entry for entry in siblings if isinstance(entry, dict)]

    return _extract_submission_ids_from_tree_entries(entries)


def merge_hf_pr(hf_repo: str, hf_pr_id: int, hf_token: str) -> None:
    """Merge an HF dataset PR/discussion."""
    if not hf_token:
        raise HFSyncError("HF token is required to merge accepted HF PRs")

    repo_quoted = parse.quote(hf_repo, safe="")
    url = f"https://huggingface.co/api/datasets/{repo_quoted}/discussions/{hf_pr_id}/merge"
    try:
        _http_post_json(url, token=hf_token, payload={})
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HFSyncError(f"HF merge request failed for PR {hf_pr_id}: {exc}") from exc


def _candidate_from_discussion(
    hf_repo: str, discussion: dict[str, Any], hf_token: str | None = None
) -> HFCandidate | None:
    pr_id = discussion.get("num")
    if not isinstance(pr_id, int):
        return None

    submission_ids = list_submission_ids_for_hf_pr(hf_repo, pr_id, hf_token=hf_token)
    if len(submission_ids) != 1:
        return None

    submission_id = next(iter(submission_ids))
    hf_pr_url = f"https://huggingface.co/datasets/{hf_repo}/discussions/{pr_id}"
    return HFCandidate(hf_repo=hf_repo, hf_pr_id=pr_id, hf_pr_url=hf_pr_url, submission_id=submission_id)


def _build_pending_record(candidate: HFCandidate, now_utc: str) -> SubmissionRecord:
    return SubmissionRecord(
        submission_id=candidate.submission_id,
        status=SubmissionStatus.PENDING,
        hf_repo=candidate.hf_repo,
        hf_pr_id=candidate.hf_pr_id,
        hf_pr_url=candidate.hf_pr_url,
        created_at_utc=now_utc,
        updated_at_utc=now_utc,
        processed_at_utc=None,
        result_reason=None,
    )


def _ensure_pending_record(submissions_root: Path, candidate: HFCandidate, now_utc: str) -> SubmissionRecord:
    try:
        return read_pending_submission(submissions_root, candidate.submission_id)
    except FileNotFoundError:
        pass

    try:
        read_processed_submission(submissions_root, candidate.submission_id)
    except FileNotFoundError:
        pass
    else:
        raise DuplicateSubmissionIDError(f"submission_id '{candidate.submission_id}' already finalized")

    pending = _build_pending_record(candidate, now_utc)
    write_pending_submission(submissions_root, pending)
    return pending


def run_hf_sync(
    hf_repo: str,
    submissions_root: Path = DEFAULT_SUBMISSIONS_ROOT,
    *,
    hf_token: str | None = None,
    merge_accepted: bool = True,
    now_utc: dt.datetime | None = None,
) -> HFSyncResult:
    """Run one HF sync batch and transition control records deterministically."""
    token = hf_token or os.getenv("HF_TOKEN")
    run_time = now_utc or _now_utc()
    now_utc_z = run_time.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    generation_id = f"hf-sync-{run_time.strftime('%Y%m%dT%H%M%SZ')}"

    discussions = list_open_hf_discussions(hf_repo, hf_token=token)

    accepted = 0
    rejected = 0
    skipped = 0
    pending_retry = 0

    for discussion in discussions:
        candidate = _candidate_from_discussion(hf_repo, discussion, hf_token=token)
        if candidate is None:
            skipped += 1
            continue

        try:
            pending_record = _ensure_pending_record(submissions_root, candidate, now_utc_z)
        except DuplicateSubmissionIDError:
            skipped += 1
            continue

        try:
            validate_hf_submission_record(pending_record, token=token)
        except SubmissionHFValidationError as exc:
            process_pending_submission(
                submissions_root=submissions_root,
                submission_id=pending_record.submission_id,
                terminal_status=SubmissionStatus.REJECTED,
                processed_at_utc=now_utc_z,
                result_reason=f"hf-validation-failed: {exc}",
            )
            rejected += 1
            continue

        if merge_accepted:
            try:
                merge_hf_pr(candidate.hf_repo, candidate.hf_pr_id, token or "")
            except HFSyncError:
                pending_retry += 1
                continue

        process_pending_submission(
            submissions_root=submissions_root,
            submission_id=pending_record.submission_id,
            terminal_status=SubmissionStatus.ACCEPTED,
            processed_at_utc=now_utc_z,
            result_reason=None,
        )
        accepted += 1

    return HFSyncResult(
        total_candidates=len(discussions),
        accepted=accepted,
        rejected=rejected,
        skipped=skipped,
        pending_retry=pending_retry,
        generation_id=generation_id,
    )
