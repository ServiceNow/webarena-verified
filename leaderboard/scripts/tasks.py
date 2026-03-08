from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from invoke.context import Context  # noqa: TC002
from invoke.tasks import task

from leaderboard.scripts.config import get_config
from leaderboard.scripts.leaderboard_builder import LeaderboardBuilder
from leaderboard.scripts.submission_handler import sync_submissions
from webarena_verified.submission.config import SubmissionFlowConfig

logger = logging.getLogger(__name__)


@task(name="rebuild-leaderboard")
def rebuild_leaderboard(
    _ctx: Context,
    repo_root: str = ".",
    dry_run: bool = False,
) -> None:
    """Invoke task: rebuild leaderboard artifacts and print paths.

    Re-ranks and rewrites all leaderboard generation artifacts in place,
    then prints the generation ID and file paths to stdout for consumption
    by CI scripts.

    Usage::

        invoke rebuild-leaderboard --repo-root /path/to/checkout
    """
    root = Path(repo_root)

    if dry_run:
        logger.info("Rebuild skipped (dry_run=True)")
        print("generation_id=")
        print("latest=")
        print("full=")
        print("hard=")
        print("dry_run=true")
        return

    builder = LeaderboardBuilder(SubmissionFlowConfig())
    latest_path, full_path, hard_path = builder.rebuild_leaderboard(repo_root=root)
    latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))

    logger.info("Rebuild complete: generation_id=%s dry_run=%s", latest_payload["generation_id"], dry_run)
    print(f"generation_id={latest_payload['generation_id']}")
    print(f"latest={latest_path}")
    print(f"full={full_path}")
    print(f"hard={hard_path}")
    print(f"dry_run={str(dry_run).lower()}")


@task(name="hf-sync-submissions")
def hf_sync_submissions(
    _ctx: Context,
    hf_repo: str,
    hf_token: str = "",
    repo_root: str = ".",
    max_recent_refs: int = 50,
) -> None:
    """Invoke task: batch-sync recent HF PRs into the leaderboard.

    Pulls the most recent HF dataset PR refs and ingests each one.
    Prints the count and list of processed PR numbers.

    Usage::

        invoke hf-sync-submissions --hf-repo AmineHA/WebArena-Verified
    """
    hf_token = hf_token or os.environ.get("HF_TOKEN", "")

    logger.info("Starting HF sync: hf_repo=%s max_recent_refs=%d", hf_repo, max_recent_refs)
    submission_ids = sync_submissions(
        repo_root=Path(repo_root),
        hf_repo=hf_repo,
        hf_token=hf_token,
        max_recent_refs=max_recent_refs,
    )
    logger.info("HF sync complete: synced %d submissions", len(submission_ids))
    print(f"synced_count={len(submission_ids)}")
    print(f"synced_submission_ids={submission_ids}")


@task(name="site-resolve-manifest-url")
def site_resolve_manifest_url(
    _ctx: Context,
    manifest_url_override: str = "",
    configured_manifest_url: str = "",
) -> None:
    """Invoke task: resolve the ``latest.json`` manifest URL.

    Prints the effective manifest URL to stdout, choosing in priority order:
    explicit override → configured URL → built-in default pointing to the
    ``leaderboard-submissions`` branch on GitHub.

    Used by the docs-site build to embed the correct leaderboard data URL.

    Usage::

        invoke site-resolve-manifest-url --manifest-url-override https://...
    """
    override = manifest_url_override.strip()
    if override:
        manifest_url = override
    else:
        configured = configured_manifest_url.strip()
        manifest_url = configured if configured else get_config().default_manifest_url

    logger.info("Resolved manifest URL: %s", manifest_url)
    print(manifest_url)
