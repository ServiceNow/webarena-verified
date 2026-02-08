"""Invoke entry points for leaderboard sync workflow commands."""

from __future__ import annotations

import logging

from invoke import task

LOGGER = logging.getLogger(__name__)


@task(name="resolve-hf-config")
def resolve_hf_config(_ctx) -> None:
    """Resolve HF sync configuration inputs.

    Placeholder entry point; implementation pending.
    """
    LOGGER.warning("resolve-hf-config is not implemented yet")


@task(name="hf-sync")
def hf_sync(_ctx) -> None:
    """Sync and process HF submission PRs.

    Placeholder entry point; implementation pending.
    """
    LOGGER.warning("hf-sync is not implemented yet")


@task(name="commit-control-plane")
def commit_control_plane(_ctx) -> None:
    """Commit and push control-plane submission updates.

    Placeholder entry point; implementation pending.
    """
    LOGGER.warning("commit-control-plane is not implemented yet")


@task(name="prepare-gh-pages-worktree")
def prepare_gh_pages_worktree(_ctx) -> None:
    """Prepare gh-pages worktree for publication.

    Placeholder entry point; implementation pending.
    """
    LOGGER.warning("prepare-gh-pages-worktree is not implemented yet")


@task(name="publish-from-processed")
def publish_from_processed(_ctx) -> None:
    """Publish leaderboard artifacts from processed submissions.

    Placeholder entry point; implementation pending.
    """
    LOGGER.warning("publish-from-processed is not implemented yet")


@task(name="write-sync-summary")
def write_sync_summary(_ctx) -> None:
    """Write workflow sync summary output.

    Placeholder entry point; implementation pending.
    """
    LOGGER.warning("write-sync-summary is not implemented yet")
