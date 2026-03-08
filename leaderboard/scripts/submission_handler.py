from __future__ import annotations

import logging
from pathlib import Path  # noqa: TC003

from webarena_verified.submission.config import SubmissionFlowConfig
from webarena_verified.submission.submission_validator import SubmissionValidator

from .leaderboard_builder import LeaderboardBuilder
from .models import IngestResult
from .submission_data_backend import SubmissionDataBackend, extract_submission_uids_from_diff
from .submission_evaluator import SubmissionEvaluator

logger = logging.getLogger(__name__)


def _locate_submission_directory(
    *,
    submissions_root: Path,
    flow_config: SubmissionFlowConfig,
    hf_repo: str,
    hf_pr_number: int,
    submission_uid_override: str | None,
    backend: SubmissionDataBackend,
) -> Path:
    """Resolve which submission directory a PR targets inside the HF snapshot.

    A snapshot may contain multiple ``submissions/<uid>/`` folders. This
    function picks the right one using three tiers:

    1. **Explicit override** – use *submission_uid_override* directly.
    2. **Single candidate** – if only one directory has the required files
       (``submission.json``, ``manifest.json``, ``_internal.json``), use it.
    3. **PR diff heuristic** – parse the PR diff to find which
       ``submissions/<uid>/`` path was touched; use it if exactly one matches.

    Raises ``ValueError`` when none of the above yields a unique directory.
    """
    candidates: list[Path] = []
    for child in sorted(submissions_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        has_submission = (child / flow_config.submission_file_name).exists()
        has_manifest = (child / flow_config.manifest_file_name).exists()
        has_internal = (child / flow_config.internal_file_name).exists()
        if has_submission and has_manifest and has_internal:
            candidates.append(child)

    if not candidates:
        raise ValueError("No valid submission directory found under submissions/")

    if isinstance(submission_uid_override, str) and submission_uid_override.strip():
        explicit_path = submissions_root / submission_uid_override
        if explicit_path in candidates:
            return explicit_path
        raise ValueError("submission_uid does not point to a valid submission folder with required files")

    if len(candidates) == 1:
        return candidates[0]

    diff_text = backend.get_pr_diff(repo_id=hf_repo, pr_number=hf_pr_number)
    if diff_text:
        changed_uids = sorted(extract_submission_uids_from_diff(diff_text))
        if len(changed_uids) == 1:
            inferred_path = submissions_root / changed_uids[0]
            if inferred_path in candidates:
                return inferred_path

    candidate_names = ", ".join(path.name for path in candidates)
    raise ValueError(
        "Unable to determine a unique submission directory from HF snapshot. "
        f"Found candidates: [{candidate_names}]. "
        "Provide submission_uid or ensure PR diff touches exactly one "
        "submissions/<submission_uid>/ path."
    )


def sync_submission(
    *,
    repo_root: Path,
    hf_repo: str,
    hf_pr_number: int,
    hf_head_sha: str,
    backend: SubmissionDataBackend,
    submission_uid: str | None = None,
) -> IngestResult:
    """Download, validate, evaluate, and apply a single HF PR submission."""
    flow_config = SubmissionFlowConfig()

    logger.info("Downloading HF snapshot for repo=%s pr=%d sha=%s", hf_repo, hf_pr_number, hf_head_sha)
    submissions_root = backend.download_submission_snapshot(repo_id=hf_repo, revision=hf_head_sha)

    logger.info("Locating submission directory in %s", submissions_root)
    submission_dir = _locate_submission_directory(
        submissions_root=submissions_root,
        flow_config=flow_config,
        hf_repo=hf_repo,
        hf_pr_number=hf_pr_number,
        submission_uid_override=submission_uid,
        backend=backend,
    )

    logger.info("Validating submission in %s", submission_dir.name)
    validator = SubmissionValidator(flow_config)
    submission_metadata, _manifest, internal = validator.validate_submission_tree(submission_dir)

    if submission_dir.name != submission_metadata.submission_uid:
        raise ValueError("Submission folder name must match submission_uid")

    logger.info("Evaluating submission uid=%s mode=%s", submission_metadata.submission_uid, internal.submission_mode)
    evaluator = SubmissionEvaluator(flow_config)
    summaries = evaluator.evaluate_submission(
        submission_dir=submission_dir,
        submission=submission_metadata,
        submission_mode=internal.submission_mode,
    )

    submission_path = flow_config.submission_dataset_path(submission_metadata.submission_uid)
    source_url = flow_config.source_submission_url_template.format(
        hf_repo=hf_repo,
        source_sha=hf_head_sha,
        submission_path=submission_path,
    )
    logger.info("Building leaderboard artifacts for uid=%s", submission_metadata.submission_uid)
    leaderboard_builder = LeaderboardBuilder(flow_config)
    latest_path, full_path, hard_path = leaderboard_builder.apply_submission_result(
        repo_root=repo_root,
        submission_uid=submission_metadata.submission_uid,
        submission_mode=internal.submission_mode,
        source_url=source_url,
        submission_name=submission_metadata.name,
        submission_model=submission_metadata.model,
        evaluation_summaries=summaries,
    )

    logger.info("Ingest complete for uid=%s", submission_metadata.submission_uid)
    return IngestResult(
        submission_uid=submission_metadata.submission_uid,
        leaderboard_latest_path=str(latest_path),
        full_artifact_path=str(full_path),
        hard_artifact_path=str(hard_path),
    )


def sync_submissions(
    *,
    repo_root: Path,
    hf_repo: str,
    hf_token: str,
    max_recent_refs: int = 50,
) -> list[int]:
    """Pull recent HF dataset PRs and ingest each one."""
    if not hf_repo.strip() or not hf_token.strip():
        raise ValueError("hf_repo and hf_token are required")
    if max_recent_refs < 1:
        raise ValueError("max_recent_refs must be >= 1")

    backend = SubmissionDataBackend(hf_token)
    logger.info("Listing recent PR refs from %s (max=%d)", hf_repo, max_recent_refs)
    head_by_pr_number = backend.list_pr_refs(repo_id=hf_repo)
    selected_numbers = sorted(head_by_pr_number.keys(), reverse=True)[:max_recent_refs]
    logger.info("Found %d PR refs, processing %d", len(head_by_pr_number), len(selected_numbers))

    processed: list[int] = []
    for pr_number in selected_numbers:
        sync_submission(
            repo_root=repo_root,
            hf_repo=hf_repo,
            hf_pr_number=pr_number,
            hf_head_sha=head_by_pr_number[pr_number],
            backend=backend,
        )
        processed.append(pr_number)
    return processed
