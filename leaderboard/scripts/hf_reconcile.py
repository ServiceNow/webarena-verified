from __future__ import annotations

import json
from typing import TYPE_CHECKING

from huggingface_hub import HfApi

from leaderboard.scripts.hf_ingest import ingest_hf_submission
from webarena_verified.types.leaderboard import SubmissionControlRecord
from webarena_verified.types.leaderboard.submission_control import SubmissionControlStatus

if TYPE_CHECKING:
    from pathlib import Path

_RECONCILE_RETRYABLE_STATUSES = {
    SubmissionControlStatus.ACCEPTED_PENDING_PUBLISH,
    SubmissionControlStatus.FAILED_RETRYABLE,
}


def _validate_reconcile_inputs(
    *,
    repo_root: Path,
    hf_repo: str,
    hf_token: str,
    evaluator_version: str,
    max_recent_refs: int,
) -> None:
    missing: list[str] = []
    if not hf_repo.strip():
        missing.append("hf_repo")
    if not hf_token.strip():
        missing.append("hf_token")
    if not evaluator_version.strip():
        missing.append("evaluator_version")
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required reconcile input(s): {joined}")

    if max_recent_refs < 1:
        raise ValueError("max_recent_refs must be >= 1")
    if not repo_root.exists():
        raise ValueError(f"repo_root does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise ValueError(f"repo_root is not a directory: {repo_root}")


def _list_hf_ref_by_submission_id(*, hf_repo: str, hf_token: str) -> dict[int, str]:
    refs = HfApi(token=hf_token or None).list_repo_refs(repo_id=hf_repo, repo_type="dataset")
    ref_by_num: dict[int, str] = {}
    for ref in refs.pull_requests or []:
        suffix = ref.ref.replace("refs/pr/", "")
        if suffix.isdigit():
            ref_by_num[int(suffix)] = ref.target_commit
    return ref_by_num


def _load_control_records(*, repo_root: Path) -> dict[int, SubmissionControlRecord]:
    root = repo_root / "submission_control"
    if not root.exists():
        return {}

    records: dict[int, SubmissionControlRecord] = {}
    for record_path in sorted(root.glob("*.json")):
        payload = json.loads(record_path.read_text(encoding="utf-8"))
        record = SubmissionControlRecord.model_validate(payload)
        records[record.submission_id] = record
    return records


def reconcile_hf_submissions(
    *,
    repo_root: Path,
    hf_repo: str,
    hf_token: str,
    evaluator_version: str,
    max_recent_refs: int = 50,
) -> list[int]:
    """Reconcile pending HF submissions and trigger ingest per candidate."""
    _validate_reconcile_inputs(
        repo_root=repo_root,
        hf_repo=hf_repo,
        hf_token=hf_token,
        evaluator_version=evaluator_version,
        max_recent_refs=max_recent_refs,
    )

    ref_by_num = _list_hf_ref_by_submission_id(hf_repo=hf_repo, hf_token=hf_token)
    control_records = _load_control_records(repo_root=repo_root)

    candidate_numbers = sorted(ref_by_num.keys(), reverse=True)[:max_recent_refs]
    for submission_id, record in control_records.items():
        if record.status in _RECONCILE_RETRYABLE_STATUSES and submission_id not in candidate_numbers:
            candidate_numbers.append(submission_id)

    reconciled_submission_ids: list[int] = []
    for submission_id in candidate_numbers:
        head_sha = ref_by_num.get(submission_id)
        record = control_records.get(submission_id)
        if not head_sha and record:
            head_sha = record.hf_head_sha
        if not head_sha:
            continue

        event_payload = {
            "client_payload": {
                "event_id": f"reconcile-{submission_id}-{head_sha}",
                "event_scope": "schedule",
                "event_action": "reconcile",
                "hf_repo": hf_repo,
                "hf_pr_number": submission_id,
                "hf_head_sha": head_sha,
                "hf_pr_url": (
                    record.hf_pr_url
                    if record and record.hf_pr_url
                    else f"https://huggingface.co/datasets/{hf_repo}/discussions/{submission_id}"
                ),
            }
        }

        event_path = repo_root / ".tmp" / f"reconcile-{submission_id}.json"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(json.dumps(event_payload), encoding="utf-8")

        ingest_hf_submission(
            repo_root=repo_root,
            event_path=event_path,
            hf_repo_canonical=hf_repo,
            hf_token=hf_token,
            evaluator_version=evaluator_version,
        )
        reconciled_submission_ids.append(submission_id)

    return reconciled_submission_ids
