"""Orchestration for leaderboard HF submission sync."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dev.leaderboard import constants
from dev.leaderboard.hf_discussion_client import HFDiscussionClient, SyncCommentStatus
from dev.leaderboard.hf_submission_validator import HFSubmissionValidator, SubmissionHFValidationError
from dev.leaderboard.models import (
    DiscoverMatrix,
    DiscoverMatrixItem,
    DiscoverResult,
    HFDiscussionStatus,
    SubmissionRecord,
    SubmissionsManfiest,
    SubmissionStatus,
)

if TYPE_CHECKING:
    from dev.leaderboard.settings import HFSyncSettings
    from dev.leaderboard.submission_record_repository import SubmissionRecordRepository
    from dev.leaderboard.template_renderer import TemplateRenderer

LOGGER = logging.getLogger(__name__)


class SubmissionSyncOrchestrator:
    """Dependency-injected application service for leaderboard HF sync."""

    def __init__(
        self,
        settings: HFSyncSettings,
        discussion_client: HFDiscussionClient,
        validator: HFSubmissionValidator,
        repository: SubmissionRecordRepository,
        template_renderer: TemplateRenderer,
    ) -> None:
        """Wire injected collaborators used by the sync workflow."""
        self._settings = settings
        self._discussion_client = discussion_client
        self._validator = validator
        self._repository = repository
        self._template_renderer = template_renderer

    def run_hf_single_pr(
        self, hf_pr_id: int, expected_head_sha: str | None = None, merge_accepted: bool = True
    ) -> None:
        """Process one PR from validation through status publish and record persistence."""
        LOGGER.info("Starting single-PR sync for hf_pr_id=%s", hf_pr_id)

        # 1) Load current state and establish a stable PR context.
        now_utc = self._now_utc_z()
        key = (self._settings.leaderboard_hf_repo, hf_pr_id)
        existing = self._repository.load_existing_records()
        previous = existing.get(key)
        LOGGER.info("Loaded existing records=%s previous_exists=%s", len(existing), previous is not None)

        details, start_sha = self._load_single_pr_context(hf_pr_id=hf_pr_id, expected_head_sha=expected_head_sha)
        if details is None or start_sha is None:
            LOGGER.info("Skipping hf_pr_id=%s due to context guard", hf_pr_id)
            return
        LOGGER.info("Loaded PR context hf_pr_id=%s head_sha=%s", hf_pr_id, start_sha)

        # 2) Enforce mutation guard across processing runs.
        initial_head_sha = previous.initial_head_sha if previous and previous.initial_head_sha else start_sha
        if previous and initial_head_sha != start_sha:
            LOGGER.info(
                "Rejecting mutated PR hf_pr_id=%s initial_head_sha=%s current_head_sha=%s",
                hf_pr_id,
                initial_head_sha,
                start_sha,
            )
            self._reject_mutated_pr(
                previous=previous,
                details=details,
                hf_pr_id=hf_pr_id,
                now_utc=now_utc,
                initial_head_sha=initial_head_sha,
                start_sha=start_sha,
            )
            return

        # 3) Publish processing status and validate candidate payload.
        self._discussion_client.upsert_status_comment(
            hf_pr_id=hf_pr_id,
            status=SyncCommentStatus.PROCESSING,
            message=f"Processing started for head SHA `{start_sha}`.",
        )

        candidate = SubmissionRecord(
            submission_id=previous.submission_id
            if previous
            else self._submission_id(self._settings.leaderboard_hf_repo, hf_pr_id),
            status=SubmissionStatus.PENDING,
            hf_repo=self._settings.leaderboard_hf_repo,
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
        new_status, result_reason = self._validate_candidate(candidate)
        LOGGER.info("Validation finished hf_pr_id=%s status=%s", hf_pr_id, new_status.value)

        # 4) Re-validate freshness and build final persisted state.
        new_status, result_reason = self._apply_stale_guard(
            hf_pr_id=hf_pr_id,
            start_sha=start_sha,
            status=new_status,
            reason=result_reason,
        )
        LOGGER.info("Stale guard finished hf_pr_id=%s status=%s", hf_pr_id, new_status.value)

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
        self._repository.persist_submission_record(previous, updated)
        LOGGER.info(
            "Persisted submission record hf_pr_id=%s submission_id=%s status=%s",
            hf_pr_id,
            updated.submission_id,
            updated.status.value,
        )

        # 5) Publish terminal status (and merge on accepted if enabled).
        self._publish_final_status(
            hf_pr_id=hf_pr_id,
            start_sha=start_sha,
            status=new_status,
            reason=result_reason,
            merge_accepted=merge_accepted,
            submission_id=updated.submission_id,
        )
        LOGGER.info("Completed single-PR sync for hf_pr_id=%s", hf_pr_id)

    def discover_submission_prs(self) -> DiscoverResult:
        """Build typed CI matrix entries from discoverable open submission PRs."""
        include: list[DiscoverMatrixItem] = []
        for discussion in self._discussion_client.list_open_submission_prs():
            hf_pr_id = int(discussion.num)
            details = self._discussion_client.get_discussion_details(hf_pr_id)
            head_sha = self._discussion_client.latest_head_sha(details)
            if not head_sha:
                LOGGER.info("Skipping hf_pr_id=%s in discover because no head SHA was found", hf_pr_id)
                continue
            include.append(DiscoverMatrixItem(hf_pr_id=hf_pr_id, hf_head_sha=head_sha))
        LOGGER.info("Discovery produced %s PR candidate(s)", len(include))
        return DiscoverResult(count=len(include), matrix=DiscoverMatrix(include=include))

    def run_discover_hf_submission_prs(self) -> None:
        """Emit discovered PR count + matrix to stdout and optional GitHub output file."""
        LOGGER.info("Starting PR discovery for repo=%s", self._settings.leaderboard_hf_repo)
        discovered = self.discover_submission_prs()
        count = str(discovered.count)
        matrix_json = discovered.matrix.model_dump_json()
        output_path = self._settings.github_output
        if output_path:
            with Path(output_path).open("a", encoding="utf-8") as handle:
                handle.write(f"{constants.DISCOVER_OUTPUT_COUNT_KEY}={count}\n")
                handle.write(f"{constants.DISCOVER_OUTPUT_MATRIX_KEY}<<EOF\n")
                handle.write(f"{matrix_json}\n")
                handle.write("EOF\n")
            LOGGER.info("Wrote discovery outputs to %s", output_path)
        else:
            LOGGER.info("No GitHub output path configured; emitting discovery outputs to stdout only")

        print(f"Discovered {count} matching open HF submission PR(s)")
        print(f"{constants.DISCOVER_OUTPUT_COUNT_KEY}={count}")
        print(f"{constants.DISCOVER_OUTPUT_MATRIX_KEY}={matrix_json}")
        LOGGER.info("Completed PR discovery for repo=%s", self._settings.leaderboard_hf_repo)

    def build_submissions_json(self, output_path: Path | None = None) -> Path:
        """Materialize deterministic `submissions.json` from stored control-plane records."""
        destination = output_path or Path(".tmp-gh-pages/submissions.json")
        records = self._repository.read_all_records()
        output = SubmissionsManfiest(
            generated_at_utc=self._now_utc_z(),
            count=len(records),
            records=records,
        )

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(f"{output.model_dump_json(indent=2)}\n", encoding="utf-8")
        LOGGER.info("Built submissions JSON at %s with %s record(s)", destination, len(records))
        return destination

    def _load_single_pr_context(self, hf_pr_id: int, expected_head_sha: str | None) -> tuple[Any | None, str | None]:
        """Load current PR details and guard against closed/missing/mutated heads."""
        details = self._discussion_client.get_discussion_details(hf_pr_id)
        if details.status != HFDiscussionStatus.OPEN.value:
            LOGGER.info("Skipping HF PR %s because it is not open (status=%s)", hf_pr_id, details.status)
            return None, None

        start_sha = self._discussion_client.latest_head_sha(details)
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

    def _reject_mutated_pr(
        self,
        *,
        previous: SubmissionRecord,
        details: Any,
        hf_pr_id: int,
        now_utc: str,
        initial_head_sha: str,
        start_sha: str,
    ) -> None:
        """Persist terminal rejection + status comment when head SHA changed after first seen."""
        LOGGER.info("Rendering mutated-PR rejection for hf_pr_id=%s", hf_pr_id)
        reason = self._template_renderer.render_markdown_template(
            self._settings.mutated_pr_rejection_template_path,
            initial_head_sha=initial_head_sha,
            start_sha=start_sha,
        )
        updated = SubmissionRecord(
            submission_id=previous.submission_id,
            status=SubmissionStatus.REJECTED,
            hf_repo=self._settings.leaderboard_hf_repo,
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
        self._repository.persist_submission_record(previous, updated)
        self._discussion_client.upsert_status_comment(
            hf_pr_id=hf_pr_id,
            status=SyncCommentStatus.REJECTED_MUTATED_PR,
            message=reason,
        )
        LOGGER.info("Published mutated-PR rejection for hf_pr_id=%s", hf_pr_id)

    def _validate_candidate(self, candidate: SubmissionRecord) -> tuple[SubmissionStatus, str | None]:
        """Run payload validation and map failures into status + message."""
        try:
            self._validator.validate_submission_record(candidate)
            return SubmissionStatus.ACCEPTED, None
        except SubmissionHFValidationError as exc:
            return self._classify_validation_failure(exc), str(exc)

    def _apply_stale_guard(
        self,
        *,
        hf_pr_id: int,
        start_sha: str,
        status: SubmissionStatus,
        reason: str | None,
    ) -> tuple[SubmissionStatus, str | None]:
        """Recheck PR head/status post-validation to avoid accepting stale inputs."""
        if status != SubmissionStatus.ACCEPTED:
            return status, reason

        LOGGER.info("Running stale guard check for hf_pr_id=%s", hf_pr_id)
        final_details = self._discussion_client.get_discussion_details(hf_pr_id)
        final_sha = self._discussion_client.latest_head_sha(final_details)
        if final_details.status != HFDiscussionStatus.OPEN.value or final_sha != start_sha:
            return (
                SubmissionStatus.REJECTED,
                self._template_renderer.render_markdown_template(
                    self._settings.stale_rejection_template_path,
                    pr_status=str(final_details.status),
                    start_sha=start_sha,
                    final_sha=str(final_sha),
                ),
            )
        LOGGER.info("Stale guard passed for hf_pr_id=%s", hf_pr_id)
        return status, reason

    def _publish_final_status(
        self,
        *,
        hf_pr_id: int,
        start_sha: str,
        status: SubmissionStatus,
        reason: str | None,
        merge_accepted: bool,
        submission_id: str,
    ) -> None:
        """Publish terminal status comment and merge automatically on accepted PRs."""
        LOGGER.info("Publishing final status for hf_pr_id=%s status=%s", hf_pr_id, status.value)
        if status == SubmissionStatus.ACCEPTED:
            self._discussion_client.upsert_status_comment(
                hf_pr_id=hf_pr_id,
                status=SyncCommentStatus.PASS,
                message=f"Validation passed for head SHA `{start_sha}`.",
            )
            if merge_accepted:
                LOGGER.info("Merging accepted PR hf_pr_id=%s", hf_pr_id)
                merge_comment = self._template_renderer.render_markdown_template(
                    self._settings.merge_comment_template_path,
                    submission_id=submission_id,
                )
                self._discussion_client.merge_pull_request(hf_pr_id=hf_pr_id, comment=merge_comment)
            return

        self._discussion_client.upsert_status_comment(
            hf_pr_id=hf_pr_id,
            status=SyncCommentStatus.FAILED,
            message=reason or "Validation failed.",
        )
        LOGGER.info("Published failed status for hf_pr_id=%s", hf_pr_id)

    @staticmethod
    def _classify_validation_failure(exc: SubmissionHFValidationError) -> SubmissionStatus:
        """Classify fail-closed/network-style validation failures as pending for retry."""
        message = str(exc).lower()
        if any(marker in message for marker in constants.HF_SYNC_TRANSIENT_ERROR_MARKERS):
            return SubmissionStatus.PENDING
        return SubmissionStatus.REJECTED

    @staticmethod
    def _now_utc_z() -> str:
        """Return current UTC timestamp normalized to second precision with `Z` suffix."""
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _sanitize_repo(repo: str) -> str:
        """Normalize repo id into lowercase slug-safe string for submission IDs."""
        return re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")

    @classmethod
    def _submission_id(cls, repo: str, hf_pr_id: int) -> str:
        """Create stable submission id from repo slug + PR number."""
        return f"{cls._sanitize_repo(repo)}-pr-{hf_pr_id}"
