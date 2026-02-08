"""Reusable Hugging Face PR payload validation for leaderboard submissions."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib import error, parse

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import EntryNotFoundError, HfHubHTTPError, RepositoryNotFoundError, RevisionNotFoundError
from pydantic import ValidationError

import dev.leaderboard.constants as leaderboard_constants
from dev.leaderboard.models import SubmissionArtifacts, SubmissionManifest, SubmissionMetadata, SubmissionRecord
from dev.leaderboard.utils import http_get_json

LOGGER = logging.getLogger(__name__)


class SubmissionHFValidationError(Exception):
    """Raised when HF PR payload validation fails."""


def validate_hf_discussion_open(repo: str, hf_pr_id: int, token: str | None = None) -> None:
    """Validate HF PR/discussion is currently open."""
    LOGGER.info("Validating Hugging Face discussion state for repo=%s pr_id=%s", repo, hf_pr_id)
    repo_quoted = parse.quote(repo, safe="/")
    url = f"https://huggingface.co/api/datasets/{repo_quoted}/discussions/{hf_pr_id}?diff=1"
    try:
        payload = http_get_json(url, token=token)
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SubmissionHFValidationError(f"Unable to verify Hugging Face PR open state (fail-closed): {exc}") from exc

    status = payload.get("status")
    if isinstance(status, str):
        if status.lower() != "open":
            raise SubmissionHFValidationError(f"Linked Hugging Face PR must be open, but status is '{status}'")
        LOGGER.info("Hugging Face discussion is open")
        return

    if payload.get("isClosed") is True or payload.get("closedAt"):
        raise SubmissionHFValidationError("Linked Hugging Face PR is not open")

    raise SubmissionHFValidationError("Unable to determine Hugging Face PR open state from API response (fail-closed)")


def _extract_payload_archive(archive_bytes: bytes, output_dir: Path) -> None:
    """Extract submission archive bytes into output_dir using system tar."""
    LOGGER.info(
        "Extracting archive %s into temporary directory",
        leaderboard_constants.HF_SUBMISSION_ARCHIVE_FILE,
    )
    archive_path = output_dir / leaderboard_constants.HF_SUBMISSION_ARCHIVE_FILE
    archive_path.write_bytes(archive_bytes)

    cmd = ["tar", "-xzf", str(archive_path), "-C", str(output_dir)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "unknown tar error"
        raise SubmissionHFValidationError(
            f"{leaderboard_constants.HF_SUBMISSION_ARCHIVE_FILE} extraction failed: {stderr}"
        ) from exc


def _validate_archive_members_before_extraction(archive_bytes: bytes) -> None:
    """Validate archive member paths and allowed task-level files before extraction."""
    if len(archive_bytes) > leaderboard_constants.HF_SUBMISSION_ARCHIVE_MAX_BYTES:
        raise SubmissionHFValidationError(
            f"{leaderboard_constants.HF_SUBMISSION_ARCHIVE_FILE} exceeds max size "
            f"{leaderboard_constants.HF_SUBMISSION_ARCHIVE_MAX_BYTES} bytes"
        )

    try:
        tar = tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise SubmissionHFValidationError(
            f"{leaderboard_constants.HF_SUBMISSION_ARCHIVE_FILE} is not a valid gzip tar archive: {exc}"
        ) from exc

    allowed_task_files = {
        leaderboard_constants.TASK_AGENT_RESPONSE_FILE,
        leaderboard_constants.TASK_NETWORK_HAR_FILE,
        leaderboard_constants.TASK_MISSING_SENTINEL_FILE,
    }
    task_entries: dict[str, set[str]] = {}
    with tar:
        for member in tar.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise SubmissionHFValidationError(
                    f"{leaderboard_constants.HF_SUBMISSION_ARCHIVE_FILE} contains unsafe path '{member.name}'"
                )
            if member.issym() or member.islnk() or member.ischr() or member.isblk() or member.isfifo():
                raise SubmissionHFValidationError(
                    f"{leaderboard_constants.HF_SUBMISSION_ARCHIVE_FILE} contains unsupported entry type '{member.name}'"
                )
            if member.isdir():
                continue

            parts = [p for p in member_path.parts if p]
            if len(parts) != 2:
                raise SubmissionHFValidationError(
                    f"Invalid archive path '{member.name}': expected '<task_id>/<file>'"
                )
            task_id, file_name = parts
            if not task_id.isdigit():
                raise SubmissionHFValidationError(
                    f"Invalid archive path '{member.name}': task_id directory must be numeric"
                )
            if file_name not in allowed_task_files:
                raise SubmissionHFValidationError(
                    f"Invalid archive path '{member.name}': file '{file_name}' is not allowed"
                )
            task_entries.setdefault(task_id, set()).add(file_name)

    if not task_entries:
        raise SubmissionHFValidationError(
            f"{leaderboard_constants.HF_SUBMISSION_ARCHIVE_FILE} must contain at least one task directory"
        )

    for task_id, names in task_entries.items():
        if leaderboard_constants.TASK_MISSING_SENTINEL_FILE in names:
            if names != {leaderboard_constants.TASK_MISSING_SENTINEL_FILE}:
                raise SubmissionHFValidationError(
                    f"Task {task_id} is invalid: '{leaderboard_constants.TASK_MISSING_SENTINEL_FILE}' cannot coexist "
                    "with other files"
                )
            continue
        if {
            leaderboard_constants.TASK_AGENT_RESPONSE_FILE,
            leaderboard_constants.TASK_NETWORK_HAR_FILE,
        } - names:
            raise SubmissionHFValidationError(
                f"Task {task_id} must contain {leaderboard_constants.TASK_AGENT_RESPONSE_FILE} + "
                f"{leaderboard_constants.TASK_NETWORK_HAR_FILE} or only "
                f"{leaderboard_constants.TASK_MISSING_SENTINEL_FILE}"
            )


def _validate_task_dir(task_dir: Path) -> None:
    """Validate per-task folder with missing-sentinel and HAR invariants."""
    LOGGER.debug("Validating task directory: %s", task_dir.name)
    children = [item for item in task_dir.iterdir() if item.name != "__MACOSX"]
    names = {item.name for item in children}

    if leaderboard_constants.TASK_MISSING_SENTINEL_FILE in names:
        if names != {leaderboard_constants.TASK_MISSING_SENTINEL_FILE}:
            raise SubmissionHFValidationError(
                f"Task {task_dir.name} is invalid: '{leaderboard_constants.TASK_MISSING_SENTINEL_FILE}' "
                "cannot coexist with other files"
            )
        missing_file = task_dir / leaderboard_constants.TASK_MISSING_SENTINEL_FILE
        if missing_file.stat().st_size != 0:
            raise SubmissionHFValidationError(
                f"Task {task_dir.name} {leaderboard_constants.TASK_MISSING_SENTINEL_FILE} file must be empty"
            )
        return

    if (
        leaderboard_constants.TASK_AGENT_RESPONSE_FILE not in names
        or leaderboard_constants.TASK_NETWORK_HAR_FILE not in names
    ):
        raise SubmissionHFValidationError(
            f"Task {task_dir.name} must contain {leaderboard_constants.TASK_AGENT_RESPONSE_FILE} "
            f"+ {leaderboard_constants.TASK_NETWORK_HAR_FILE} or only "
            f"{leaderboard_constants.TASK_MISSING_SENTINEL_FILE}"
        )

    try:
        json.loads((task_dir / leaderboard_constants.TASK_AGENT_RESPONSE_FILE).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SubmissionHFValidationError(
            f"Task {task_dir.name} has invalid {leaderboard_constants.TASK_AGENT_RESPONSE_FILE}: {exc}"
        ) from exc

    network_har = task_dir / leaderboard_constants.TASK_NETWORK_HAR_FILE
    try:
        json.loads(network_har.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SubmissionHFValidationError(
            f"Task {task_dir.name} has invalid {leaderboard_constants.TASK_NETWORK_HAR_FILE}: {exc}"
        ) from exc


def _validate_extracted_payload_structure(extract_root: Path) -> None:
    """Validate extracted payload task structure and HAR policy."""
    LOGGER.info("Validating extracted archive structure under %s", extract_root)
    top_level_dirs = [entry for entry in extract_root.iterdir() if entry.is_dir()]
    if not top_level_dirs:
        raise SubmissionHFValidationError(
            f"{leaderboard_constants.HF_SUBMISSION_ARCHIVE_FILE} must contain at least one task directory"
        )

    for task_dir in sorted(top_level_dirs, key=lambda p: p.name):
        if not task_dir.name.isdigit():
            raise SubmissionHFValidationError(
                f"Invalid top-level directory '{task_dir.name}': expected numeric task_id directory"
            )
        _validate_task_dir(task_dir)
    LOGGER.info("Validated %s extracted task directory(ies)", len(top_level_dirs))


def _download_required_payload_files(
    record: SubmissionRecord, artifacts: SubmissionArtifacts, token: str | None = None
) -> dict[str, bytes]:
    """Download all required HF payload files for a submission record."""
    file_bytes: dict[str, bytes] = {}
    for file_name in (artifacts.archive_file, artifacts.metadata_file):
        remote_path = artifacts.remote_path_for(file_name)
        LOGGER.info("Fetching payload file: %s", remote_path)
        try:
            LOGGER.debug(
                "Downloading HF artifact via hub api repo=%s ref=%s path=%s",
                record.hf_repo,
                artifacts.ref,
                remote_path,
            )
            downloaded_path = hf_hub_download(
                repo_id=record.hf_repo,
                repo_type="dataset",
                revision=artifacts.ref,
                filename=remote_path,
                token=token,
            )
            file_bytes[file_name] = Path(downloaded_path).read_bytes()
        except (EntryNotFoundError, RepositoryNotFoundError, RevisionNotFoundError, HfHubHTTPError, OSError) as exc:
            raise SubmissionHFValidationError(
                f"Missing or inaccessible HF payload file '{remote_path}' from linked PR: {exc}"
            ) from exc
    return file_bytes


def _validate_submission_root_inputs_exact(
    record: SubmissionRecord, artifacts: SubmissionArtifacts, token: str | None = None
) -> None:
    expected_files = set(leaderboard_constants.HF_REQUIRED_SUBMISSION_FILES)
    api = HfApi(token=token)
    found_files: set[str] = set()
    try:
        entries = api.list_repo_tree(
            repo_id=record.hf_repo,
            repo_type="dataset",
            revision=artifacts.ref,
            path_in_repo=artifacts.submission_root,
            recursive=False,
            token=token,
        )
        for entry in entries:
            entry_path = getattr(entry, "path", None)
            if not entry_path:
                continue
            entry_path_obj = Path(entry_path)
            if entry_path_obj.parent.as_posix() != artifacts.submission_root:
                continue
            found_files.add(entry_path_obj.name)
    except (RepositoryNotFoundError, RevisionNotFoundError, HfHubHTTPError, OSError) as exc:
        raise SubmissionHFValidationError(
            f"Unable to list payload files under '{artifacts.submission_root}': {exc}"
        ) from exc

    if found_files != expected_files:
        missing = sorted(expected_files - found_files)
        extra = sorted(found_files - expected_files)
        raise SubmissionHFValidationError(
            f"Submission payload files under '{artifacts.submission_root}' must be exactly "
            f"{sorted(expected_files)} (missing={missing or []}, extra={extra or []})"
        )


def _compute_submission_checksums(payload_archive: bytes, metadata_bytes: bytes) -> tuple[str, str, str]:
    payload_sha256 = hashlib.sha256(payload_archive).hexdigest()
    metadata_sha256 = hashlib.sha256(metadata_bytes).hexdigest()
    submission_checksum = hashlib.sha256(f"{payload_sha256}:{metadata_sha256}".encode("utf-8")).hexdigest()
    return payload_sha256, metadata_sha256, submission_checksum


def validate_hf_payload(record: SubmissionRecord, token: str | None = None) -> None:
    """Fetch and validate required payload artifacts from linked HF PR."""
    LOGGER.info("Validating HF payload artifacts for submission_id=%s", record.submission_id)
    artifacts = SubmissionArtifacts.from_record(record)
    _validate_submission_root_inputs_exact(record, artifacts, token=token)

    file_bytes = _download_required_payload_files(record, artifacts, token=token)

    payload_archive = file_bytes[artifacts.archive_file]
    metadata_bytes = file_bytes[artifacts.metadata_file]
    _validate_archive_members_before_extraction(payload_archive)
    payload_sha256, metadata_sha256, submission_checksum = _compute_submission_checksums(payload_archive, metadata_bytes)

    metadata_data = json.loads(metadata_bytes.decode("utf-8"))

    try:
        metadata = SubmissionMetadata.model_validate(metadata_data)
    except ValidationError as exc:
        raise SubmissionHFValidationError(
            f"Invalid HF {leaderboard_constants.HF_SUBMISSION_METADATA_FILE} schema: {exc}"
        ) from exc

    if metadata.submission_id != record.submission_id:
        raise SubmissionHFValidationError(
            f"HF {leaderboard_constants.HF_SUBMISSION_METADATA_FILE} submission_id does not match submission record"
        )

    generated_manifest = SubmissionManifest(
        manifest_version=1,
        submission_id=metadata.submission_id,
        hf_pr_id=record.hf_pr_id,
        hf_pr_url=record.hf_pr_url,
        payload_file=leaderboard_constants.HF_SUBMISSION_ARCHIVE_FILE,
        payload_sha256=payload_sha256,
        payload_size_bytes=len(payload_archive),
        metadata_file=leaderboard_constants.HF_SUBMISSION_METADATA_FILE,
        metadata_sha256=metadata_sha256,
        metadata_size_bytes=len(metadata_bytes),
        submission_checksum=submission_checksum,
    ).model_dump(mode="json")
    LOGGER.info("Generated submission manifest with checksum=%s", generated_manifest["submission_checksum"])

    with tempfile.TemporaryDirectory() as tmp_dir:
        extract_root = Path(tmp_dir)
        _extract_payload_archive(payload_archive, extract_root)
        _validate_extracted_payload_structure(extract_root)
    LOGGER.info("HF payload archive content validation passed")


def validate_hf_submission_record(record: SubmissionRecord, token: str | None = None) -> None:
    """Run full HF validation checks for one linked submission record."""
    LOGGER.info("Starting full HF submission validation for submission_id=%s", record.submission_id)
    validate_hf_discussion_open(record.hf_repo, record.hf_pr_id, token=token)
    validate_hf_payload(record, token=token)
    LOGGER.info("Finished full HF submission validation for submission_id=%s", record.submission_id)
