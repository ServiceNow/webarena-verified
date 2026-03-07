"""Backward-compatible helpers for HF discovery and single-PR handling."""

from __future__ import annotations

import os
from typing import Any

from huggingface_hub import HfApi

from dev.leaderboard import constants
from dev.leaderboard.hf_discussion_client import STATUS_COMMENT_MARKER as _STATUS_COMMENT_MARKER
from dev.leaderboard.hf_discussion_client import HFDiscussionClient
from dev.leaderboard.hf_submission_validator import HFSubmissionValidator
from dev.leaderboard.settings import HFSyncSettings, get_hf_sync_settings
from dev.leaderboard.submission_record_repository import SubmissionRecordRepository
from dev.leaderboard.submission_sync_orchestrator import SubmissionSyncOrchestrator
from dev.leaderboard.template_renderer import TemplateRenderer

STATUS_COMMENT_MARKER = _STATUS_COMMENT_MARKER


def _get_open_submission_prs(api: HfApi, hf_repo: str) -> list[Any]:
    """List open submission PR discussions for one dataset repo."""
    discussions = list(
        api.get_repo_discussions(
            repo_id=hf_repo,
            repo_type=constants.HF_REPO_TYPE_DATASET,
            discussion_type="pull_request",
            discussion_status="open",
        )
    )
    return [
        item
        for item in discussions
        if (item.title or "").startswith(constants.HF_SUBMISSION_DISCUSSION_TITLE_PREFIX)
        and (item.status or "").lower() == "open"
    ]


def _latest_head_sha(details: Any) -> str | None:
    """Extract latest commit SHA from discussion details payload."""
    head_sha: str | None = None
    for event in details.events:
        oid = getattr(event, "oid", None)
        if isinstance(oid, str) and oid:
            head_sha = oid
    return head_sha


def discover_submission_prs(hf_repo: str, hf_token: str) -> dict[str, Any]:
    """Discover open HF submission PRs and emit matrix payload."""
    api = HfApi(token=hf_token)
    include: list[dict[str, Any]] = []
    for discussion in _get_open_submission_prs(api, hf_repo):
        hf_pr_id = int(discussion.num)
        details = api.get_discussion_details(
            repo_id=hf_repo,
            discussion_num=hf_pr_id,
            repo_type=constants.HF_REPO_TYPE_DATASET,
            token=hf_token,
        )
        head_sha = _latest_head_sha(details)
        if not head_sha:
            continue
        include.append({"hf_pr_id": hf_pr_id, "hf_head_sha": head_sha})
    return {"count": len(include), "matrix": {"include": include}}


def _resolve_settings(hf_repo: str | None, hf_token: str | None) -> HFSyncSettings:
    settings = get_hf_sync_settings()
    if hf_repo is None and hf_token is None:
        return settings
    merged = settings.model_dump(mode="python")
    if hf_repo is not None:
        merged["leaderboard_hf_repo"] = hf_repo
    if hf_token is not None:
        merged["hf_token"] = hf_token
    return HFSyncSettings.model_validate(merged)


def run_hf_single_pr(
    hf_pr_id: int,
    *,
    expected_head_sha: str | None = None,
    merge_accepted: bool = True,
    hf_repo: str | None = None,
    hf_token: str | None = None,
) -> None:
    """Run the single-PR sync flow for one HF PR id."""
    resolved_token = hf_token or os.getenv("HF_TOKEN")
    settings = _resolve_settings(hf_repo=hf_repo, hf_token=resolved_token)
    api = HfApi(token=settings.hf_token)
    orchestrator = SubmissionSyncOrchestrator(
        settings=settings,
        discussion_client=HFDiscussionClient(
            api=api,
            hf_repo=settings.leaderboard_hf_repo,
            token=settings.hf_token,
        ),
        validator=HFSubmissionValidator(token=settings.hf_token),
        repository=SubmissionRecordRepository(root=constants.LEADERBOARD_SUBMISSIONS_ROOT),
        template_renderer=TemplateRenderer(),
    )
    orchestrator.run_hf_single_pr(
        hf_pr_id=hf_pr_id,
        expected_head_sha=expected_head_sha,
        merge_accepted=merge_accepted,
    )
