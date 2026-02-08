"""Invoke tasks for leaderboard automation workflows."""

from __future__ import annotations

import logging
from pathlib import Path

from invoke import task
from invoke.exceptions import Exit

from dev.leaderboard.models import SubmissionPRContext
from dev.leaderboard.submission_pr_validator import (
    SubmissionPRValidationError,
    _build_failure_report,
    validate_submission_pr,
)


def _configure_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )


@task(
    name="submission-validate-pr",
    help={
        "base_sha": "Base commit SHA for PR diff.",
        "head_sha": "Head commit SHA for PR diff.",
        "repo": "GitHub repo in owner/name format.",
        "actor": "GitHub actor login.",
        "pr_number": "GitHub PR number.",
        "pr_title": "GitHub PR title.",
        "github_token": "GitHub token used for API calls.",
        "report_file": "Optional markdown report output path.",
        "log_level": "Python log level (DEBUG, INFO, WARNING, ERROR).",
    },
)
def submission_validate_pr(
    _ctx,
    base_sha: str,
    head_sha: str,
    repo: str,
    actor: str,
    pr_number: int,
    pr_title: str,
    github_token: str,
    report_file: str | None = None,
    log_level: str = "INFO",
) -> None:
    """Validate leaderboard submission PR for CI/automation."""
    _configure_logging(log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting submission PR validation task")
    logger.info("Context: repo=%s pr=%s actor=%s", repo, pr_number, actor)

    context = SubmissionPRContext(
        repo_root=Path.cwd(),
        base_sha=base_sha,
        head_sha=head_sha,
        repo=repo,
        actor=actor,
        pr_number=pr_number,
        pr_title=pr_title,
        github_token=github_token,
    )

    try:
        validate_submission_pr(context)
    except SubmissionPRValidationError as exc:
        message = str(exc)
        logger.error("Submission PR validation failed: %s", message)
        report = _build_failure_report(message)
        print(report)
        if report_file:
            Path(report_file).write_text(report, encoding="utf-8")
            logger.info("Wrote failure report: %s", report_file)
        raise Exit(code=1) from exc

    success_report = "## Submission PR Validation Passed\n\nAll submission PR checks passed.\n"
    print(success_report)
    if report_file:
        Path(report_file).write_text(success_report, encoding="utf-8")
        logger.info("Wrote success report: %s", report_file)
    logger.info("Submission PR validation passed")
