"""Reusable Hugging Face PR payload validation for leaderboard submissions."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib import error, parse, request

from pydantic import ValidationError

from webarena_verified.core.utils.network_event_utils import load_har_trace
from webarena_verified.types.leaderboard import (
    SubmissionMetadata,
    SubmissionPayloadManifest,
    SubmissionRecord,
)

REQUIRED_HF_FILES = ("payload.tar.zst", "payload.sha256", "metadata.json", "manifest.json")
SHA256_PATTERN = re.compile(r"([0-9a-f]{64})")


class SubmissionHFValidationError(Exception):
    """Raised when HF PR payload validation fails."""


def _http_get_json(url: str, token: str | None = None) -> dict:
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


def _extract_sha_from_payload_sha(payload_sha: bytes) -> str:
    """Extract hash from payload.sha256 file content."""
    decoded = payload_sha.decode("utf-8").strip()
    match = SHA256_PATTERN.search(decoded)
    if not match:
        raise SubmissionHFValidationError("payload.sha256 does not contain a valid lowercase SHA256 checksum")
    return match.group(1)


def _hf_resolve_url(repo: str, ref: str, path: str) -> str:
    """Build HF resolve URL for a file in dataset repo/ref."""
    quoted_ref = parse.quote(ref, safe="")
    quoted_path = "/".join(parse.quote(part, safe="") for part in path.split("/"))
    return f"https://huggingface.co/datasets/{repo}/resolve/{quoted_ref}/{quoted_path}?download=true"


def validate_hf_discussion_open(repo: str, hf_pr_id: int, token: str | None = None) -> None:
    """Validate HF PR/discussion is currently open."""
    repo_quoted = parse.quote(repo, safe="")
    url = f"https://huggingface.co/api/datasets/{repo_quoted}/discussions/{hf_pr_id}"
    try:
        payload = _http_get_json(url, token=token)
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SubmissionHFValidationError(f"Unable to verify Hugging Face PR open state (fail-closed): {exc}") from exc

    status = payload.get("status")
    if isinstance(status, str):
        if status.lower() != "open":
            raise SubmissionHFValidationError(f"Linked Hugging Face PR must be open, but status is '{status}'")
        return

    if payload.get("isClosed") is True or payload.get("closedAt"):
        raise SubmissionHFValidationError("Linked Hugging Face PR is not open")

    raise SubmissionHFValidationError("Unable to determine Hugging Face PR open state from API response (fail-closed)")


def _extract_payload_archive(archive_bytes: bytes, output_dir: Path) -> None:
    """Extract payload.tar.zst bytes into output_dir using system tar."""
    archive_path = output_dir / "payload.tar.zst"
    archive_path.write_bytes(archive_bytes)

    cmd = ["tar", "--zstd", "-xf", str(archive_path), "-C", str(output_dir)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "unknown tar error"
        raise SubmissionHFValidationError(f"payload.tar.zst extraction failed: {stderr}") from exc


def _validate_task_dir(task_dir: Path) -> None:
    """Validate per-task folder with .missing and HAR invariants."""
    children = [item for item in task_dir.iterdir() if item.name != "__MACOSX"]
    names = {item.name for item in children}

    if ".missing" in names:
        if names != {".missing"}:
            raise SubmissionHFValidationError(
                f"Task {task_dir.name} is invalid: '.missing' cannot coexist with other files"
            )
        missing_file = task_dir / ".missing"
        if missing_file.stat().st_size != 0:
            raise SubmissionHFValidationError(f"Task {task_dir.name} .missing file must be empty")
        return

    if "agent_response.json" not in names or "network.har" not in names:
        raise SubmissionHFValidationError(
            f"Task {task_dir.name} must contain agent_response.json + network.har or only .missing"
        )

    try:
        json.loads((task_dir / "agent_response.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SubmissionHFValidationError(f"Task {task_dir.name} has invalid agent_response.json: {exc}") from exc

    try:
        load_har_trace(task_dir / "network.har")
    except (ValueError, json.JSONDecodeError) as exc:
        raise SubmissionHFValidationError(f"Task {task_dir.name} has invalid network.har: {exc}") from exc


def _validate_extracted_payload_structure(extract_root: Path) -> None:
    """Validate extracted payload task structure and HAR policy."""
    top_level_dirs = [entry for entry in extract_root.iterdir() if entry.is_dir()]
    if not top_level_dirs:
        raise SubmissionHFValidationError("payload.tar.zst must contain at least one task directory")

    for task_dir in sorted(top_level_dirs, key=lambda p: p.name):
        if not task_dir.name.isdigit():
            raise SubmissionHFValidationError(
                f"Invalid top-level directory '{task_dir.name}': expected numeric task_id directory"
            )
        _validate_task_dir(task_dir)


def validate_hf_payload(record: SubmissionRecord) -> None:
    """Fetch and validate required payload artifacts from linked HF PR."""
    ref = f"refs/pr/{record.hf_pr_id}"
    submission_root = f"submissions/accepted/{record.submission_id}"

    file_bytes: dict[str, bytes] = {}
    for file_name in REQUIRED_HF_FILES:
        remote_path = f"{submission_root}/{file_name}"
        file_url = _hf_resolve_url(record.hf_repo, ref, remote_path)
        try:
            file_bytes[file_name] = _http_get_bytes(file_url)
        except (error.URLError, TimeoutError) as exc:
            raise SubmissionHFValidationError(
                f"Missing or inaccessible HF payload file '{remote_path}' from linked PR: {exc}"
            ) from exc

    payload_archive = file_bytes["payload.tar.zst"]
    payload_sha256 = _extract_sha_from_payload_sha(file_bytes["payload.sha256"])
    computed_sha256 = hashlib.sha256(payload_archive).hexdigest()
    if payload_sha256 != computed_sha256:
        raise SubmissionHFValidationError(
            "payload checksum mismatch: payload.sha256 does not match payload.tar.zst content"
        )

    metadata_data = json.loads(file_bytes["metadata.json"].decode("utf-8"))
    manifest_data = json.loads(file_bytes["manifest.json"].decode("utf-8"))

    try:
        metadata = SubmissionMetadata.model_validate(metadata_data)
    except ValidationError as exc:
        raise SubmissionHFValidationError(f"Invalid HF metadata.json schema: {exc}") from exc

    try:
        manifest = SubmissionPayloadManifest.model_validate(manifest_data)
    except ValidationError as exc:
        raise SubmissionHFValidationError(f"Invalid HF manifest.json schema: {exc}") from exc

    if metadata.submission_id != record.submission_id:
        raise SubmissionHFValidationError("HF metadata.json submission_id does not match submission record")
    if manifest.submission_id != record.submission_id:
        raise SubmissionHFValidationError("HF manifest.json submission_id does not match submission record")
    if manifest.hf_pr_id is None or manifest.hf_pr_url is None:
        raise SubmissionHFValidationError(
            "HF manifest must include non-null hf_pr_id and hf_pr_url for uploaded submissions"
        )
    if manifest.hf_pr_id != record.hf_pr_id or manifest.hf_pr_url != record.hf_pr_url:
        raise SubmissionHFValidationError("HF manifest hf_pr_id/hf_pr_url must match submission record linkage")
    if manifest.archive_sha256 != payload_sha256:
        raise SubmissionHFValidationError("HF manifest archive_sha256 does not match payload.sha256")
    if manifest.archive_size_bytes != len(payload_archive):
        raise SubmissionHFValidationError("HF manifest archive_size_bytes does not match payload.tar.zst size")

    with tempfile.TemporaryDirectory() as tmp_dir:
        extract_root = Path(tmp_dir)
        _extract_payload_archive(payload_archive, extract_root)
        _validate_extracted_payload_structure(extract_root)


def validate_hf_submission_record(record: SubmissionRecord, token: str | None = None) -> None:
    """Run full HF validation checks for one linked submission record."""
    validate_hf_discussion_open(record.hf_repo, record.hf_pr_id, token=token)
    validate_hf_payload(record)
