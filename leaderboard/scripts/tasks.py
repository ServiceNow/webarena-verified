"""Invoke entry points for leaderboard submission workflows."""

from __future__ import annotations

import os
from pathlib import Path

from invoke import task

from leaderboard.scripts.hf_ingest import ingest_hf_submission
from leaderboard.scripts.publish import publish_from_canonical


@task(name="rebuild-canonical")
def rebuild_canonical(
    _ctx,
    repo_root: str = ".",
    canonical_dir: str = "submissions",
    staging_dir: str = ".tmp/leaderboard-staging",
    max_canonical_records: int = 100,
    generation_id: str = "",
    generated_at_utc: str = "",
    dry_run: bool = False,
) -> None:
    """Rebuild leaderboard artifacts from canonical submission records."""
    root = Path(repo_root)
    canonical_root = root / canonical_dir
    canonical_before = len(list(canonical_root.glob("*.json"))) if canonical_root.exists() else 0

    manifest = publish_from_canonical(
        branch_root=root,
        canonical_dir=canonical_root,
        staging_dir=root / staging_dir,
        max_canonical_records=max_canonical_records,
        generation_id=generation_id or None,
        generated_at_utc=generated_at_utc or None,
        dry_run=dry_run,
    )

    canonical_after = len(list(canonical_root.glob("*.json"))) if canonical_root.exists() else 0
    print(f"generation_id={manifest.generation_id}")
    print(f"full_file={manifest.full_file}")
    print(f"hard_file={manifest.hard_file}")
    print(f"canonical_count_before={canonical_before}")
    print(f"canonical_count_after={canonical_after}")
    print(f"dry_run={str(dry_run).lower()}")


@task(name="hf-ingest")
def hf_ingest(
    _ctx,
    event_path: str,
    hf_repo: str,
    github_repo: str = "",
    hf_token: str = "",
    evaluator_version: str = "",
) -> None:
    github_repo = github_repo or os.environ.get("GITHUB_REPOSITORY", "")
    hf_token = hf_token or os.environ.get("HF_TOKEN", "")
    if not github_repo:
        raise RuntimeError("github_repo is required (arg or GITHUB_REPOSITORY)")

    result = ingest_hf_submission(
        repo_root=Path.cwd(),
        event_path=Path(event_path),
        github_repo=github_repo,
        hf_repo_canonical=hf_repo,
        hf_token=hf_token,
        evaluator_version=evaluator_version,
    )
    print(result.model_dump_json(indent=2))
