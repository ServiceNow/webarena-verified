"""Invoke entry points for leaderboard sync workflow commands."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from invoke import task

from dev.leaderboard.utils.hf_sync import build_submissions_json, run_discover_hf_submission_prs, run_hf_single_pr, run_hf_sync

LOGGER = logging.getLogger(__name__)


@task(name="resolve-hf-config")
def resolve_hf_config(_ctx) -> None:
    """Resolve HF sync configuration inputs.

    Placeholder entry point; implementation pending.
    """
    LOGGER.warning("resolve-hf-config is not implemented yet")


@task(name="hf-sync")
def hf_sync(_ctx) -> None:
    """Sync and process open HF dataset pull requests into control-plane records."""
    run_hf_sync()


@task(name="discover-hf-prs")
def discover_hf_prs(_ctx) -> None:
    """Discover open HF submission PRs and emit workflow outputs."""
    run_discover_hf_submission_prs()


def _parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


@task(name="hf-handle-pr")
def hf_handle_pr(_ctx, hf_pr_id: int, expected_head_sha: str = "", merge_accepted: str | bool = True) -> None:
    """Process one HF dataset PR by ID."""
    run_hf_single_pr(
        hf_pr_id=int(hf_pr_id),
        expected_head_sha=expected_head_sha or None,
        merge_accepted=_parse_bool(merge_accepted),
    )


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)


@task(name="commit-control-plane")
def commit_control_plane(_ctx, hf_pr_id: int = 0) -> None:
    """Commit/push submission control-plane changes if needed."""
    target = Path("leaderboard/data/submissions")
    if not target.exists():
        LOGGER.info("No control-plane directory found; skipping commit")
        return
    status = _run(["git", "status", "--porcelain", "--", str(target)])
    if not status.stdout.strip():
        LOGGER.info("No submission control-plane changes to commit")
        return

    _run(["git", "add", str(target)])
    message = f"leaderboard: process HF PR #{hf_pr_id}" if hf_pr_id else "leaderboard: update submission control-plane"
    _run(["git", "commit", "-m", message])
    _run(["git", "push", "origin", "HEAD"])
    LOGGER.info("Committed control-plane changes")


@task(name="prepare-gh-pages-worktree")
def prepare_gh_pages_worktree(_ctx, worktree_path: str = "gh-pages-worktree") -> None:
    """Prepare local gh-pages worktree."""
    worktree = Path(worktree_path)
    if worktree.exists():
        shutil.rmtree(worktree)
    _run(["git", "fetch", "origin", "gh-pages"])
    _run(["git", "worktree", "add", worktree_path, "origin/gh-pages"])
    LOGGER.info("Prepared gh-pages worktree at %s", worktree_path)


@task(name="build-gh-pages-json")
def build_gh_pages_json(_ctx, output_path: str = ".tmp-gh-pages/submissions.json") -> None:
    """Build submissions JSON artifact for gh-pages publishing."""
    build_submissions_json(output_path=Path(output_path))


@task(name="publish-from-processed")
def publish_from_processed(
    _ctx,
    hf_pr_id: int = 0,
    source_json: str = ".tmp-gh-pages/submissions.json",
    worktree_path: str = "gh-pages-worktree",
) -> None:
    """Publish submissions JSON to gh-pages if content changed."""
    source = Path(source_json)
    if not source.exists():
        raise RuntimeError(f"Source JSON does not exist: {source}")

    worktree = Path(worktree_path)
    if not worktree.exists():
        prepare_gh_pages_worktree(_ctx, worktree_path=worktree_path)

    destination = worktree / "submissions.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    status = _run(["git", "status", "--porcelain", "--", "submissions.json"], cwd=worktree)
    if not status.stdout.strip():
        LOGGER.info("No gh-pages changes to publish")
        return

    _run(["git", "add", "submissions.json"], cwd=worktree)
    message = f"leaderboard: publish HF PR #{hf_pr_id}" if hf_pr_id else "leaderboard: publish submissions.json"
    _run(["git", "commit", "-m", message], cwd=worktree)
    _run(["git", "push", "origin", "HEAD:gh-pages"], cwd=worktree)
    LOGGER.info("Published submissions.json to gh-pages")


@task(name="write-sync-summary")
def write_sync_summary(_ctx) -> None:
    """Write workflow sync summary output.

    Placeholder entry point; implementation pending.
    """
    LOGGER.warning("write-sync-summary is not implemented yet")
