"""PR gate intake validators for submissions/inbox payloads."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from dev.leaderboard.constants import TASK_AGENT_RESPONSE_FILE, TASK_MISSING_SENTINEL_FILE, TASK_NETWORK_HAR_FILE
from webarena_verified.types.leaderboard import SubmissionLeaderboard
from webarena_verified.types.leaderboard._validators import validate_rfc3339_utc_z, validate_sha256_hex

INBOX_PREFIX = "submissions/inbox/"


class PRGateValidationError(Exception):
    """Raised when PR gate intake validation fails."""


class IntakeSubmission(BaseModel):
    """Intake payload contract for submission.json."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    leaderboard: SubmissionLeaderboard
    reference: str = Field(min_length=1)
    created_at_utc: str
    packaging_summary: dict[str, Any]
    version: str | None = None
    contact_info: str | None = None

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("reference must be an http(s) URL")
        return value

    @field_validator("created_at_utc")
    @classmethod
    def validate_created_at_utc(cls, value: str) -> str:
        return validate_rfc3339_utc_z(value, "created_at_utc")


class IntakeManifestFile(BaseModel):
    """Single manifest file entry."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    sha256: str
    size_bytes: int = Field(ge=0)

    @field_validator("sha256")
    @classmethod
    def validate_entry_sha256(cls, value: str) -> str:
        return validate_sha256_hex(value, "sha256")


class IntakeManifest(BaseModel):
    """Intake payload contract for manifest.json."""

    model_config = ConfigDict(extra="forbid")

    created_at_utc: str
    schema_version: str = Field(min_length=1)
    files: list[IntakeManifestFile] = Field(min_length=1)

    @field_validator("created_at_utc")
    @classmethod
    def validate_created_at_utc(cls, value: str) -> str:
        return validate_rfc3339_utc_z(value, "created_at_utc")

    @field_validator("files")
    @classmethod
    def validate_unique_paths(cls, files: list[IntakeManifestFile]) -> list[IntakeManifestFile]:
        paths = [entry.path for entry in files]
        if len(paths) != len(set(paths)):
            raise ValueError("manifest files paths must be unique")
        return files


class PRGateValidationResult(BaseModel):
    """Structured result for successful intake validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intake_id: str
    intake_root: Path
    changed_paths: list[str]


def _run_git_diff_paths(base_sha: str, head_sha: str, repo_root: Path) -> list[str]:
    cmd = ["git", "diff", "--name-only", "--no-renames", f"{base_sha}..{head_sha}"]
    result = subprocess.run(cmd, cwd=repo_root, check=True, capture_output=True, text=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _select_single_intake_id(changed_paths: list[str]) -> str:
    if not changed_paths:
        raise PRGateValidationError("No files changed in PR diff")

    invalid_scope = [path for path in changed_paths if not path.startswith(INBOX_PREFIX)]
    if invalid_scope:
        joined = ", ".join(sorted(invalid_scope))
        raise PRGateValidationError(f"PR Gate accepts only intake paths under {INBOX_PREFIX}. Invalid paths: {joined}")

    intake_ids: set[str] = set()
    for path in changed_paths:
        suffix = path[len(INBOX_PREFIX) :]
        intake_id = suffix.split("/", maxsplit=1)[0].strip()
        if not intake_id:
            raise PRGateValidationError(f"Invalid intake path: {path}")
        intake_ids.add(intake_id)

    if len(intake_ids) != 1:
        joined = ", ".join(sorted(intake_ids))
        raise PRGateValidationError(f"Exactly one intake folder is allowed per PR. Found: {joined}")

    return next(iter(intake_ids))


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PRGateValidationError(f"Invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PRGateValidationError(f"Expected JSON object at {path}")
    return payload


def _resolve_declared_file(intake_root: Path, declared_path: str) -> Path:
    declared = Path(declared_path)
    if declared.is_absolute() or ".." in declared.parts:
        raise PRGateValidationError(f"Manifest path is unsafe: {declared_path}")

    resolved = (intake_root / declared).resolve()
    intake_resolved = intake_root.resolve()
    try:
        resolved.relative_to(intake_resolved)
    except ValueError as exc:
        raise PRGateValidationError(f"Manifest path escapes intake root: {declared_path}") from exc
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_intake_tree(intake_root: Path) -> tuple[IntakeSubmission, IntakeManifest]:
    submission_file = intake_root / "submission.json"
    manifest_file = intake_root / "manifest.json"
    tasks_root = intake_root / "tasks"

    if not submission_file.is_file():
        raise PRGateValidationError(f"Missing required file: {submission_file}")
    if not manifest_file.is_file():
        raise PRGateValidationError(f"Missing required file: {manifest_file}")
    if not tasks_root.is_dir():
        raise PRGateValidationError(f"Missing required directory: {tasks_root}")

    submission_payload = _read_json_file(submission_file)
    manifest_payload = _read_json_file(manifest_file)

    try:
        submission = IntakeSubmission.model_validate(submission_payload)
    except ValidationError as exc:
        raise PRGateValidationError(f"Invalid submission schema in {submission_file}: {exc}") from exc

    try:
        manifest = IntakeManifest.model_validate(manifest_payload)
    except ValidationError as exc:
        raise PRGateValidationError(f"Invalid manifest schema in {manifest_file}: {exc}") from exc

    validate_manifest_integrity(intake_root, manifest)
    validate_task_invariants(tasks_root)
    return submission, manifest


def validate_manifest_integrity(intake_root: Path, manifest: IntakeManifest) -> None:
    for entry in manifest.files:
        target = _resolve_declared_file(intake_root, entry.path)
        if not target.is_file():
            raise PRGateValidationError(f"Manifest declared path does not exist as a file: {entry.path}")

        actual_size = target.stat().st_size
        if actual_size != entry.size_bytes:
            raise PRGateValidationError(
                f"Manifest size mismatch for {entry.path}: expected {entry.size_bytes}, got {actual_size}"
            )

        actual_sha = _sha256_file(target)
        if actual_sha != entry.sha256:
            raise PRGateValidationError(
                f"Manifest sha256 mismatch for {entry.path}: expected {entry.sha256}, got {actual_sha}"
            )


def validate_task_invariants(tasks_root: Path) -> None:
    task_dirs = sorted([entry for entry in tasks_root.iterdir() if entry.is_dir()], key=lambda path: path.name)
    if not task_dirs:
        raise PRGateValidationError(f"tasks directory must contain at least one task folder: {tasks_root}")

    for task_dir in task_dirs:
        names = {entry.name for entry in task_dir.iterdir() if entry.is_file()}
        if not names:
            raise PRGateValidationError(f"Task directory has no files: {task_dir}")

        allowed = {TASK_MISSING_SENTINEL_FILE, TASK_AGENT_RESPONSE_FILE, TASK_NETWORK_HAR_FILE}
        extra = names - allowed
        if extra:
            joined = ", ".join(sorted(extra))
            raise PRGateValidationError(f"Task directory has unsupported file(s) in {task_dir}: {joined}")

        has_missing = TASK_MISSING_SENTINEL_FILE in names
        has_agent = TASK_AGENT_RESPONSE_FILE in names
        has_har = TASK_NETWORK_HAR_FILE in names

        if has_missing:
            if names != {TASK_MISSING_SENTINEL_FILE}:
                raise PRGateValidationError(
                    f"Task invariant failed in {task_dir}: {TASK_MISSING_SENTINEL_FILE} cannot coexist with other files"
                )
            missing_file = task_dir / TASK_MISSING_SENTINEL_FILE
            if missing_file.stat().st_size != 0:
                raise PRGateValidationError(
                    f"Task invariant failed in {task_dir}: {TASK_MISSING_SENTINEL_FILE} must be empty"
                )
            continue

        if not (has_agent and has_har):
            raise PRGateValidationError(
                f"Task invariant failed in {task_dir}: expected {TASK_AGENT_RESPONSE_FILE} + {TASK_NETWORK_HAR_FILE} "
                f"or only {TASK_MISSING_SENTINEL_FILE}"
            )

        try:
            json.loads((task_dir / TASK_AGENT_RESPONSE_FILE).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PRGateValidationError(f"Invalid JSON in {task_dir / TASK_AGENT_RESPONSE_FILE}: {exc}") from exc

        try:
            json.loads((task_dir / TASK_NETWORK_HAR_FILE).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PRGateValidationError(f"Invalid JSON in {task_dir / TASK_NETWORK_HAR_FILE}: {exc}") from exc


def run_pr_gate_intake_validation(repo_root: Path, base_sha: str, head_sha: str) -> PRGateValidationResult:
    changed_paths = _run_git_diff_paths(base_sha=base_sha, head_sha=head_sha, repo_root=repo_root)
    intake_id = _select_single_intake_id(changed_paths)
    intake_root = repo_root / INBOX_PREFIX / intake_id
    if not intake_root.is_dir():
        raise PRGateValidationError(f"Intake folder does not exist in PR checkout: {intake_root}")

    validate_intake_tree(intake_root)
    return PRGateValidationResult(intake_id=intake_id, intake_root=intake_root, changed_paths=changed_paths)
