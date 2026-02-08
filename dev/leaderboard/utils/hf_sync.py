"""HF leaderboard sync implementation used by invoke entry points."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi
from huggingface_hub.community import DiscussionComment, DiscussionCommit
from huggingface_hub.utils import HfHubHTTPError

from dev.leaderboard import constants
from dev.leaderboard.hf_submission_validator import HFSubmissionValidator, SubmissionHFValidationError
from dev.leaderboard.models import (
    DiscoverMatrix,
    DiscoverMatrixItem,
    DiscoverResult,
    HFDiscussionStatus,
    SubmissionRecord,
    SubmissionStatus,
    SubmissionsManfiest,
)
from dev.leaderboard.settings import HFSyncSettings, get_hf_sync_settings

LOGGER = logging.getLogger(__name__)
STATUS_COMMENT_MARKER = "<!-- leaderboard-hf-sync-status -->"


class SyncCommentStatus(StrEnum):
    PROCESSING = "PROCESSING"
    REJECTED_MUTATED_PR = "REJECTED_MUTATED_PR"
    PASS = "PASS"
    FAILED = "FAILED"


class TemplateRenderer:
    """Load and render markdown templates used in status comments."""

    def render_markdown_template(self, template_path: str, **context: str) -> str:
        template = Path(template_path).read_text(encoding="utf-8")
        try:
            return template.format(**context).strip()
        except KeyError as exc:
            raise RuntimeError(f"Missing template variable '{exc.args[0]}' in {template_path}") from exc


class SubmissionRecordRepository:
    """Persist and load submission control-plane records."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def load_existing_records(self) -> dict[tuple[str, int], SubmissionRecord]:
        records: dict[tuple[str, int], SubmissionRecord] = {}
        if not self._root.exists():
            return records

        for status_dir in self._root.iterdir():
            if not status_dir.is_dir():
                continue
            for record_file in status_dir.glob("*.json"):
                try:
                    payload = json.loads(record_file.read_text(encoding="utf-8"))
                    record = SubmissionRecord.model_validate(payload)
                except (OSError, json.JSONDecodeError, ValueError) as exc:
                    raise RuntimeError(f"Unreadable submission record '{record_file}': {exc}") from exc
                records[(record.hf_repo, record.hf_pr_id)] = record
        return records

    def persist_submission_record(self, previous: SubmissionRecord | None, updated: SubmissionRecord) -> None:
        if previous:
            previous_path = self.record_path(previous)
            if previous_path.exists():
                previous_path.unlink()
        self.write_record(updated)

    def write_record(self, record: SubmissionRecord) -> None:
        path = self.record_path(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True)
        path.write_text(f"{serialized}\n", encoding="utf-8")

    def read_all_records(self) -> list[SubmissionRecord]:
        if not self._root.exists():
            return []

        records: list[SubmissionRecord] = []
        for path in sorted(self._root.glob("*/*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(SubmissionRecord.model_validate(payload))
        return records

    def record_path(self, record: SubmissionRecord) -> Path:
        return self.status_dir(record.status) / f"{record.submission_id}.json"

    def status_dir(self, status: SubmissionStatus) -> Path:
        return self._root / status.value


class HFDiscussionClient:
    """Typed wrapper over Hugging Face discussion APIs used by sync."""

    def __init__(self, api: HfApi, hf_repo: str, token: str) -> None:
        self._api = api
        self._hf_repo = hf_repo
        self._token = token

    def list_open_submission_prs(self) -> list[Any]:
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

        filtered = [discussion for discussion in discussions if constants.HF_SUBMISSION_TITLE_PATTERN.match(discussion.title or "")]
        LOGGER.info("Found %s open submission PR discussion(s) after title filtering", len(filtered))
        return filtered

    def get_discussion_details(self, hf_pr_id: int) -> Any:
        return self._api.get_discussion_details(
            repo_id=self._hf_repo,
            discussion_num=hf_pr_id,
            repo_type=constants.HF_REPO_TYPE_DATASET,
            token=self._token,
        )

    def latest_head_sha(self, details: Any) -> str | None:
        head_sha: str | None = None
        for event in details.events:
            if isinstance(event, DiscussionCommit):
                head_sha = event.oid
        return head_sha

    def upsert_status_comment(self, hf_pr_id: int, status: SyncCommentStatus, message: str) -> None:
        details = self.get_discussion_details(hf_pr_id)
        content = self._status_comment_content(status=status, message=message)
        existing_comment: DiscussionComment | None = None
        for event in details.events:
            if isinstance(event, DiscussionComment) and not event.hidden and STATUS_COMMENT_MARKER in (event.content or ""):
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
        self._api.merge_pull_request(
            repo_id=self._hf_repo,
            discussion_num=hf_pr_id,
            repo_type=constants.HF_REPO_TYPE_DATASET,
            token=self._token,
            comment=comment,
        )

    @staticmethod
    def _status_comment_content(status: SyncCommentStatus, message: str) -> str:
        return f"{STATUS_COMMENT_MARKER}\nLeaderboard sync status: **{status.value}**\n\n{message}\n"


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
        self._settings = settings
        self._discussion_client = discussion_client
        self._validator = validator
        self._repository = repository
        self._template_renderer = template_renderer

    @classmethod
    def from_settings(cls, settings: HFSyncSettings) -> SubmissionSyncOrchestrator:
        api = HfApi(token=settings.hf_token)
        return cls(
            settings=settings,
            discussion_client=HFDiscussionClient(api=api, hf_repo=settings.leaderboard_hf_repo, token=settings.hf_token),
            validator=HFSubmissionValidator(token=settings.hf_token),
            repository=SubmissionRecordRepository(root=constants.LEADERBOARD_SUBMISSIONS_ROOT),
            template_renderer=TemplateRenderer(),
        )

    def discover_submission_prs(self) -> DiscoverResult:
        include: list[DiscoverMatrixItem] = []
        for discussion in self._discussion_client.list_open_submission_prs():
            hf_pr_id = int(discussion.num)
            details = self._discussion_client.get_discussion_details(hf_pr_id)
            head_sha = self._discussion_client.latest_head_sha(details)
            if not head_sha:
                continue
            include.append(DiscoverMatrixItem(hf_pr_id=hf_pr_id, hf_head_sha=head_sha))

        return DiscoverResult(count=len(include), matrix=DiscoverMatrix(include=include))

    def run_discover_hf_submission_prs(self) -> None:
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
        print(f"Discovered {count} matching open HF submission PR(s)")
        print(f"{constants.DISCOVER_OUTPUT_COUNT_KEY}={count}")
        print(f"{constants.DISCOVER_OUTPUT_MATRIX_KEY}={matrix_json}")

    def run_hf_single_pr(self, hf_pr_id: int, expected_head_sha: str | None = None, merge_accepted: bool = True) -> None:
        now_utc = self._now_utc_z()
        key = (self._settings.leaderboard_hf_repo, hf_pr_id)
        existing = self._repository.load_existing_records()
        previous = existing.get(key)

        details, start_sha = self._load_single_pr_context(hf_pr_id=hf_pr_id, expected_head_sha=expected_head_sha)
        if details is None or start_sha is None:
            return

        initial_head_sha = previous.initial_head_sha if previous and previous.initial_head_sha else start_sha
        if previous and initial_head_sha != start_sha:
            self._reject_mutated_pr(
                previous=previous,
                details=details,
                hf_pr_id=hf_pr_id,
                now_utc=now_utc,
                initial_head_sha=initial_head_sha,
                start_sha=start_sha,
            )
            return

        self._discussion_client.upsert_status_comment(
            hf_pr_id=hf_pr_id,
            status=SyncCommentStatus.PROCESSING,
            message=f"Processing started for head SHA `{start_sha}`.",
        )

        candidate = SubmissionRecord(
            submission_id=previous.submission_id if previous else self._submission_id(self._settings.leaderboard_hf_repo, hf_pr_id),
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
        new_status, result_reason = self._apply_stale_guard(
            hf_pr_id=hf_pr_id,
            start_sha=start_sha,
            status=new_status,
            reason=result_reason,
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
        self._repository.persist_submission_record(previous, updated)

        self._publish_final_status(
            hf_pr_id=hf_pr_id,
            start_sha=start_sha,
            status=new_status,
            reason=result_reason,
            merge_accepted=merge_accepted,
            submission_id=updated.submission_id,
        )

    def build_submissions_json(self, output_path: Path | None = None) -> Path:
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

    def _validate_candidate(self, candidate: SubmissionRecord) -> tuple[SubmissionStatus, str | None]:
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
        if status != SubmissionStatus.ACCEPTED:
            return status, reason

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
        if status == SubmissionStatus.ACCEPTED:
            self._discussion_client.upsert_status_comment(
                hf_pr_id=hf_pr_id,
                status=SyncCommentStatus.PASS,
                message=f"Validation passed for head SHA `{start_sha}`.",
            )
            if merge_accepted:
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

    @staticmethod
    def _classify_validation_failure(exc: SubmissionHFValidationError) -> SubmissionStatus:
        """Classify fail-closed/network-style validation failures as pending for retry."""
        message = str(exc).lower()
        if any(marker in message for marker in constants.HF_SYNC_TRANSIENT_ERROR_MARKERS):
            return SubmissionStatus.PENDING
        return SubmissionStatus.REJECTED

    @staticmethod
    def _now_utc_z() -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _sanitize_repo(repo: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")

    @classmethod
    def _submission_id(cls, repo: str, hf_pr_id: int) -> str:
        return f"{cls._sanitize_repo(repo)}-pr-{hf_pr_id}"


def discover_submission_prs(hf_repo: str, token: str) -> DiscoverResult:
    """Discover open submission PRs and return workflow-ready structured data."""
    settings = HFSyncSettings.model_validate(
        {
            "LEADERBOARD_HF_REPO": hf_repo,
            "HF_TOKEN": token,
            "GITHUB_OUTPUT": None,
        }
    )
    return SubmissionSyncOrchestrator.from_settings(settings=settings).discover_submission_prs()


def run_discover_hf_submission_prs() -> None:
    """Discover open submission HF PRs and emit matrix/count outputs for CI."""
    settings = get_hf_sync_settings()
    SubmissionSyncOrchestrator.from_settings(settings).run_discover_hf_submission_prs()


def run_hf_single_pr(hf_pr_id: int, expected_head_sha: str | None = None, merge_accepted: bool = True) -> None:
    """Process exactly one HF dataset PR and write/update its control-plane record."""
    settings = get_hf_sync_settings()
    SubmissionSyncOrchestrator.from_settings(settings).run_hf_single_pr(
        hf_pr_id=hf_pr_id,
        expected_head_sha=expected_head_sha,
        merge_accepted=merge_accepted,
    )


def build_submissions_json(output_path: Path | None = None) -> Path:
    """Build deterministic submissions.json from control-plane records."""
    destination = output_path or Path(".tmp-gh-pages/submissions.json")
    records = SubmissionRecordRepository(root=constants.LEADERBOARD_SUBMISSIONS_ROOT).read_all_records()
    output = SubmissionsManfiest(
        generated_at_utc=SubmissionSyncOrchestrator._now_utc_z(),
        count=len(records),
        records=records,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(f"{output.model_dump_json(indent=2)}\n", encoding="utf-8")
    LOGGER.info("Built submissions JSON at %s with %s record(s)", destination, len(records))
    return destination
