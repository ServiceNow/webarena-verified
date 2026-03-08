from __future__ import annotations

import json
from pathlib import Path

from webarena_verified.submission.config import SubmissionFlowConfig
from webarena_verified.submission.leaderboard_builder import LeaderboardBuilder


def rebuild_leaderboard_artifacts(
    *,
    branch_root: Path,
    dry_run: bool = False,
) -> dict[str, str]:
    if dry_run:
        return {"mode": "dry_run"}

    builder = LeaderboardBuilder(SubmissionFlowConfig())
    latest_path, full_path, hard_path = builder.rebuild_leaderboard(repo_root=branch_root)
    latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
    return {
        "generation_id": latest_payload["generation_id"],
        "latest": str(latest_path),
        "full": str(full_path),
        "hard": str(hard_path),
    }
