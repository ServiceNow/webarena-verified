"""Invoke entry points for leaderboard submission workflows."""

from __future__ import annotations

import os
from pathlib import Path

from invoke.tasks import task

from leaderboard.scripts.hf_ingest import ingest_hf_submission
from leaderboard.scripts.hf_publish_pr import _run_hf_publish_pr_gate
from leaderboard.scripts.hf_reconcile import reconcile_hf_submissions
from leaderboard.scripts.publish import publish_from_canonical
from leaderboard.scripts.rebuild_flow import _commit_and_push_rebuild
from leaderboard.scripts.site_build_flow import _resolve_manifest_url
from leaderboard.scripts.smoke_flow import _run_leaderboard_smoke_check


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
    hf_token: str = "",
    evaluator_version: str = "",
) -> None:
    hf_token = hf_token or os.environ.get("HF_TOKEN", "")

    result = ingest_hf_submission(
        repo_root=Path.cwd(),
        event_path=Path(event_path),
        hf_repo_canonical=hf_repo,
        hf_token=hf_token,
        evaluator_version=evaluator_version,
    )
    print(result.model_dump_json(indent=2))


@task(name="hf-reconcile")
def hf_reconcile(
    _ctx,
    hf_repo: str,
    hf_token: str = "",
    evaluator_version: str = "",
    repo_root: str = ".",
    max_recent_refs: int = 50,
) -> None:
    hf_token = hf_token or os.environ.get("HF_TOKEN", "")

    submission_ids = reconcile_hf_submissions(
        repo_root=Path(repo_root),
        hf_repo=hf_repo,
        hf_token=hf_token,
        evaluator_version=evaluator_version,
        max_recent_refs=max_recent_refs,
    )
    print(f"reconciled_count={len(submission_ids)}")
    print(f"reconciled_submission_ids={submission_ids}")


@task(name="hf-publish-pr-gate")
def hf_publish_pr_gate(
    _ctx,
    pr_number: int,
    base_branch: str = "leaderboard-submissions",
    repo_root: str = ".",
    max_canonical_records: int = 100,
) -> None:
    pr_head_sha = _run_hf_publish_pr_gate(
        repo_root=Path(repo_root),
        pr_number=pr_number,
        base_branch=base_branch,
        max_canonical_records=max_canonical_records,
    )
    print(f"pr_number={pr_number}")
    print(f"pr_head_sha={pr_head_sha}")


@task(name="rebuild-and-push")
def rebuild_and_push(
    _ctx,
    target_branch: str,
    repo_root: str = ".",
    canonical_dir: str = "submissions",
    staging_dir: str = ".tmp/leaderboard-staging",
    max_canonical_records: int = 100,
    generation_id: str = "",
    generated_at_utc: str = "",
) -> None:
    root = Path(repo_root)
    manifest = publish_from_canonical(
        branch_root=root,
        canonical_dir=root / canonical_dir,
        staging_dir=root / staging_dir,
        max_canonical_records=max_canonical_records,
        generation_id=generation_id or None,
        generated_at_utc=generated_at_utc or None,
        dry_run=False,
    )

    changed, pushed_generation_id = _commit_and_push_rebuild(repo_root=root, target_branch=target_branch)
    print(f"changed={str(changed).lower()}")
    print(f"generation_id={pushed_generation_id or manifest.generation_id}")


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


@task(name="smoke-check")
def smoke_check(
    _ctx,
    leaderboard_base_url: str = "",
) -> None:
    result = _run_leaderboard_smoke_check(leaderboard_base_url=leaderboard_base_url)
    print(f"base_url={result['base_url']}")
    print(f"generation_id={result['generation_id']}")
    print(f"full_file={result['full_file']}")
    print(f"hard_file={result['hard_file']}")
