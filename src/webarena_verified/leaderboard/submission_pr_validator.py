"""Submission PR validator for leaderboard Track B CI."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from pydantic import ValidationError

from webarena_verified.core.utils.network_event_utils import load_har_trace
from webarena_verified.types.leaderboard import (
    SubmissionMetadata,
    SubmissionPayloadManifest,
    SubmissionRecord,
    SubmissionStatus,
)

PR_TITLE_PREFIX = "Leaderboard Submission: "
PENDING_PREFIX = "leaderboard/data/submissions/pending/"
PROCESSED_PREFIX = "leaderboard/data/submissions/processed/"
REQUIRED_HF_FILES = ("payload.tar.zst", "payload.sha256", "metadata.json", "manifest.json")
SHA256_PATTERN = re.compile(r"([0-9a-f]{64})")


class SubmissionPRValidationError(Exception):
    """Raised when submission PR validation fails."""


@dataclass(frozen=True)
class ChangedFile:
    """Single changed file from git diff."""

    status: str
    path: str


@dataclass(frozen=True)
class SubmissionPRContext:
    """Input context for submission PR validation."""

    repo_root: Path
    base_sha: str
    head_sha: str
    repo: str
    actor: str
    pr_number: int
    pr_title: str
    github_token: str


def _parse_iso_utc(value: str) -> dt.datetime:
    """Parse ISO timestamp with optional trailing Z into UTC aware datetime."""
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def _http_get_json(url: str, token: str | None = None) -> dict[str, Any]:
    """Fetch a JSON payload from HTTP endpoint."""
    req = request.Request(url)
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get_bytes(url: str) -> bytes:
    """Fetch raw bytes from HTTP endpoint."""
    req = request.Request(url)
    with request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _run_git_diff(base_sha: str, head_sha: str, repo_root: Path) -> list[ChangedFile]:
    """Return list of changed files for PR diff."""
    cmd = ["git", "diff", "--name-status", "--no-renames", f"{base_sha}..{head_sha}"]
    result = subprocess.run(cmd, cwd=repo_root, check=True, capture_output=True, text=True)

    changed_files: list[ChangedFile] = []
    for raw_line in result.stdout.splitlines():
        if not raw_line.strip():
            continue
        status, path = raw_line.split("\t", maxsplit=1)
        changed_files.append(ChangedFile(status=status.strip(), path=path.strip()))
    return changed_files


def _validate_changed_files(changed_files: list[ChangedFile]) -> str:
    """Validate file scope and exactly-one-record rule."""
    if not changed_files:
        raise SubmissionPRValidationError("No files changed in PR diff")

    invalid_scope = [cf.path for cf in changed_files if not cf.path.startswith((PENDING_PREFIX, PROCESSED_PREFIX))]
    if invalid_scope:
        joined = ", ".join(sorted(invalid_scope))
        raise SubmissionPRValidationError(
            "Submission PRs may only change control records under leaderboard/data/submissions/. "
            f"Invalid paths: {joined}"
        )

    json_files = [cf for cf in changed_files if cf.path.endswith(".json")]
    if len(json_files) != 1 or len(changed_files) != 1:
        raise SubmissionPRValidationError(
            "Submission PRs must change exactly one submission control JSON and no other files"
        )

    changed = json_files[0]
    if changed.status not in {"A", "M"}:
        raise SubmissionPRValidationError(
            f"Submission control JSON must be added or modified, got git status '{changed.status}'"
        )

    return changed.path


def _validate_path_status_invariants(record: SubmissionRecord, control_path: str) -> None:
    """Validate path/status invariants from the spec."""
    if control_path.startswith(PENDING_PREFIX) and record.status != SubmissionStatus.PENDING:
        raise SubmissionPRValidationError("Path/status invariant failed: pending/<id>.json must have status='pending'")

    if control_path.startswith(PROCESSED_PREFIX) and record.status not in {
        SubmissionStatus.ACCEPTED,
        SubmissionStatus.REJECTED,
    }:
        raise SubmissionPRValidationError(
            "Path/status invariant failed: processed/<id>.json must have status in {'accepted','rejected'}"
        )


def _load_submission_record(repo_root: Path, control_path: str) -> SubmissionRecord:
    """Load and validate control record JSON from repository file."""
    control_file = repo_root / control_path
    if not control_file.exists():
        raise SubmissionPRValidationError(f"Submission control file is missing: {control_path}")

    payload = json.loads(control_file.read_text(encoding="utf-8"))
    try:
        record = SubmissionRecord.model_validate(payload)
    except ValidationError as exc:
        raise SubmissionPRValidationError(f"Invalid submission record schema in {control_path}: {exc}") from exc

    file_submission_id = Path(control_path).stem
    if record.submission_id != file_submission_id:
        raise SubmissionPRValidationError(
            "submission_id mismatch: file name and submission record must match "
            f"(file='{file_submission_id}', record='{record.submission_id}')"
        )

    _validate_path_status_invariants(record, control_path)
    return record


def _extract_sha_from_payload_sha(payload_sha: bytes) -> str:
    """Extract hash from payload.sha256 file content."""
    decoded = payload_sha.decode("utf-8").strip()
    match = SHA256_PATTERN.search(decoded)
    if not match:
        raise SubmissionPRValidationError("payload.sha256 does not contain a valid lowercase SHA256 checksum")
    return match.group(1)


def _hf_resolve_url(repo: str, ref: str, path: str) -> str:
    """Build HF resolve URL for a file in dataset repo/ref."""
    quoted_ref = parse.quote(ref, safe="")
    quoted_path = "/".join(parse.quote(part, safe="") for part in path.split("/"))
    return f"https://huggingface.co/datasets/{repo}/resolve/{quoted_ref}/{quoted_path}?download=true"


def _validate_hf_discussion_open(repo: str, hf_pr_id: int) -> None:
    """Validate HF PR/discussion is currently open."""
    repo_quoted = parse.quote(repo, safe="")
    url = f"https://huggingface.co/api/datasets/{repo_quoted}/discussions/{hf_pr_id}"
    try:
        payload = _http_get_json(url)
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SubmissionPRValidationError(f"Unable to verify Hugging Face PR open state (fail-closed): {exc}") from exc

    status = payload.get("status")
    if isinstance(status, str):
        if status.lower() != "open":
            raise SubmissionPRValidationError(f"Linked Hugging Face PR must be open, but status is '{status}'")
        return

    if payload.get("isClosed") is True or payload.get("closedAt"):
        raise SubmissionPRValidationError("Linked Hugging Face PR is not open")

    raise SubmissionPRValidationError("Unable to determine Hugging Face PR open state from API response (fail-closed)")


def _extract_payload_archive(archive_bytes: bytes, output_dir: Path) -> None:
    """Extract payload.tar.zst bytes into output_dir using system tar."""
    archive_path = output_dir / "payload.tar.zst"
    archive_path.write_bytes(archive_bytes)

    cmd = ["tar", "--zstd", "-xf", str(archive_path), "-C", str(output_dir)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "unknown tar error"
        raise SubmissionPRValidationError(f"payload.tar.zst extraction failed: {stderr}") from exc


def _validate_task_dir(task_dir: Path) -> None:
    """Validate per-task folder with .missing and HAR invariants."""
    children = [item for item in task_dir.iterdir() if item.name != "__MACOSX"]
    names = {item.name for item in children}

    if ".missing" in names:
        if names != {".missing"}:
            raise SubmissionPRValidationError(
                f"Task {task_dir.name} is invalid: '.missing' cannot coexist with other files"
            )
        missing_file = task_dir / ".missing"
        if missing_file.stat().st_size != 0:
            raise SubmissionPRValidationError(f"Task {task_dir.name} .missing file must be empty")
        return

    if "agent_response.json" not in names or "network.har" not in names:
        raise SubmissionPRValidationError(
            f"Task {task_dir.name} must contain agent_response.json + network.har or only .missing"
        )

    try:
        json.loads((task_dir / "agent_response.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SubmissionPRValidationError(f"Task {task_dir.name} has invalid agent_response.json: {exc}") from exc

    try:
        load_har_trace(task_dir / "network.har")
    except (ValueError, json.JSONDecodeError) as exc:
        raise SubmissionPRValidationError(f"Task {task_dir.name} has invalid network.har: {exc}") from exc


def _validate_extracted_payload_structure(extract_root: Path) -> None:
    """Validate extracted payload task structure and HAR policy."""
    top_level_dirs = [entry for entry in extract_root.iterdir() if entry.is_dir()]
    if not top_level_dirs:
        raise SubmissionPRValidationError("payload.tar.zst must contain at least one task directory")

    for task_dir in sorted(top_level_dirs, key=lambda p: p.name):
        if not task_dir.name.isdigit():
            raise SubmissionPRValidationError(
                f"Invalid top-level directory '{task_dir.name}': expected numeric task_id directory"
            )
        _validate_task_dir(task_dir)


def _validate_hf_payload(record: SubmissionRecord) -> None:
    """Fetch and validate all required payload artifacts from linked HF PR."""
    ref = f"refs/pr/{record.hf_pr_id}"
    submission_root = f"submissions/accepted/{record.submission_id}"

    file_bytes: dict[str, bytes] = {}
    for file_name in REQUIRED_HF_FILES:
        remote_path = f"{submission_root}/{file_name}"
        file_url = _hf_resolve_url(record.hf_repo, ref, remote_path)
        try:
            file_bytes[file_name] = _http_get_bytes(file_url)
        except (error.URLError, TimeoutError) as exc:
            raise SubmissionPRValidationError(
                f"Missing or inaccessible HF payload file '{remote_path}' from linked PR: {exc}"
            ) from exc

    payload_archive = file_bytes["payload.tar.zst"]
    payload_sha256 = _extract_sha_from_payload_sha(file_bytes["payload.sha256"])
    computed_sha256 = hashlib.sha256(payload_archive).hexdigest()
    if payload_sha256 != computed_sha256:
        raise SubmissionPRValidationError(
            "payload checksum mismatch: payload.sha256 does not match payload.tar.zst content"
        )

    metadata_data = json.loads(file_bytes["metadata.json"].decode("utf-8"))
    manifest_data = json.loads(file_bytes["manifest.json"].decode("utf-8"))

    try:
        metadata = SubmissionMetadata.model_validate(metadata_data)
    except ValidationError as exc:
        raise SubmissionPRValidationError(f"Invalid HF metadata.json schema: {exc}") from exc

    try:
        manifest = SubmissionPayloadManifest.model_validate(manifest_data)
    except ValidationError as exc:
        raise SubmissionPRValidationError(f"Invalid HF manifest.json schema: {exc}") from exc

    if metadata.submission_id != record.submission_id:
        raise SubmissionPRValidationError("HF metadata.json submission_id does not match submission record")

    if manifest.submission_id != record.submission_id:
        raise SubmissionPRValidationError("HF manifest.json submission_id does not match submission record")

    if manifest.hf_pr_id is None or manifest.hf_pr_url is None:
        raise SubmissionPRValidationError(
            "HF manifest must include non-null hf_pr_id and hf_pr_url for uploaded submissions"
        )

    if manifest.hf_pr_id != record.hf_pr_id or manifest.hf_pr_url != record.hf_pr_url:
        raise SubmissionPRValidationError("HF manifest hf_pr_id/hf_pr_url must match submission record linkage")

    if manifest.archive_sha256 != payload_sha256:
        raise SubmissionPRValidationError("HF manifest archive_sha256 does not match payload.sha256")

    if manifest.archive_size_bytes != len(payload_archive):
        raise SubmissionPRValidationError("HF manifest archive_size_bytes does not match payload.tar.zst size")

    with tempfile.TemporaryDirectory() as tmp_dir:
        extract_root = Path(tmp_dir)
        _extract_payload_archive(payload_archive, extract_root)
        _validate_extracted_payload_structure(extract_root)


def _list_all_repo_pulls(repo: str, token: str) -> list[dict[str, Any]]:
    """List pull requests from GitHub REST API with pagination."""
    pulls: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/pulls?state=all&per_page=100&page={page}"
        data = _http_get_json(url, token=token)
        if not isinstance(data, list):
            raise SubmissionPRValidationError("Unexpected GitHub API response while listing PRs")

        pulls.extend(data)
        if len(data) < 100:
            break
        page += 1
    return pulls


def _enforce_github_rate_limits(
    repo: str,
    actor: str,
    current_pr_number: int,
    token: str,
    now_utc: dt.datetime,
) -> None:
    """Enforce author rate limits using GitHub API (fail closed)."""
    try:
        pulls = _list_all_repo_pulls(repo, token)
    except Exception as exc:
        raise SubmissionPRValidationError(
            f"Unable to evaluate GitHub actor rate limits due to API error (fail-closed): {exc}"
        ) from exc

    actor_submission_prs = [
        pr
        for pr in pulls
        if pr.get("user", {}).get("login") == actor and str(pr.get("title", "")).startswith(PR_TITLE_PREFIX)
    ]

    open_submission_prs = [
        pr for pr in actor_submission_prs if pr.get("state") == "open" and pr.get("number") != current_pr_number
    ]
    if open_submission_prs:
        numbers = ", ".join(str(pr["number"]) for pr in open_submission_prs)
        raise SubmissionPRValidationError(
            f"Rate limit exceeded: actor already has an open submission PR (PR number(s): {numbers})"
        )

    window_start = now_utc - dt.timedelta(hours=24)
    recent_submission_prs = []
    for pr in actor_submission_prs:
        if pr.get("number") == current_pr_number:
            continue
        created_at = pr.get("created_at")
        if not created_at:
            continue
        created_dt = _parse_iso_utc(str(created_at))
        if created_dt >= window_start:
            recent_submission_prs.append(created_dt)

    if recent_submission_prs:
        next_allowed = max(recent_submission_prs) + dt.timedelta(hours=24)
        next_allowed_str = next_allowed.strftime("%Y-%m-%dT%H:%M:%SZ")
        raise SubmissionPRValidationError(
            "Rate limit exceeded: only one new submission PR is allowed per rolling 24h window. "
            f"Next allowed UTC timestamp: {next_allowed_str}"
        )


def validate_submission_pr(context: SubmissionPRContext, now_utc: dt.datetime | None = None) -> None:
    """Run full submission PR validation."""
    if not context.pr_title.startswith(PR_TITLE_PREFIX):
        raise SubmissionPRValidationError(f"PR title must start with exact prefix '{PR_TITLE_PREFIX}'")

    changed_files = _run_git_diff(base_sha=context.base_sha, head_sha=context.head_sha, repo_root=context.repo_root)
    control_path = _validate_changed_files(changed_files)
    record = _load_submission_record(context.repo_root, control_path)

    _validate_hf_discussion_open(record.hf_repo, record.hf_pr_id)
    _validate_hf_payload(record)

    current_time = now_utc or dt.datetime.now(dt.UTC)
    _enforce_github_rate_limits(
        repo=context.repo,
        actor=context.actor,
        current_pr_number=context.pr_number,
        token=context.github_token,
        now_utc=current_time,
    )


def _build_failure_report(error_message: str) -> str:
    """Build markdown report for workflow summaries/comments."""
    return (
        "## Submission PR Validation Failed\n\n"
        f"- Error: {error_message}\n"
        "- Required: exactly one submission control JSON change under "
        "`leaderboard/data/submissions/`, valid path/status invariants, valid linked HF payload PR (open), "
        "checksum/archive/task/HAR checks, and GitHub actor rate-limit compliance.\n"
    )


def main() -> int:
    """CLI entrypoint for GitHub Actions workflow."""
    parser = argparse.ArgumentParser(description="Validate leaderboard submission PR")
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--repo", required=True, help="GitHub repo in owner/name format")
    parser.add_argument("--actor", required=True, help="GitHub actor login")
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--pr-title", required=True)
    parser.add_argument("--github-token", required=True)
    parser.add_argument("--report-file", required=False)
    args = parser.parse_args()

    try:
        validate_submission_pr(
            SubmissionPRContext(
                repo_root=Path.cwd(),
                base_sha=args.base_sha,
                head_sha=args.head_sha,
                repo=args.repo,
                actor=args.actor,
                pr_number=args.pr_number,
                pr_title=args.pr_title,
                github_token=args.github_token,
            ),
        )
    except SubmissionPRValidationError as exc:
        message = str(exc)
        report = _build_failure_report(message)
        print(report)
        if args.report_file:
            Path(args.report_file).write_text(report, encoding="utf-8")
        return 1

    success_report = "## Submission PR Validation Passed\n\nAll submission PR checks passed.\n"
    print(success_report)
    if args.report_file:
        Path(args.report_file).write_text(success_report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
