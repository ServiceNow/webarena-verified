from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, snapshot_download

from webarena_verified.submission.config import SubmissionFlowConfig
from webarena_verified.submission.submission_validator import SubmissionValidator

from .leaderboard_builder import LeaderboardBuilder
from .models import IngestResult
from .submission_evaluator import SubmissionEvaluator


class IngestError(ValueError):
    """Raised when a submission ingest fails due to invalid input.

    Covers missing fields in the GitHub dispatch event, HF snapshot issues,
    ambiguous submission directories, and submission-uid mismatches.
    Caught by the CI workflow to report a clear failure reason.
    """


def _require_dict(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IngestError(f"{field_name} must be an object")
    return value


def _parse_dispatch_context(event_path: Path) -> dict[str, Any]:
    payload = _require_dict(json.loads(event_path.read_text(encoding="utf-8")), field_name="event payload")
    context = _require_dict(payload.get("client_payload"), field_name="client_payload")
    required = ("hf_repo", "hf_pr_number", "hf_head_sha")
    for field_name in required:
        if not context.get(field_name):
            raise IngestError(f"Missing required client_payload field: {field_name}")
    submission_uid = context.get("submission_uid")
    if submission_uid is not None and not isinstance(submission_uid, str):
        raise IngestError("client_payload.submission_uid must be a string when provided")
    return context


def _materialize_submission_snapshot(*, context: dict[str, Any], hf_token: str) -> Path:
    snapshot_root = Path(
        snapshot_download(
            repo_id=context["hf_repo"],
            repo_type="dataset",
            revision=context["hf_head_sha"],
            token=hf_token or None,
            allow_patterns=["submissions/*", "submissions/*/**"],
        )
    )
    source_root = snapshot_root / "submissions"
    if not source_root.exists():
        raise IngestError("HF snapshot does not contain submissions directory")
    return source_root


def _extract_submission_uids_from_diff(diff_text: str) -> set[str]:
    uids: set[str] = set()
    pattern = re.compile(r"^diff --git a/submissions/([^/]+)/", re.MULTILINE)
    for match in pattern.finditer(diff_text):
        uids.add(match.group(1))
    return uids


def _resolve_submission_uid_from_pr_diff(*, context: dict[str, Any], hf_token: str) -> str | None:
    details = HfApi(token=hf_token or None).get_discussion_details(
        repo_id=context["hf_repo"],
        discussion_num=int(context["hf_pr_number"]),
        repo_type="dataset",
    )
    if not getattr(details, "diff", None):
        return None

    changed_uids = sorted(_extract_submission_uids_from_diff(details.diff or ""))
    if len(changed_uids) == 1:
        return changed_uids[0]
    return None


def _locate_submission_directory(
    *, submissions_root: Path, flow_config: SubmissionFlowConfig, context: dict[str, Any], hf_token: str
) -> Path:
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
        raise IngestError("No valid submission directory found under submissions/")

    explicit_submission_uid = context.get("submission_uid")
    if isinstance(explicit_submission_uid, str) and explicit_submission_uid.strip():
        explicit_path = submissions_root / explicit_submission_uid
        if explicit_path in candidates:
            return explicit_path
        raise IngestError("Event submission_uid does not point to a valid submission folder with required files")

    if len(candidates) == 1:
        return candidates[0]

    inferred_submission_uid = _resolve_submission_uid_from_pr_diff(context=context, hf_token=hf_token)
    if inferred_submission_uid is not None:
        inferred_path = submissions_root / inferred_submission_uid
        if inferred_path in candidates:
            return inferred_path

    candidate_names = ", ".join(path.name for path in candidates)
    raise IngestError(
        "Unable to determine a unique submission directory from HF snapshot. "
        f"Found candidates: [{candidate_names}]. "
        "Provide client_payload.submission_uid or ensure PR diff touches exactly one "
        "submissions/<submission_uid>/ path."
    )


def ingest_hf_submission(
    *,
    repo_root: Path,
    event_path: Path,
    hf_repo_expected: str,
    hf_token: str,
    evaluator_version: str,
) -> IngestResult:
    """End-to-end ingest of a single HF dataset PR submission.

    This is the top-level entry point for stage 1 of the leaderboard
    pipeline, orchestrating the full sequence:

    1. Parse the GitHub ``repository_dispatch`` event JSON.
    2. Download the HF dataset snapshot at the PR head SHA.
    3. Locate and validate the submission directory.
    4. Evaluate all tasks via ``SubmissionEvaluator``.
    5. Update leaderboard artifacts via ``LeaderboardBuilder``.

    Triggered by the ``hf-ingest`` Invoke task (which is called from the
    ``leaderboard-hf-ingest.yml`` GitHub Actions workflow).

    Args:
        repo_root: Checkout of the ``leaderboard-submissions`` branch.
        event_path: Path to the ``$GITHUB_EVENT_PATH`` JSON file.
        hf_repo_expected: HF dataset repo ID to validate against.
        hf_token: Hugging Face API token.
        evaluator_version: Reserved for future evaluator version pinning.

    Returns:
        ``IngestResult`` with paths to the written leaderboard files.

    Raises:
        IngestError: On any validation or snapshot failure.
    """
    del evaluator_version
    flow_config = SubmissionFlowConfig()
    context = _parse_dispatch_context(event_path)
    if context["hf_repo"] != hf_repo_expected:
        raise IngestError(f"Event hf_repo '{context['hf_repo']}' does not match expected repo '{hf_repo_expected}'")

    submissions_root = _materialize_submission_snapshot(context=context, hf_token=hf_token)
    submission_dir = _locate_submission_directory(
        submissions_root=submissions_root,
        flow_config=flow_config,
        context=context,
        hf_token=hf_token,
    )

    validator = SubmissionValidator(flow_config)
    submission_metadata, _manifest, internal = validator.validate_submission_tree(submission_dir)

    if submission_dir.name != submission_metadata.submission_uid:
        raise IngestError("Submission folder name must match submission_uid")

    evaluator = SubmissionEvaluator(flow_config)
    summaries = evaluator.evaluate_submission(
        submission_dir=submission_dir,
        submission=submission_metadata,
        submission_mode=internal.submission_mode,
    )

    submission_path = flow_config.submission_dataset_path(submission_metadata.submission_uid)
    source_url = flow_config.source_submission_url_template.format(
        hf_repo=context["hf_repo"],
        source_sha=context["hf_head_sha"],
        submission_path=submission_path,
    )
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

    return IngestResult(
        submission_uid=submission_metadata.submission_uid,
        leaderboard_latest_path=str(latest_path),
        full_artifact_path=str(full_path),
        hard_artifact_path=str(hard_path),
    )


def _list_recent_hf_pr_heads(*, hf_repo: str, hf_token: str) -> dict[int, str]:
    refs = HfApi(token=hf_token or None).list_repo_refs(repo_id=hf_repo, repo_type="dataset")
    head_by_pr_number: dict[int, str] = {}
    for ref in refs.pull_requests or []:
        suffix = ref.ref.replace("refs/pr/", "")
        if suffix.isdigit():
            head_by_pr_number[int(suffix)] = ref.target_commit
    return head_by_pr_number


def sync_submissions(
    *,
    repo_root: Path,
    hf_repo: str,
    hf_token: str,
    evaluator_version: str,
    max_recent_refs: int = 50,
) -> list[int]:
    """Batch-sync recent HF dataset PRs by ingesting each one.

    Lists open pull-request refs on the HF dataset repo, takes the most
    recent ``max_recent_refs``, and calls ``ingest_hf_submission`` for each.
    This is the scheduled counterpart to event-driven single-PR ingest —
    it catches any PRs that were missed or need re-evaluation.

    Triggered by the ``hf-sync-submissions`` Invoke task (run on a cron
    schedule by the ``leaderboard-hf-ingest.yml`` workflow).

    Args:
        repo_root: Checkout of the ``leaderboard-submissions`` branch.
        hf_repo: HF dataset repo ID (e.g. ``"AmineHA/WebArena-Verified"``).
        hf_token: Hugging Face API token.
        evaluator_version: Passed through to ``ingest_hf_submission``.
        max_recent_refs: Cap on how many PR refs to process.

    Returns:
        List of HF PR numbers that were successfully processed.
    """
    if not hf_repo.strip() or not hf_token.strip():
        raise ValueError("hf_repo and hf_token are required")
    if max_recent_refs < 1:
        raise ValueError("max_recent_refs must be >= 1")

    head_by_pr_number = _list_recent_hf_pr_heads(hf_repo=hf_repo, hf_token=hf_token)
    selected_numbers = sorted(head_by_pr_number.keys(), reverse=True)[:max_recent_refs]

    processed: list[int] = []
    for pr_number in selected_numbers:
        event_payload = {
            "client_payload": {
                "event_id": f"sync-{pr_number}-{head_by_pr_number[pr_number]}",
                "event_scope": "schedule",
                "event_action": "sync_submissions",
                "hf_repo": hf_repo,
                "hf_pr_number": pr_number,
                "hf_head_sha": head_by_pr_number[pr_number],
                "hf_pr_url": f"https://huggingface.co/datasets/{hf_repo}/discussions/{pr_number}",
            }
        }
        event_path = repo_root / ".tmp" / f"sync-{pr_number}.json"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(json.dumps(event_payload), encoding="utf-8")
        ingest_hf_submission(
            repo_root=repo_root,
            event_path=event_path,
            hf_repo_expected=hf_repo,
            hf_token=hf_token,
            evaluator_version=evaluator_version,
        )
        processed.append(pr_number)
    return processed
