"""Invoke entry points for leaderboard submission workflows."""

from __future__ import annotations

import os
from pathlib import Path

from invoke.tasks import task

from leaderboard.scripts.hf_ingest import ingest_hf_submission
from leaderboard.scripts.hf_reconcile import sync_submissions
from leaderboard.scripts.publish import rebuild_leaderboard_artifacts
from leaderboard.scripts.site_build_flow import _resolve_manifest_url


@task(name="rebuild-leaderboard")
def rebuild_leaderboard(
    _ctx,
    repo_root: str = ".",
    dry_run: bool = False,
) -> None:
    root = Path(repo_root)
    result = rebuild_leaderboard_artifacts(
        branch_root=root,
        dry_run=dry_run,
    )

    print(f"generation_id={result.get('generation_id', '')}")
    print(f"latest={result.get('latest', '')}")
    print(f"full={result.get('full', '')}")
    print(f"hard={result.get('hard', '')}")
    print(f"dry_run={str(dry_run).lower()}")


@task(name="hf-ingest")
def hf_ingest(
    _ctx,
    event_path: str,
    hf_repo: str,
    hf_token: str = "",
    evaluator_version: str = "",
) -> None:
    hf_token = hf_token or os.environ.get("HF_TOKEN", "")

    result = ingest_hf_submission(
        repo_root=Path.cwd(),
        event_path=Path(event_path),
        hf_repo_expected=hf_repo,
        hf_token=hf_token,
        evaluator_version=evaluator_version,
    )
    print(result.model_dump_json(indent=2))


@task(name="hf-sync-submissions")
def hf_sync_submissions(
    _ctx,
    hf_repo: str,
    hf_token: str = "",
    evaluator_version: str = "",
    repo_root: str = ".",
    max_recent_refs: int = 50,
) -> None:
    hf_token = hf_token or os.environ.get("HF_TOKEN", "")

    submission_ids = sync_submissions(
        repo_root=Path(repo_root),
        hf_repo=hf_repo,
        hf_token=hf_token,
        evaluator_version=evaluator_version,
        max_recent_refs=max_recent_refs,
    )
    print(f"synced_count={len(submission_ids)}")
    print(f"synced_submission_ids={submission_ids}")


@task(name="site-resolve-manifest-url")
def site_resolve_manifest_url(
    _ctx,
    manifest_url_override: str = "",
    configured_manifest_url: str = "",
) -> None:
    manifest_url = _resolve_manifest_url(
        manifest_url_override=manifest_url_override,
        configured_manifest_url=configured_manifest_url,
    )
    print(manifest_url)
