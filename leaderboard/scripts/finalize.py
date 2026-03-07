"""Finalize merged leaderboard submission PRs into canonical records."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import time
from typing import TYPE_CHECKING, Any
from urllib import error as urlerror
from urllib import parse, request

from huggingface_hub import HfApi
from pydantic import BaseModel

from webarena_verified.api import WebArenaVerified
from webarena_verified.types.eval import WEBARENA_VERIFIED_VERSION, EvalStatus
from webarena_verified.types.leaderboard import CanonicalSubmissionRecord

if TYPE_CHECKING:
    from pathlib import Path

_INTAKE_PREFIX = "submissions/inbox/"
_TASKS_DIR_NAME = "tasks"
_MISSING_SENTINEL_FILE = ".missing"
_AGENT_RESPONSE_FILE = "agent_response.json"
_NETWORK_HAR_FILE = "network.har"
_SITE_KEYS = ("shopping", "reddit", "gitlab", "wikipedia", "map", "shopping_admin")
_NETWORK_RETRY_ATTEMPTS = 3
_NETWORK_RETRY_DELAY_SECONDS = 1.0
_REQUIRED_SUBMISSION_FIELDS = (
    "name",
    "leaderboard",
    "reference",
    "created_at_utc",
    "packaging_summary",
)


class FinalizeContext(BaseModel):
    """Context extracted from a merged pull request event."""

    pr_number: int
    pr_url: str
    merge_commit_sha: str
    source_repository_id: int
    source_repository_full_name: str
    github_pr_author_id: int
    github_pr_author_login: str


class HFPersistResult(BaseModel):
    """HF persistence result for one canonical submission payload upload."""

    hf_repo: str
    hf_path: str
    hf_revision: str


class FinalizeResult(BaseModel):
    """Summary of finalize outputs."""

    submission_id: int
    intake_id: str
    canonical_record_path: str
    deleted_inbox_path: str
    hf_repo: str
    hf_path: str
    hf_revision: str


class FinalizeError(ValueError):
    """Raised when finalize invariants are violated."""


def _now_utc_z() -> str:
    return dt.datetime.now(tz=dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_dict(obj: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise FinalizeError(f"{field_name} must be an object")
    return obj


def _require_int(obj: Any, *, field_name: str) -> int:
    if isinstance(obj, bool) or not isinstance(obj, int):
        raise FinalizeError(f"{field_name} must be an integer")
    return obj


def _require_non_empty_str(obj: Any, *, field_name: str) -> str:
    if not isinstance(obj, str) or not obj.strip():
        raise FinalizeError(f"{field_name} must be a non-empty string")
    return obj


def _http_get_json(url: str, token: str) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, _NETWORK_RETRY_ATTEMPTS + 1):
        try:
            req = request.Request(url)
            req.add_header("Accept", "application/vnd.github+json")
            req.add_header("X-GitHub-Api-Version", "2022-11-28")
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            with request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urlerror.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == _NETWORK_RETRY_ATTEMPTS:
                break
            time.sleep(_NETWORK_RETRY_DELAY_SECONDS * attempt)
    raise FinalizeError(f"GitHub API request failed after {_NETWORK_RETRY_ATTEMPTS} attempts: {last_error}")


def parse_finalize_event(event_path: Path) -> FinalizeContext:
    """Parse merged PR context from a GitHub event payload file."""
    payload = _require_dict(json.loads(event_path.read_text(encoding="utf-8")), field_name="event payload")
    pull_request = _require_dict(payload.get("pull_request"), field_name="pull_request")

    merged = pull_request.get("merged")
    if merged is not True:
        raise FinalizeError("pull_request.merged must be true for finalize")

    head = _require_dict(pull_request.get("head"), field_name="pull_request.head")
    head_repo = _require_dict(head.get("repo"), field_name="pull_request.head.repo")
    user = _require_dict(pull_request.get("user"), field_name="pull_request.user")

    return FinalizeContext(
        pr_number=_require_int(pull_request.get("number"), field_name="pull_request.number"),
        pr_url=_require_non_empty_str(pull_request.get("html_url"), field_name="pull_request.html_url"),
        merge_commit_sha=_require_non_empty_str(
            pull_request.get("merge_commit_sha"),
            field_name="pull_request.merge_commit_sha",
        ),
        source_repository_id=_require_int(head_repo.get("id"), field_name="pull_request.head.repo.id"),
        source_repository_full_name=_require_non_empty_str(
            head_repo.get("full_name"),
            field_name="pull_request.head.repo.full_name",
        ),
        github_pr_author_id=_require_int(user.get("id"), field_name="pull_request.user.id"),
        github_pr_author_login=_require_non_empty_str(
            user.get("login"),
            field_name="pull_request.user.login",
        ),
    )


def list_merged_pr_changed_files(repo: str, pr_number: int, token: str) -> list[str]:
    """List all changed file paths for one merged GitHub pull request."""
    file_paths: list[str] = []
    page = 1

    repo_quoted = parse.quote(repo, safe="")
    while True:
        url = f"https://api.github.com/repos/{repo_quoted}/pulls/{pr_number}/files?per_page=100&page={page}"
        payload = _http_get_json(url, token)
        if not isinstance(payload, list):
            raise FinalizeError(f"Unexpected GitHub file-list payload for PR #{pr_number}")

        for item in payload:
            if not isinstance(item, dict):
                continue
            filename = item.get("filename")
            if isinstance(filename, str):
                file_paths.append(filename)

        if len(payload) < 100:
            break
        page += 1

    return file_paths


def resolve_single_intake_id(changed_files: list[str]) -> str:
    """Resolve exactly one intake folder ID from merged PR changed paths."""
    intake_ids: set[str] = set()
    for changed in changed_files:
        if not changed.startswith(_INTAKE_PREFIX):
            continue
        suffix = changed[len(_INTAKE_PREFIX) :]
        intake_id = suffix.split("/", maxsplit=1)[0]
        if intake_id:
            intake_ids.add(intake_id)

    if not intake_ids:
        raise FinalizeError("No intake folder changes found under submissions/inbox/<intake_id>/")
    if len(intake_ids) != 1:
        joined = ", ".join(sorted(intake_ids))
        raise FinalizeError(f"Expected exactly one intake_id, found: {joined}")
    return next(iter(intake_ids))


def _load_json_file(path: Path, *, field_name: str) -> dict[str, Any]:
    if not path.exists():
        raise FinalizeError(f"{field_name} file is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _require_dict(payload, field_name=field_name)


def load_intake_payload(repo_root: Path, intake_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load intake submission and manifest payloads for one intake folder."""
    intake_root = repo_root / _INTAKE_PREFIX / intake_id
    submission = _load_json_file(intake_root / "submission.json", field_name="submission")
    manifest = _load_json_file(intake_root / "manifest.json", field_name="manifest")
    return submission, manifest


def _validate_intake_submission(submission: dict[str, Any]) -> None:
    missing = [field for field in _REQUIRED_SUBMISSION_FIELDS if field not in submission]
    if missing:
        joined = ", ".join(missing)
        raise FinalizeError(f"submission.json is missing required field(s): {joined}")

    leaderboard = submission.get("leaderboard")
    if leaderboard not in {"hard", "full", "both"}:
        raise FinalizeError("submission.json field 'leaderboard' must be one of: hard, full, both")


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


def run_evaluation(repo_root: Path, intake_id: str, evaluator_version: str) -> dict[str, Any]:
    """Evaluate intake task payloads and return leaderboard metric fields."""
    tasks_root = repo_root / _INTAKE_PREFIX / intake_id / _TASKS_DIR_NAME
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
        raise FinalizeError("No task directories found under submissions/inbox/<intake_id>/tasks/")

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
    return {
        "overall_score": success_count / total_count,
        "shopping_score": site_scores["shopping"],
        "reddit_score": site_scores["reddit"],
        "gitlab_score": site_scores["gitlab"],
        "wikipedia_score": site_scores["wikipedia"],
        "map_score": site_scores["map"],
        "shopping_admin_score": site_scores["shopping_admin"],
        "success_count": success_count,
        "failure_count": failure_count,
        "error_count": error_count,
        "missing_count": missing_count,
        "evaluator_version": resolved_version,
    }


def persist_payload_to_hf(
    *,
    repo_root: Path,
    intake_id: str,
    submission_id: int,
    hf_repo: str,
    hf_token: str,
) -> HFPersistResult:
    """Upload merged intake payload to canonical HF path and capture revision."""
    intake_root = repo_root / _INTAKE_PREFIX / intake_id
    if not intake_root.exists():
        raise FinalizeError(f"Intake path does not exist: {intake_root}")

    hf_path = f"submissions/{submission_id}"
    last_error: Exception | None = None
    commit_info = None
    for attempt in range(1, _NETWORK_RETRY_ATTEMPTS + 1):
        try:
            commit_info = HfApi(token=hf_token or None).upload_folder(
                repo_id=hf_repo,
                repo_type="dataset",
                folder_path=str(intake_root),
                path_in_repo=hf_path,
                commit_message=f"Finalize leaderboard submission {submission_id}",
            )
            break
        except Exception as exc:
            last_error = exc
            if attempt == _NETWORK_RETRY_ATTEMPTS:
                raise FinalizeError(f"HF upload failed after {_NETWORK_RETRY_ATTEMPTS} attempts: {last_error}") from exc
            time.sleep(_NETWORK_RETRY_DELAY_SECONDS * attempt)

    if commit_info is None:
        raise FinalizeError("HF upload did not return commit metadata")

    hf_revision = getattr(commit_info, "oid", "")
    if not isinstance(hf_revision, str) or not hf_revision:
        raise FinalizeError("Unable to capture HF revision from upload result")

    return HFPersistResult(hf_repo=hf_repo, hf_path=hf_path, hf_revision=hf_revision)


def _manifest_checksum(manifest: dict[str, Any]) -> str:
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_canonical_record(
    *,
    context: FinalizeContext,
    submission_id: int,
    intake_submission: dict[str, Any],
    intake_manifest: dict[str, Any],
    eval_summary: dict[str, Any],
    hf_result: HFPersistResult,
    now_utc: str,
) -> dict[str, Any]:
    """Build canonical accepted record payload and validate it."""
    _validate_intake_submission(intake_submission)

    payload = {
        "submission_id": submission_id,
        "github_pr_number": context.pr_number,
        "github_pr_url": context.pr_url,
        "source_repository_id": context.source_repository_id,
        "source_repository_full_name": context.source_repository_full_name,
        "github_pr_author_id": context.github_pr_author_id,
        "github_pr_author_login": context.github_pr_author_login,
        "eval_completed_at_utc": now_utc,
        "evaluator_version": eval_summary["evaluator_version"],
        "status": "accepted",
        "hf_repo": hf_result.hf_repo,
        "hf_path": hf_result.hf_path,
        "hf_revision": hf_result.hf_revision,
        "name": intake_submission["name"],
        "leaderboard": intake_submission["leaderboard"],
        "reference": intake_submission["reference"],
        "model_version": intake_submission.get("version"),
        "contact_info": intake_submission.get("contact_info"),
        "overall_score": eval_summary["overall_score"],
        "shopping_score": eval_summary["shopping_score"],
        "reddit_score": eval_summary["reddit_score"],
        "gitlab_score": eval_summary["gitlab_score"],
        "wikipedia_score": eval_summary["wikipedia_score"],
        "map_score": eval_summary["map_score"],
        "shopping_admin_score": eval_summary["shopping_admin_score"],
        "success_count": eval_summary["success_count"],
        "failure_count": eval_summary["failure_count"],
        "error_count": eval_summary["error_count"],
        "missing_count": eval_summary["missing_count"],
        "checksum": _manifest_checksum(intake_manifest),
    }
    validated = CanonicalSubmissionRecord.model_validate(payload)
    return validated.model_dump(mode="python")


def write_canonical_record(*, repo_root: Path, submission_id: int, record: dict[str, Any]) -> Path:
    """Write canonical submission record JSON to submissions/<submission_id>.json."""
    output_path = repo_root / "submissions" / f"{submission_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    validated = CanonicalSubmissionRecord.model_validate(record)
    output_path.write_text(validated.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output_path


def delete_inbox_folder(*, repo_root: Path, intake_id: str) -> Path:
    """Delete the merged intake folder after canonicalization completes."""
    inbox_path = repo_root / _INTAKE_PREFIX / intake_id
    if not inbox_path.exists():
        raise FinalizeError(f"Inbox path does not exist: {inbox_path}")
    shutil.rmtree(inbox_path)
    return inbox_path


def finalize_submission(
    *,
    repo_root: Path,
    event_path: Path,
    github_repo: str,
    github_token: str,
    hf_repo: str,
    hf_token: str,
    evaluator_version: str,
) -> FinalizeResult:
    """Finalize a merged intake PR into canonical record + HF snapshot."""
    context = parse_finalize_event(event_path)
    submission_id = context.pr_number

    changed_files = list_merged_pr_changed_files(github_repo, context.pr_number, github_token)
    intake_id = resolve_single_intake_id(changed_files)

    intake_submission, intake_manifest = load_intake_payload(repo_root, intake_id)
    eval_summary = run_evaluation(repo_root, intake_id, evaluator_version)
    hf_result = persist_payload_to_hf(
        repo_root=repo_root,
        intake_id=intake_id,
        submission_id=submission_id,
        hf_repo=hf_repo,
        hf_token=hf_token,
    )

    canonical_record = build_canonical_record(
        context=context,
        submission_id=submission_id,
        intake_submission=intake_submission,
        intake_manifest=intake_manifest,
        eval_summary=eval_summary,
        hf_result=hf_result,
        now_utc=_now_utc_z(),
    )
    record_path = write_canonical_record(repo_root=repo_root, submission_id=submission_id, record=canonical_record)
    inbox_path = delete_inbox_folder(repo_root=repo_root, intake_id=intake_id)

    return FinalizeResult(
        submission_id=submission_id,
        intake_id=intake_id,
        canonical_record_path=str(record_path),
        deleted_inbox_path=str(inbox_path),
        hf_repo=hf_result.hf_repo,
        hf_path=hf_result.hf_path,
        hf_revision=hf_result.hf_revision,
    )
