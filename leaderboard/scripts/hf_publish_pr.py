from __future__ import annotations

import fnmatch
import subprocess
from typing import TYPE_CHECKING

from leaderboard.scripts.publish import rebuild_leaderboard_artifacts

if TYPE_CHECKING:
    from pathlib import Path

_ALLOWLISTED_PATH_PATTERNS = (
    "leaderboard/latest.json",
    "leaderboard/generations/*/full.json",
    "leaderboard/generations/*/hard.json",
)


def _run_git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        text=True,
        capture_output=True,
    )


def _overlay_pr_head_data(*, repo_root: Path, pr_number: int) -> str:
    _run_git(repo_root, "fetch", "--no-tags", "--depth=1", "origin", f"pull/{pr_number}/head")
    pr_head_sha = _run_git(repo_root, "rev-parse", "FETCH_HEAD").stdout.strip()

    _run_git(repo_root, "checkout", pr_head_sha, "--", "leaderboard", check=False)
    for pattern in (
        "leaderboard/latest.json",
        "leaderboard/generations/*/full.json",
        "leaderboard/generations/*/hard.json",
    ):
        for path in sorted(repo_root.glob(pattern)):
            if path.is_file():
                _run_git(repo_root, "checkout", pr_head_sha, "--", str(path.relative_to(repo_root)), check=False)

    return pr_head_sha


def _path_is_allowlisted(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in _ALLOWLISTED_PATH_PATTERNS)


def _enforce_allowlisted_changed_paths(*, repo_root: Path, base_branch: str, pr_head_sha: str) -> None:
    diff_range = f"origin/{base_branch}...{pr_head_sha}"
    changed_files = _run_git(repo_root, "diff", "--name-only", diff_range).stdout.splitlines()
    for file_path in changed_files:
        if file_path and not _path_is_allowlisted(file_path):
            raise ValueError(f"Non-allowlisted file changed: {file_path}")


def _ensure_rebuild_is_idempotent(*, repo_root: Path) -> None:
    changed_files = _run_git(repo_root, "diff", "--name-only").stdout.splitlines()
    changed_files = [path for path in changed_files if path]
    if changed_files:
        changed = ", ".join(changed_files)
        raise ValueError(
            "Leaderboard rebuild is not reproducible for the current PR head. "
            f"Rebuild produced additional diff(s): {changed}"
        )


def _run_hf_publish_pr_gate(
    *,
    repo_root: Path,
    pr_number: int,
    base_branch: str,
) -> str:
    pr_head_sha = _overlay_pr_head_data(repo_root=repo_root, pr_number=pr_number)

    rebuild_leaderboard_artifacts(
        branch_root=repo_root,
        dry_run=False,
    )
    _ensure_rebuild_is_idempotent(repo_root=repo_root)

    _enforce_allowlisted_changed_paths(repo_root=repo_root, base_branch=base_branch, pr_head_sha=pr_head_sha)
    return pr_head_sha
