from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _run_git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        text=True,
        capture_output=True,
    )


def _commit_and_push_rebuild(*, repo_root: Path, target_branch: str) -> tuple[bool, str | None]:
    _run_git(repo_root, "add", "-A", "submissions", "leaderboard_manifest.json")

    generation_files = [path.name for path in sorted(repo_root.glob("leaderboard_full.*.json"))]
    generation_files.extend(path.name for path in sorted(repo_root.glob("leaderboard_hard.*.json")))
    if generation_files:
        _run_git(repo_root, "add", "-A", *generation_files)

    staged_diff = _run_git(repo_root, "diff", "--cached", "--quiet", check=False)
    if staged_diff.returncode == 0:
        return False, None

    manifest_path = repo_root / "leaderboard_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    generation_id = str(manifest.get("generation_id", "")).strip()
    if not generation_id:
        raise ValueError("leaderboard_manifest.json missing generation_id")

    _run_git(repo_root, "commit", "-m", f"Rebuild leaderboard generation {generation_id}")

    for _attempt in (1, 2, 3):
        push = _run_git(repo_root, "push", "origin", f"HEAD:{target_branch}", check=False)
        if push.returncode == 0:
            return True, generation_id
        _run_git(repo_root, "pull", "--rebase", "origin", target_branch)

    raise RuntimeError("Failed to push rebuild updates after retries")
