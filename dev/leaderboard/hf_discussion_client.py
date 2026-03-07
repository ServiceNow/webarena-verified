"""Hugging Face discussion client wrapper for leaderboard sync."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from huggingface_hub.community import DiscussionComment, DiscussionCommit
from huggingface_hub.utils import HfHubHTTPError

from dev.leaderboard import constants
from dev.leaderboard.models import HFDiscussionStatus

if TYPE_CHECKING:
    from huggingface_hub import HfApi

LOGGER = logging.getLogger(__name__)
STATUS_COMMENT_MARKER = "<!-- leaderboard-hf-sync-status -->"


class SyncCommentStatus(StrEnum):
    """Status labels written into the bot comment on HF PR discussions."""

    PROCESSING = "PROCESSING"
    REJECTED_MUTATED_PR = "REJECTED_MUTATED_PR"
    PASS = "PASS"
    FAILED = "FAILED"


class HFDiscussionClient:
    """Typed wrapper over Hugging Face discussion APIs used by sync."""

    def __init__(self, api: HfApi, hf_repo: str, token: str) -> None:
        """Store API client + repo context for discussion operations."""
        self._api = api
        self._hf_repo = hf_repo
        self._token = token

    def list_open_submission_prs(self) -> list[Any]:
        """List open PR discussions and keep only title-contract submission PRs."""
        try:
            discussions = list(
                self._api.get_repo_discussions(
                    repo_id=self._hf_repo,
                    repo_type=constants.HF_REPO_TYPE_DATASET,
                    discussion_type="pull_request",
                    discussion_status=HFDiscussionStatus.OPEN.value,
                )
            )
        except HfHubHTTPError as exc:
            raise RuntimeError(f"Unable to list open HF pull requests for '{self._hf_repo}': {exc}") from exc

        filtered = [
            discussion
            for discussion in discussions
            if constants.HF_SUBMISSION_TITLE_PATTERN.match(discussion.title or "")
        ]
        LOGGER.info("Found %s open submission PR discussion(s) after title filtering", len(filtered))
        return filtered

    def get_discussion_details(self, hf_pr_id: int) -> Any:
        """Fetch discussion details payload for one PR number."""
        return self._api.get_discussion_details(
            repo_id=self._hf_repo,
            discussion_num=hf_pr_id,
            repo_type=constants.HF_REPO_TYPE_DATASET,
            token=self._token,
        )

    def latest_head_sha(self, details: Any) -> str | None:
        """Extract the latest commit SHA by scanning discussion events in order."""
        head_sha: str | None = None
        for event in details.events:
            if isinstance(event, DiscussionCommit):
                head_sha = event.oid
        return head_sha

    def upsert_status_comment(self, hf_pr_id: int, status: SyncCommentStatus, message: str) -> None:
        """Create or edit the single managed status comment identified by marker."""
        details = self.get_discussion_details(hf_pr_id)
        content = self._status_comment_content(status=status, message=message)
        existing_comment: DiscussionComment | None = None
        for event in details.events:
            if (
                isinstance(event, DiscussionComment)
                and not event.hidden
                and STATUS_COMMENT_MARKER in (event.content or "")
            ):
                existing_comment = event
        if existing_comment is None:
            self._api.comment_discussion(
                repo_id=self._hf_repo,
                discussion_num=hf_pr_id,
                comment=content,
                repo_type=constants.HF_REPO_TYPE_DATASET,
                token=self._token,
            )
            return
        self._api.edit_discussion_comment(
            repo_id=self._hf_repo,
            discussion_num=hf_pr_id,
            comment_id=existing_comment.id,
            new_content=content,
            repo_type=constants.HF_REPO_TYPE_DATASET,
            token=self._token,
        )

    def merge_pull_request(self, hf_pr_id: int, comment: str) -> None:
        """Merge the HF pull request with a rendered merge comment."""
        self._api.merge_pull_request(
            repo_id=self._hf_repo,
            discussion_num=hf_pr_id,
            repo_type=constants.HF_REPO_TYPE_DATASET,
            token=self._token,
            comment=comment,
        )

    @staticmethod
    def _status_comment_content(status: SyncCommentStatus, message: str) -> str:
        """Build normalized markdown body used for the managed status comment."""
        return f"{STATUS_COMMENT_MARKER}\nLeaderboard sync status: **{status.value}**\n\n{message}\n"
