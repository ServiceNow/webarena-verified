"""Submission PR validator for leaderboard CI."""

from __future__ import annotations

import datetime as dt
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from jinja2 import Template

from dev.leaderboard.constants import (
    SUBMISSION_PENDING_DIR_PREFIX,
    SUBMISSION_PR_FAILURE_TEMPLATE_FILE,
    SUBMISSION_PR_TITLE_PREFIX,
)
from dev.leaderboard.hf_validator import SubmissionHFValidationError, validate_hf_submission_record
from dev.leaderboard.models import ChangedFile, SubmissionPRContext, SubmissionRecord, SubmissionStatus
from dev.leaderboard.utils import http_get_json

LOGGER = logging.getLogger(__name__)


class SubmissionPRValidationError(Exception):
    """Raised when submission PR validation fails."""


def _parse_iso_utc(value: str) -> dt.datetime:
    """Parse ISO timestamp with optional trailing Z into UTC aware datetime."""
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def _run_git_diff(base_sha: str, head_sha: str, repo_root: Path) -> list[ChangedFile]:
    """Return list of changed files for PR diff."""
    LOGGER.info("Computing git diff for range %s..%s", base_sha, head_sha)
    cmd = ["git", "diff", "--name-status", "--no-renames", f"{base_sha}..{head_sha}"]
    result = subprocess.run(cmd, cwd=repo_root, check=True, capture_output=True, text=True)

    changed_files: list[ChangedFile] = []
    for raw_line in result.stdout.splitlines():
        if not raw_line.strip():
            continue
        status, path = raw_line.split("\t", maxsplit=1)
        changed_files.append(ChangedFile(status=status.strip(), path=path.strip()))
    LOGGER.info("Detected %s changed file(s) in PR diff", len(changed_files))
    return changed_files


def _validate_changed_files(changed_files: list[ChangedFile]) -> str:
    """Validate file scope and exactly-one-record rule."""
    LOGGER.info("Validating changed-file scope and cardinality")
    if not changed_files:
        raise SubmissionPRValidationError("No files changed in PR diff")

    invalid_scope = [cf.path for cf in changed_files if not cf.path.startswith(SUBMISSION_PENDING_DIR_PREFIX)]
    if invalid_scope:
        joined = ", ".join(sorted(invalid_scope))
        raise SubmissionPRValidationError(
            f"Submission PRs may only change control records under {SUBMISSION_PENDING_DIR_PREFIX}. "
            f"Invalid paths: {joined}"
        )

    json_files = [cf for cf in changed_files if cf.path.endswith(".json")]
    if len(json_files) != 1 or len(changed_files) != 1:
        raise SubmissionPRValidationError(
            "Submission PRs must change exactly one submission control JSON and no other files"
        )

    changed = json_files[0]
    if changed.status not in {"A", "M"}:
        raise SubmissionPRValidationError(
            f"Submission control JSON must be added or modified, got git status '{changed.status}'"
        )

    LOGGER.info("Validated changed control file: %s", changed.path)
    return changed.path


def _load_submission_record(repo_root: Path, control_path: str) -> SubmissionRecord:
    """Load and validate control record JSON from repository file."""
    LOGGER.info("Loading submission control record from %s", control_path)
    control_file = repo_root / control_path
    if not control_file.exists():
        raise SubmissionPRValidationError(f"Submission control file is missing: {control_path}")

    payload = json.loads(control_file.read_text(encoding="utf-8"))
    try:
        record = SubmissionRecord.model_validate(payload)
    except Exception as exc:
        raise SubmissionPRValidationError(f"Invalid submission record schema in {control_path}: {exc}") from exc

    file_submission_id = Path(control_path).stem
    if record.submission_id != file_submission_id:
        raise SubmissionPRValidationError(
            "submission_id mismatch: file name and submission record must match "
            f"(file='{file_submission_id}', record='{record.submission_id}')"
        )

    if record.status != SubmissionStatus.PENDING:
        raise SubmissionPRValidationError("Path/status invariant failed: pending/<id>.json must have status='pending'")

    LOGGER.info("Submission control record validated for submission_id=%s", record.submission_id)
    return record


def _list_all_repo_pulls(repo: str, token: str) -> list[dict[str, Any]]:
    """List pull requests from GitHub REST API with pagination."""
    LOGGER.info("Listing all pull requests for repository %s", repo)
    pulls: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/pulls?state=all&per_page=100&page={page}"
        data = http_get_json(url, token=token)
        if not isinstance(data, list):
            raise SubmissionPRValidationError("Unexpected GitHub API response while listing PRs")

        pulls.extend(data)
        if len(data) < 100:
            break
        page += 1
    LOGGER.info("Fetched %s pull requests from GitHub", len(pulls))
    return pulls


def _list_pull_files(repo: str, pr_number: int, token: str) -> list[str]:
    """List changed file paths for a GitHub PR."""
    LOGGER.debug("Listing changed files for PR #%s", pr_number)
    file_paths: list[str] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files?per_page=100&page={page}"
        data = http_get_json(url, token=token)
        if not isinstance(data, list):
            raise SubmissionPRValidationError(f"Unexpected GitHub API response while listing PR #{pr_number} files")

        for item in data:
            filename = item.get("filename")
            if isinstance(filename, str):
                file_paths.append(filename)
        if len(data) < 100:
            break
        page += 1
    LOGGER.debug("PR #%s has %s changed path(s)", pr_number, len(file_paths))
    return file_paths


def _is_submission_pr(repo: str, pr_number: int, token: str) -> bool:
    """Classify PR as submission PR based on changed file scope."""
    paths = _list_pull_files(repo, pr_number, token)
    is_submission = any(path.startswith(SUBMISSION_PENDING_DIR_PREFIX) for path in paths)
    LOGGER.debug("PR #%s classified as submission_pr=%s", pr_number, is_submission)
    return is_submission


def _enforce_github_rate_limits(
    repo: str,
    actor: str,
    current_pr_number: int,
    token: str,
    now_utc: dt.datetime,
) -> None:
    """Enforce author rate limits using GitHub API (fail closed)."""
    LOGGER.info("Evaluating GitHub fairness/rate-limit rules for actor=%s", actor)
    try:
        pulls = _list_all_repo_pulls(repo, token)
    except Exception as exc:
        raise SubmissionPRValidationError(
            f"Unable to evaluate GitHub actor rate limits due to API error (fail-closed): {exc}"
        ) from exc

    actor_prs = [pr for pr in pulls if pr.get("user", {}).get("login") == actor]
    LOGGER.info("Found %s PR(s) authored by %s", len(actor_prs), actor)
    actor_submission_prs = []
    for pr in actor_prs:
        number = pr.get("number")
        if not isinstance(number, int):
            continue
        try:
            if _is_submission_pr(repo, number, token):
                actor_submission_prs.append(pr)
        except Exception as exc:
            raise SubmissionPRValidationError(
                f"Unable to classify PR #{number} for submission rate limiting (fail-closed): {exc}"
            ) from exc

    open_submission_prs = [
        pr for pr in actor_submission_prs if pr.get("state") == "open" and pr.get("number") != current_pr_number
    ]
    if open_submission_prs:
        numbers = ", ".join(str(pr["number"]) for pr in open_submission_prs)
        raise SubmissionPRValidationError(
            f"Rate limit exceeded: actor already has an open submission PR (PR number(s): {numbers})"
        )

    window_start = now_utc - dt.timedelta(hours=24)
    recent_submission_prs = []
    for pr in actor_submission_prs:
        if pr.get("number") == current_pr_number:
            continue
        created_at = pr.get("created_at")
        if not created_at:
            continue
        created_dt = _parse_iso_utc(str(created_at))
        if created_dt >= window_start:
            recent_submission_prs.append(created_dt)

    if recent_submission_prs:
        next_allowed = max(recent_submission_prs) + dt.timedelta(hours=24)
        next_allowed_str = next_allowed.strftime("%Y-%m-%dT%H:%M:%SZ")
        raise SubmissionPRValidationError(
            "Rate limit exceeded: only one new submission PR is allowed per rolling 24h window. "
            f"Next allowed UTC timestamp: {next_allowed_str}"
        )
    LOGGER.info("GitHub fairness/rate-limit checks passed")


def validate_submission_pr(context: SubmissionPRContext, now_utc: dt.datetime | None = None) -> None:
    """Run full submission PR validation."""
    _ = now_utc
    LOGGER.info(
        "Starting submission PR validation (repo=%s, pr_number=%s, actor=%s)",
        context.repo,
        context.pr_number,
        context.actor,
    )
    if not context.pr_title.startswith(SUBMISSION_PR_TITLE_PREFIX):
        raise SubmissionPRValidationError(
            f"PR title must start with exact prefix '{SUBMISSION_PR_TITLE_PREFIX}'"
        )

    changed_files = _run_git_diff(base_sha=context.base_sha, head_sha=context.head_sha, repo_root=context.repo_root)
    control_path = _validate_changed_files(changed_files)
    record = _load_submission_record(context.repo_root, control_path)

    try:
        validate_hf_submission_record(record)
    except SubmissionHFValidationError as exc:
        raise SubmissionPRValidationError(str(exc)) from exc
    LOGGER.info("Hugging Face-linked submission payload validation passed")

    # TODO: Re-enable fairness/rate-limit enforcement once we define robust handling for classification edge cases.
    # current_time = now_utc or dt.datetime.now(dt.UTC)
    # _enforce_github_rate_limits(
    #     repo=context.repo,
    #     actor=context.actor,
    #     current_pr_number=context.pr_number,
    #     token=context.github_token,
    #     now_utc=current_time,
    # )
    LOGGER.warning("Fairness/rate-limit enforcement is currently disabled (TODO)")
    LOGGER.info("Submission PR validation completed successfully")


def _build_failure_report(error_message: str) -> str:
    """Build markdown report for workflow summaries/comments."""
    templates_dir = Path(__file__).resolve().parent / "templates"
    template_path = templates_dir / SUBMISSION_PR_FAILURE_TEMPLATE_FILE
    LOGGER.info("Rendering failure report template: %s", template_path)
    template = Template(template_path.read_text(encoding="utf-8"))
    return template.render(pending_prefix=SUBMISSION_PENDING_DIR_PREFIX, error_message=error_message)
