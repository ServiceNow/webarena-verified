"""PR gate intake validators for submissions/inbox payloads."""

from __future__ import annotations

import hashlib
from importlib import metadata as importlib_metadata
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


def _fail(code: str, message: str) -> None:
    raise PRGateValidationError(f"[{code}] {message}")


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
    task_summary: "TaskInvariantSummary"
    score_preview: "ScorePreview"


class TaskInvariantSummary(BaseModel):
    """Task-level invariant summary used by score preview."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_tasks: int = Field(ge=0)
    artifact_tasks: int = Field(ge=0)
    missing_tasks: int = Field(ge=0)


class ScorePreview(BaseModel):
    """Deterministic score preview emitted by PR gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluator_version: str = Field(min_length=1)
    overall_score: float
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)


def _run_git_diff_paths(base_sha: str, head_sha: str, repo_root: Path) -> list[str]:
    cmd = ["git", "diff", "--name-only", "--no-renames", f"{base_sha}..{head_sha}"]
    result = subprocess.run(cmd, cwd=repo_root, check=True, capture_output=True, text=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _select_single_intake_id(changed_paths: list[str]) -> str:
    if not changed_paths:
        _fail("C03_NO_DIFF", "No files changed in PR diff")

    invalid_scope = [path for path in changed_paths if not path.startswith(INBOX_PREFIX)]
    if invalid_scope:
        joined = ", ".join(sorted(invalid_scope))
        _fail("C03_SCOPE_INVALID", f"PR Gate accepts only intake paths under {INBOX_PREFIX}. Invalid paths: {joined}")

    intake_ids: set[str] = set()
    for path in changed_paths:
        suffix = path[len(INBOX_PREFIX) :]
        intake_id = suffix.split("/", maxsplit=1)[0].strip()
        if not intake_id:
            _fail("C03_INTAKE_PATH_INVALID", f"Invalid intake path: {path}")
        intake_ids.add(intake_id)

    if len(intake_ids) != 1:
        joined = ", ".join(sorted(intake_ids))
        _fail("C03_MULTIPLE_INTAKES", f"Exactly one intake folder is allowed per PR. Found: {joined}")

    return next(iter(intake_ids))


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PRGateValidationError(f"[C03_JSON_INVALID] Invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        _fail("C03_JSON_NOT_OBJECT", f"Expected JSON object at {path}")
    return payload


def _resolve_declared_file(intake_root: Path, declared_path: str) -> Path:
    declared = Path(declared_path)
    if declared.is_absolute() or ".." in declared.parts:
        _fail("C04_MANIFEST_PATH_UNSAFE", f"Manifest path is unsafe: {declared_path}")

    resolved = (intake_root / declared).resolve()
    intake_resolved = intake_root.resolve()
    try:
        resolved.relative_to(intake_resolved)
    except ValueError as exc:
        raise PRGateValidationError(
            f"[C04_MANIFEST_PATH_ESCAPE] Manifest path escapes intake root: {declared_path}"
        ) from exc
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_intake_tree(intake_root: Path) -> tuple[IntakeSubmission, IntakeManifest, TaskInvariantSummary]:
    submission_file = intake_root / "submission.json"
    manifest_file = intake_root / "manifest.json"
    tasks_root = intake_root / "tasks"

    if not submission_file.is_file():
        _fail("C03_MISSING_REQUIRED_FILE", f"Missing required file: {submission_file}")
    if not manifest_file.is_file():
        _fail("C03_MISSING_REQUIRED_FILE", f"Missing required file: {manifest_file}")
    if not tasks_root.is_dir():
        _fail("C03_MISSING_REQUIRED_DIR", f"Missing required directory: {tasks_root}")

    submission_payload = _read_json_file(submission_file)
    manifest_payload = _read_json_file(manifest_file)

    try:
        submission = IntakeSubmission.model_validate(submission_payload)
    except ValidationError as exc:
        raise PRGateValidationError(
            f"[C03_SUBMISSION_SCHEMA_INVALID] Invalid submission schema in {submission_file}: {exc}"
        ) from exc

    try:
        manifest = IntakeManifest.model_validate(manifest_payload)
    except ValidationError as exc:
        raise PRGateValidationError(
            f"[C04_MANIFEST_SCHEMA_INVALID] Invalid manifest schema in {manifest_file}: {exc}"
        ) from exc

    validate_manifest_integrity(intake_root, manifest)
    task_summary = validate_task_invariants(tasks_root)
    return submission, manifest, task_summary


def validate_manifest_integrity(intake_root: Path, manifest: IntakeManifest) -> None:
    for entry in manifest.files:
        target = _resolve_declared_file(intake_root, entry.path)
        if not target.is_file():
            _fail("C04_MANIFEST_PATH_MISSING", f"Manifest declared path does not exist as a file: {entry.path}")

        actual_size = target.stat().st_size
        if actual_size != entry.size_bytes:
            _fail(
                "C04_MANIFEST_SIZE_MISMATCH",
                f"Manifest size mismatch for {entry.path}: expected {entry.size_bytes}, got {actual_size}",
            )

        actual_sha = _sha256_file(target)
        if actual_sha != entry.sha256:
            _fail(
                "C04_MANIFEST_SHA256_MISMATCH",
                f"Manifest sha256 mismatch for {entry.path}: expected {entry.sha256}, got {actual_sha}",
            )


def validate_task_invariants(tasks_root: Path) -> TaskInvariantSummary:
    task_dirs = sorted([entry for entry in tasks_root.iterdir() if entry.is_dir()], key=lambda path: path.name)
    if not task_dirs:
        _fail("C05_TASKS_EMPTY", f"tasks directory must contain at least one task folder: {tasks_root}")

    missing_tasks = 0
    artifact_tasks = 0

    for task_dir in task_dirs:
        names = {entry.name for entry in task_dir.iterdir() if entry.is_file()}
        if not names:
            _fail("C05_TASK_EMPTY_DIR", f"Task directory has no files: {task_dir}")

        allowed = {TASK_MISSING_SENTINEL_FILE, TASK_AGENT_RESPONSE_FILE, TASK_NETWORK_HAR_FILE}
        extra = names - allowed
        if extra:
            joined = ", ".join(sorted(extra))
            _fail("C05_TASK_UNSUPPORTED_FILE", f"Task directory has unsupported file(s) in {task_dir}: {joined}")

        has_missing = TASK_MISSING_SENTINEL_FILE in names
        has_agent = TASK_AGENT_RESPONSE_FILE in names
        has_har = TASK_NETWORK_HAR_FILE in names

        if has_missing:
            if names != {TASK_MISSING_SENTINEL_FILE}:
                _fail(
                    "C05_TASK_XOR_VIOLATION",
                    f"Task invariant failed in {task_dir}: {TASK_MISSING_SENTINEL_FILE} cannot coexist with other files",
                )
            missing_file = task_dir / TASK_MISSING_SENTINEL_FILE
            if missing_file.stat().st_size != 0:
                _fail(
                    "C05_TASK_MISSING_SENTINEL_NOT_EMPTY",
                    f"Task invariant failed in {task_dir}: {TASK_MISSING_SENTINEL_FILE} must be empty",
                )
            missing_tasks += 1
            continue

        if not (has_agent and has_har):
            _fail(
                "C05_TASK_XOR_VIOLATION",
                f"Task invariant failed in {task_dir}: expected {TASK_AGENT_RESPONSE_FILE} + {TASK_NETWORK_HAR_FILE} "
                f"or only {TASK_MISSING_SENTINEL_FILE}",
            )

        try:
            json.loads((task_dir / TASK_AGENT_RESPONSE_FILE).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PRGateValidationError(
                f"[C05_TASK_AGENT_RESPONSE_INVALID_JSON] Invalid JSON in {task_dir / TASK_AGENT_RESPONSE_FILE}: {exc}"
            ) from exc

        try:
            json.loads((task_dir / TASK_NETWORK_HAR_FILE).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PRGateValidationError(
                f"[C05_TASK_NETWORK_HAR_INVALID_JSON] Invalid JSON in {task_dir / TASK_NETWORK_HAR_FILE}: {exc}"
            ) from exc

        artifact_tasks += 1

    return TaskInvariantSummary(
        total_tasks=len(task_dirs),
        artifact_tasks=artifact_tasks,
        missing_tasks=missing_tasks,
    )


def resolve_evaluator_version() -> str:
    """Resolve installed evaluator package version."""
    try:
        return importlib_metadata.version("webarena-verified")
    except importlib_metadata.PackageNotFoundError as exc:
        raise PRGateValidationError(
            "[C06_EVALUATOR_VERSION_UNRESOLVED] Package 'webarena-verified' is not installed"
        ) from exc


def build_score_preview(
    task_summary: TaskInvariantSummary, evaluator_version: str, expected_version: str | None
) -> ScorePreview:
    """Build deterministic score preview from validated task invariants."""
    if expected_version and not evaluator_version.startswith(expected_version):
        _fail(
            "C06_EVALUATOR_VERSION_MISMATCH",
            f"Installed evaluator version '{evaluator_version}' does not match expected prefix '{expected_version}'",
        )

    total_tasks = task_summary.total_tasks
    success_count = task_summary.artifact_tasks
    missing_count = task_summary.missing_tasks
    overall_score = 0.0 if total_tasks == 0 else success_count / total_tasks

    return ScorePreview(
        evaluator_version=evaluator_version,
        overall_score=round(overall_score, 6),
        success_count=success_count,
        failure_count=0,
        error_count=0,
        missing_count=missing_count,
    )


def run_pr_gate_intake_validation(
    repo_root: Path,
    base_sha: str,
    head_sha: str,
    expected_evaluator_version: str | None = None,
) -> PRGateValidationResult:
    changed_paths = _run_git_diff_paths(base_sha=base_sha, head_sha=head_sha, repo_root=repo_root)
    intake_id = _select_single_intake_id(changed_paths)
    intake_root = repo_root / INBOX_PREFIX / intake_id
    if not intake_root.is_dir():
        _fail("C03_INTAKE_DIR_MISSING", f"Intake folder does not exist in PR checkout: {intake_root}")

    _, _, task_summary = validate_intake_tree(intake_root)
    evaluator_version = resolve_evaluator_version()
    score_preview = build_score_preview(task_summary, evaluator_version, expected_evaluator_version)
    return PRGateValidationResult(
        intake_id=intake_id,
        intake_root=intake_root,
        changed_paths=changed_paths,
        task_summary=task_summary,
        score_preview=score_preview,
    )
