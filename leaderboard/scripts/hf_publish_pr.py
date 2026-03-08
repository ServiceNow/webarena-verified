from __future__ import annotations

import fnmatch
import json
import subprocess
from typing import TYPE_CHECKING

from leaderboard.scripts.publish import publish_from_canonical

if TYPE_CHECKING:
    from pathlib import Path

_ALLOWLISTED_PATH_PATTERNS = (
    "submission_control/*",
    "submissions/*",
    "leaderboard_manifest.json",
    "leaderboard_full.*.json",
    "leaderboard_hard.*.json",
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

    _run_git(repo_root, "checkout", pr_head_sha, "--", "submission_control", "submissions", check=False)
    for pattern in ("leaderboard_manifest.json", "leaderboard_full.*.json", "leaderboard_hard.*.json"):
        for path in sorted(repo_root.glob(pattern)):
            if path.is_file():
                _run_git(repo_root, "checkout", pr_head_sha, "--", path.name, check=False)

    return pr_head_sha


def _path_is_allowlisted(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in _ALLOWLISTED_PATH_PATTERNS)


def _enforce_allowlisted_changed_paths(*, repo_root: Path, base_branch: str, pr_head_sha: str) -> None:
    diff_range = f"origin/{base_branch}...{pr_head_sha}"
    changed_files = _run_git(repo_root, "diff", "--name-only", diff_range).stdout.splitlines()
    for file_path in changed_files:
        if file_path and not _path_is_allowlisted(file_path):
            raise ValueError(f"Non-allowlisted file changed: {file_path}")


def _verify_latest_accepted_head_sha_linkage(*, repo_root: Path) -> None:
    control_root = repo_root / "submission_control"
    canonical_root = repo_root / "submissions"
    if not control_root.exists() or not canonical_root.exists():
        return

    for canonical_path in canonical_root.glob("*.json"):
        canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
        submission_id = canonical.get("submission_id")
        control_path = control_root / f"{submission_id}.json"
        if not control_path.exists():
            continue
        control = json.loads(control_path.read_text(encoding="utf-8"))
        if canonical.get("hf_head_sha") != control.get("hf_head_sha"):
            raise ValueError(
                "Canonical/control head SHA mismatch for submission "
                f"{submission_id}: {canonical.get('hf_head_sha')} != {control.get('hf_head_sha')}"
            )


def _run_hf_publish_pr_gate(
    *,
    repo_root: Path,
    pr_number: int,
    base_branch: str,
    max_canonical_records: int,
) -> str:
    pr_head_sha = _overlay_pr_head_data(repo_root=repo_root, pr_number=pr_number)

    publish_from_canonical(
        branch_root=repo_root,
        canonical_dir=repo_root / "submissions",
        staging_dir=repo_root / ".tmp/leaderboard-staging",
        max_canonical_records=max_canonical_records,
        dry_run=True,
    )

    _enforce_allowlisted_changed_paths(repo_root=repo_root, base_branch=base_branch, pr_head_sha=pr_head_sha)
    _verify_latest_accepted_head_sha_linkage(repo_root=repo_root)
    return pr_head_sha
