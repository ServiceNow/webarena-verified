from __future__ import annotations

import hashlib
import json
import datetime as dt
import shutil
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi
from huggingface_hub import snapshot_download
from webarena_verified.api import WebArenaVerified
from webarena_verified.types.eval import WEBARENA_VERIFIED_VERSION, EvalStatus
from webarena_verified.types.leaderboard import (
    CanonicalSubmissionRecord,
    EvaluationSummary,
    HFDispatchContext,
    HFIngestResult,
    IntakeManifest,
    IntakeSubmission,
    SubmissionControlRecord,
    SubmissionStatusEvent,
)
from webarena_verified.types.leaderboard.submission_control import SubmissionControlStatus


_CONTROL_DIR = "submission_control"
_CONTROL_EVENT_CAP = 32
_INTAKE_PREFIX = "submissions/inbox/"
_TASKS_DIR_NAME = "tasks"
_MISSING_SENTINEL_FILE = ".missing"
_AGENT_RESPONSE_FILE = "agent_response.json"
_NETWORK_HAR_FILE = "network.har"
_SITE_KEYS = ("shopping", "reddit", "gitlab", "wikipedia", "map", "shopping_admin")


class FinalizeError(ValueError):
    pass


def _now_utc_z() -> str:
    return dt.datetime.now(tz=dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json_file(path: Path, *, field_name: str) -> dict[str, Any]:
    if not path.exists():
        raise FinalizeError(f"{field_name} file is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _require_dict(payload, field_name=field_name)


def _load_hf_pr_payload(repo_root: Path, context: HFDispatchContext) -> tuple[IntakeSubmission, IntakeManifest]:
    intake_id = f"pr-{context.hf_pr_number}"
    intake_root = repo_root / _INTAKE_PREFIX / intake_id
    submission = IntakeSubmission.model_validate(
        _load_json_file(intake_root / "submission.json", field_name="submission")
    )
    manifest = IntakeManifest.model_validate(_load_json_file(intake_root / "manifest.json", field_name="manifest"))
    return submission, manifest


def _materialize_hf_payload(repo_root: Path, context: HFDispatchContext, hf_token: str) -> None:
    snapshot_root = Path(
        snapshot_download(
            repo_id=context.hf_repo,
            repo_type="dataset",
            revision=context.hf_head_sha,
            token=hf_token or None,
            allow_patterns=[
                f"submissions/inbox/pr-{context.hf_pr_number}/*",
                f"submissions/inbox/pr-{context.hf_pr_number}/**",
            ],
        )
    )
    source = snapshot_root / "submissions" / "inbox" / f"pr-{context.hf_pr_number}"
    if not source.exists():
        raise FinalizeError(f"HF snapshot missing required intake path: {source}")

    destination = repo_root / "submissions" / "inbox" / f"pr-{context.hf_pr_number}"
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _latest_hf_pr_sha(*, hf_repo: str, hf_pr_number: int, hf_token: str) -> str:
    refs = HfApi(token=hf_token or None).list_repo_refs(repo_id=hf_repo, repo_type="dataset")
    pull_requests = refs.pull_requests or []
    for ref in pull_requests:
        if ref.ref == f"refs/pr/{hf_pr_number}":
            return ref.target_commit
    raise FinalizeError(f"Unable to resolve latest HF PR ref for {hf_repo}#{hf_pr_number}")


def _task_id_from_path(task_dir: Path) -> int:
    if not task_dir.name.isdigit():
        raise FinalizeError(f"Task directory name must be numeric, got '{task_dir.name}'")
    return int(task_dir.name)


def _task_sites(wa: WebArenaVerified, task_id: int) -> list[str]:
    task = wa.get_task(task_id)
    return [str(site.value) for site in task.sites if str(site.value) in _SITE_KEYS]


def _evaluate_task_status(wa: WebArenaVerified, *, task_id: int, task_dir: Path) -> str:
    if (task_dir / _MISSING_SENTINEL_FILE).exists():
        return "missing"

    agent_response = task_dir / _AGENT_RESPONSE_FILE
    network_har = task_dir / _NETWORK_HAR_FILE
    if not agent_response.exists() or not network_har.exists():
        raise FinalizeError(
            f"Task {task_id} must include {_AGENT_RESPONSE_FILE} and {_NETWORK_HAR_FILE} or use .missing sentinel"
        )

    result = wa.evaluate_task(task_id=task_id, agent_response=agent_response, network_trace=network_har)
    if result.status == EvalStatus.SUCCESS:
        return "success"
    if result.status == EvalStatus.ERROR:
        return "error"
    return "failure"


def _site_scores(*, site_total: dict[str, int], site_success: dict[str, int]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for site in _SITE_KEYS:
        total = site_total[site]
        scores[site] = 0.0 if total == 0 else site_success[site] / total
    return scores


def _run_hf_evaluation(repo_root: Path, context: HFDispatchContext, evaluator_version: str) -> EvaluationSummary:
    tasks_root = repo_root / _INTAKE_PREFIX / f"pr-{context.hf_pr_number}" / _TASKS_DIR_NAME
    if not tasks_root.exists():
        raise FinalizeError(f"Missing intake tasks directory: {tasks_root}")

    wa = WebArenaVerified()
    success_count = 0
    failure_count = 0
    error_count = 0
    missing_count = 0

    site_total: dict[str, int] = dict.fromkeys(_SITE_KEYS, 0)
    site_success: dict[str, int] = dict.fromkeys(_SITE_KEYS, 0)

    task_dirs = sorted(path for path in tasks_root.iterdir() if path.is_dir())
    if not task_dirs:
        raise FinalizeError("No task directories found under submissions/inbox/pr-<hf_pr_number>/tasks/")

    for task_dir in task_dirs:
        task_id = _task_id_from_path(task_dir)
        task_sites = _task_sites(wa, task_id)
        for site in task_sites:
            site_total[site] += 1

        task_status = _evaluate_task_status(wa, task_id=task_id, task_dir=task_dir)
        if task_status == "missing":
            missing_count += 1
            continue
        if task_status == "success":
            success_count += 1
            for site in task_sites:
                site_success[site] += 1
            continue
        if task_status == "error":
            error_count += 1
            continue
        failure_count += 1

    total_count = success_count + failure_count + error_count + missing_count
    if total_count == 0:
        raise FinalizeError("No tasks found for scoring")

    site_scores = _site_scores(site_total=site_total, site_success=site_success)
    resolved_version = evaluator_version or WEBARENA_VERIFIED_VERSION
    return EvaluationSummary(
        overall_score=success_count / total_count,
        shopping_score=site_scores["shopping"],
        reddit_score=site_scores["reddit"],
        gitlab_score=site_scores["gitlab"],
        wikipedia_score=site_scores["wikipedia"],
        map_score=site_scores["map"],
        shopping_admin_score=site_scores["shopping_admin"],
        success_count=success_count,
        failure_count=failure_count,
        error_count=error_count,
        missing_count=missing_count,
        evaluator_version=resolved_version,
    )


def _write_canonical_record(*, repo_root: Path, submission_id: int, record: CanonicalSubmissionRecord) -> Path:
    output_path = repo_root / "submissions" / f"{submission_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output_path


def _require_dict(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FinalizeError(f"{field_name} must be an object")
    return value


def _manifest_checksum(manifest: dict[str, Any]) -> str:
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_hf_dispatch_event(event_path: Path) -> HFDispatchContext:
    payload = _require_dict(json.loads(event_path.read_text(encoding="utf-8")), field_name="event payload")
    client_payload = _require_dict(payload.get("client_payload"), field_name="client_payload")
    context = HFDispatchContext.model_validate(client_payload)
    if not context.hf_pr_url:
        context.hf_pr_url = f"https://huggingface.co/datasets/{context.hf_repo}/discussions/{context.hf_pr_number}"
    return context


def _control_record_path(repo_root: Path, submission_id: int) -> Path:
    return repo_root / _CONTROL_DIR / f"{submission_id}.json"


def _append_status(
    record: SubmissionControlRecord,
    *,
    status: SubmissionControlStatus,
    reason: str | None = None,
    run_sha: str | None = None,
    latest_sha: str | None = None,
) -> SubmissionControlRecord:
    record.status = status
    record.status_history.append(
        SubmissionStatusEvent(
            status=status,
            at_utc=_now_utc_z(),
            reason=reason,
            run_sha=run_sha,
            latest_sha=latest_sha,
        )
    )
    return record


def _write_control_record(repo_root: Path, record: SubmissionControlRecord) -> Path:
    path = _control_record_path(repo_root, record.submission_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def _load_or_init_control_record(repo_root: Path, context: HFDispatchContext) -> SubmissionControlRecord:
    submission_id = context.hf_pr_number
    submission_uid = f"hf:{context.hf_repo}:pr-{context.hf_pr_number}@{context.hf_head_sha}"
    path = _control_record_path(repo_root, submission_id)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = SubmissionControlRecord.model_validate(payload)
        previous_sha = record.hf_head_sha
        if previous_sha != context.hf_head_sha:
            _append_status(
                record,
                status=SubmissionControlStatus.SUPERSEDED,
                reason="new_head_sha_detected",
                run_sha=previous_sha,
                latest_sha=context.hf_head_sha,
            )
        record.submission_uid = submission_uid
        record.hf_head_sha = context.hf_head_sha
        record.hf_pr_url = context.hf_pr_url
        return record

    record = SubmissionControlRecord(
        submission_id=submission_id,
        submission_uid=submission_uid,
        hf_repo=context.hf_repo,
        hf_pr_number=context.hf_pr_number,
        hf_head_sha=context.hf_head_sha,
        hf_pr_url=context.hf_pr_url,
        status=SubmissionControlStatus.PENDING,
    )
    return _append_status(record, status=SubmissionControlStatus.PENDING, reason="created")


def ingest_hf_submission(
    *,
    repo_root: Path,
    event_path: Path,
    hf_repo_canonical: str,
    hf_token: str,
    evaluator_version: str,
) -> HFIngestResult:
    context = parse_hf_dispatch_event(event_path)
    if context.hf_repo != hf_repo_canonical:
        raise FinalizeError(f"Event hf_repo '{context.hf_repo}' does not match canonical repo '{hf_repo_canonical}'")

    latest_sha = _latest_hf_pr_sha(hf_repo=context.hf_repo, hf_pr_number=context.hf_pr_number, hf_token=hf_token)
    if latest_sha != context.hf_head_sha:
        control = _load_or_init_control_record(repo_root, context)
        _append_status(
            control,
            status=SubmissionControlStatus.SUPERSEDED,
            reason="stale_event_head_sha",
            run_sha=context.hf_head_sha,
            latest_sha=latest_sha,
        )
        control.submission_uid = f"hf:{control.hf_repo}:pr-{control.hf_pr_number}@{latest_sha}"
        control.hf_head_sha = latest_sha
        control_path = _write_control_record(repo_root, control)
        return HFIngestResult(
            submission_id=control.submission_id,
            submission_uid=control.submission_uid,
            control_record_path=str(control_path),
            status=control.status,
        )

    control = _load_or_init_control_record(repo_root, context)
    if context.event_id in control.processed_event_ids:
        path = _write_control_record(repo_root, control)
        return HFIngestResult(
            submission_id=control.submission_id,
            submission_uid=control.submission_uid,
            control_record_path=str(path),
            status=control.status,
        )

    _append_status(control, status=SubmissionControlStatus.VALIDATING)
    control_path = _write_control_record(repo_root, control)

    _materialize_hf_payload(repo_root, context, hf_token)

    try:
        intake_submission, intake_manifest = _load_hf_pr_payload(repo_root, context)
    except Exception as exc:
        _append_status(control, status=SubmissionControlStatus.REJECTED, reason=str(exc))
        _write_control_record(repo_root, control)
        raise

    _append_status(control, status=SubmissionControlStatus.EVALUATING)
    _write_control_record(repo_root, control)

    try:
        eval_summary = _run_hf_evaluation(repo_root, context, evaluator_version)
    except Exception as exc:
        control.retry_count += 1
        _append_status(control, status=SubmissionControlStatus.FAILED_RETRYABLE, reason=str(exc))
        _write_control_record(repo_root, control)
        raise

    submission_id = context.hf_pr_number
    canonical = CanonicalSubmissionRecord(
        submission_id=submission_id,
        submission_uid=control.submission_uid,
        github_pr_number=None,
        github_pr_url=None,
        eval_completed_at_utc=_now_utc_z(),
        evaluator_version=eval_summary.evaluator_version,
        hf_repo=context.hf_repo,
        hf_path=f"submissions/inbox/pr-{context.hf_pr_number}/",
        hf_revision=context.hf_head_sha,
        hf_pr_number=context.hf_pr_number,
        hf_head_sha=context.hf_head_sha,
        hf_pr_url=context.hf_pr_url,
        name=intake_submission.name,
        model=intake_submission.model,
        leaderboard=intake_submission.leaderboard,
        reference=intake_submission.reference,
        code_repository=intake_submission.code_repository,
        model_version=None,
        contact_email=intake_submission.contact_email,
        overall_score=eval_summary.overall_score,
        shopping_score=eval_summary.shopping_score,
        reddit_score=eval_summary.reddit_score,
        gitlab_score=eval_summary.gitlab_score,
        wikipedia_score=eval_summary.wikipedia_score,
        map_score=eval_summary.map_score,
        shopping_admin_score=eval_summary.shopping_admin_score,
        success_count=eval_summary.success_count,
        failure_count=eval_summary.failure_count,
        error_count=eval_summary.error_count,
        missing_count=eval_summary.missing_count,
        checksum=_manifest_checksum(intake_manifest.model_dump(mode="python")),
    )
    canonical_path = _write_canonical_record(repo_root=repo_root, submission_id=submission_id, record=canonical)

    control.processed_event_ids.append(context.event_id)
    control.processed_event_ids = control.processed_event_ids[-_CONTROL_EVENT_CAP:]
    _append_status(control, status=SubmissionControlStatus.ACCEPTED_PENDING_PUBLISH)
    control_path = _write_control_record(repo_root, control)

    return HFIngestResult(
        submission_id=submission_id,
        submission_uid=control.submission_uid,
        control_record_path=str(control_path),
        canonical_record_path=str(canonical_path),
        status=control.status,
    )
