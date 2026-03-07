"""Invoke entry points for leaderboard submission workflows."""

from __future__ import annotations

import os
from pathlib import Path

from invoke import task

from leaderboard.scripts.finalize import finalize_submission
from leaderboard.scripts.pr_gate_intake_validator import PRGateValidationError, run_pr_gate_intake_validation
from leaderboard.scripts.publish import publish_from_canonical


@task(name="finalize")
def finalize(
    _ctx,
    event_path: str,
    github_repo: str,
    hf_repo: str,
    github_token: str = "",
    hf_token: str = "",
    evaluator_version: str = "",
) -> None:
    """Finalize one merged intake PR into a canonical submission record."""
    github_token = github_token or os.environ.get("GITHUB_TOKEN", "")
    hf_token = hf_token or os.environ.get("HF_TOKEN", "")

    result = finalize_submission(
        repo_root=Path.cwd(),
        event_path=Path(event_path),
        github_repo=github_repo,
        github_token=github_token,
        hf_repo=hf_repo,
        hf_token=hf_token,
        evaluator_version=evaluator_version,
    )
    print(result.model_dump_json(indent=2))


@task(name="pr-gate-intake-validate")
def pr_gate_intake_validate(_ctx, base_sha: str, head_sha: str, repo_root: str = ".") -> None:
    """Validate one intake payload for PR Gate (C03-C05)."""
    expected_version = os.environ.get("LEADERBOARD_EVALUATOR_VERSION", "").strip() or None
    try:
        result = run_pr_gate_intake_validation(
            repo_root=Path(repo_root),
            base_sha=base_sha,
            head_sha=head_sha,
            expected_evaluator_version=expected_version,
        )
    except PRGateValidationError as exc:
        raise RuntimeError(str(exc)) from exc

    preview = result.score_preview
    preview_json = preview.model_dump_json()

    print(f"intake_id={result.intake_id}")
    print(f"changed_files={len(result.changed_paths)}")
    print(f"evaluator_version={preview.evaluator_version}")
    print(f"overall_score={preview.overall_score:.6f}")
    print(f"success_count={preview.success_count}")
    print(f"failure_count={preview.failure_count}")
    print(f"error_count={preview.error_count}")
    print(f"missing_count={preview.missing_count}")
    print(f"score_preview_json={preview_json}")


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
