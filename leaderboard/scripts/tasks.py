from __future__ import annotations

import json
import os
from pathlib import Path

from invoke.tasks import task

from leaderboard.scripts.leaderboard_builder import LeaderboardBuilder
from leaderboard.scripts.submission_handler import ingest_hf_submission, sync_submissions
from webarena_verified.submission.config import SubmissionFlowConfig

_DEFAULT_MANIFEST_URL = (
    "https://raw.githubusercontent.com/ServiceNow/webarena-verified/leaderboard-submissions/leaderboard/latest.json"
)


def rebuild_leaderboard_artifacts(
    *,
    branch_root: Path,
    dry_run: bool = False,
) -> dict[str, str]:
    """Re-rank and rewrite all leaderboard generation artifacts in place.

    Thin wrapper around ``LeaderboardBuilder.rebuild_leaderboard`` that
    returns a serialisable dict of paths for CI consumption.  Also used
    programmatically (exported from ``leaderboard.scripts.__init__``).

    Args:
        branch_root: Checkout root of the ``leaderboard-submissions`` branch.
        dry_run: If ``True``, skip all I/O and return ``{"mode": "dry_run"}``.

    Returns:
        Dict with ``generation_id``, ``latest``, ``full``, ``hard`` keys.
    """
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


def _resolve_manifest_url(*, manifest_url_override: str, configured_manifest_url: str) -> str:
    override = manifest_url_override.strip()
    if override:
        return override

    configured = configured_manifest_url.strip()
    if configured:
        return configured

    return _DEFAULT_MANIFEST_URL


@task(name="rebuild-leaderboard")
def rebuild_leaderboard(
    _ctx,
    repo_root: str = ".",
    dry_run: bool = False,
) -> None:
    """Invoke task: rebuild leaderboard artifacts and print paths.

    CLI wrapper around ``rebuild_leaderboard_artifacts``.  Prints the
    generation ID and file paths to stdout for consumption by CI scripts.

    Usage::

        invoke rebuild-leaderboard --repo-root /path/to/checkout
    """
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
    """Invoke task: ingest a single HF submission from a dispatch event.

    Reads the GitHub ``repository_dispatch`` event at ``event_path``,
    downloads the HF snapshot, validates, evaluates, and updates the
    leaderboard.  Prints the ``IngestResult`` as JSON.

    Called by the ``leaderboard-hf-ingest.yml`` workflow on
    ``repository_dispatch`` events.

    Usage::

        invoke hf-ingest --event-path event.json --hf-repo AmineHA/WebArena-Verified
    """
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
    """Invoke task: batch-sync recent HF PRs into the leaderboard.

    Iterates over the most recent HF dataset PR refs and ingests each one.
    Prints the count and list of processed PR numbers.

    Called by the ``leaderboard-hf-ingest.yml`` workflow on a cron schedule
    to catch submissions that may have been missed by event-driven ingest.

    Usage::

        invoke hf-sync-submissions --hf-repo AmineHA/WebArena-Verified
    """
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
    """Invoke task: resolve the ``latest.json`` manifest URL.

    Prints the effective manifest URL to stdout, choosing in priority order:
    explicit override → configured URL → built-in default pointing to the
    ``leaderboard-submissions`` branch on GitHub.

    Used by the docs-site build to embed the correct leaderboard data URL.

    Usage::

        invoke site-resolve-manifest-url --manifest-url-override https://...
    """
    manifest_url = _resolve_manifest_url(
        manifest_url_override=manifest_url_override,
        configured_manifest_url=configured_manifest_url,
    )
    print(manifest_url)
