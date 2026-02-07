"""Leaderboard publish invoke tasks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from invoke import task

from dev.leaderboard.publish import publish_from_processed

if TYPE_CHECKING:
    from invoke.context import Context


@task(name="publish-from-processed")
def publish_from_processed_task(
    _ctx: Context,
    gh_pages_root: str,
    processed_dir: str = "leaderboard/data/submissions/processed",
    staging_dir: str = ".tmp/leaderboard-publish-staging",
    generation_id: str = "",
    generated_at_utc: str = "",
    dry_run: bool = False,
) -> None:
    """Generate and publish leaderboard files from processed submission records.

    Args:
        gh_pages_root: Path to a local gh-pages worktree checkout.
        processed_dir: Directory containing processed submission JSON records.
        staging_dir: Temporary staging directory for generated publish artifacts.
        generation_id: Optional generation id override.
        generated_at_utc: Optional RFC3339 UTC timestamp override.
        dry_run: Generate/validate only, skip gh-pages publish swap.
    """
    manifest = publish_from_processed(
        gh_pages_root=Path(gh_pages_root),
        processed_dir=Path(processed_dir),
        staging_dir=Path(staging_dir),
        generation_id=generation_id or None,
        generated_at_utc=generated_at_utc or None,
        dry_run=dry_run,
    )
    print(f"generation_id={manifest.generation_id}")
    print(f"full_file={manifest.full_file}")
    print(f"hard_file={manifest.hard_file}")
