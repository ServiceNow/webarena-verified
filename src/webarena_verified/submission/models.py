from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from webarena_verified.types.leaderboard._validators import (
    validate_email,
    validate_http_url,
    validate_relative_repo_path,
    validate_rfc3339_utc_z,
    validate_sha256_hex,
)


def _validate_uuid_text(value: str) -> str:
    import uuid

    parsed = uuid.UUID(value)
    normalized = str(parsed)
    if normalized != value:
        raise ValueError("submission_uid must use canonical UUID text")
    return value


SubmissionUid = Annotated[str, AfterValidator(_validate_uuid_text)]
Sha256Hex = Annotated[str, AfterValidator(lambda value: validate_sha256_hex(value, "sha256"))]
UtcZ = Annotated[str, AfterValidator(lambda value: validate_rfc3339_utc_z(value, "timestamp"))]
RelativePath = Annotated[str, AfterValidator(lambda value: validate_relative_repo_path(value, "path"))]


class SubmissionMode(StrEnum):
    FULL = "full"
    HARD = "hard"
    BOTH = "both"


class EvaluatorArtifactName(StrEnum):
    TASK_RESULT = "eval_result.json"
    FOLDER_SUMMARY = "evaluation_summary.json"


class ManifestFileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: RelativePath
    sha256: Sha256Hex
    size_bytes: int = Field(ge=0)


class SubmissionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    created_at_utc: UtcZ
    files: list[ManifestFileEntry] = Field(min_length=1)

    @field_validator("files")
    @classmethod
    def validate_unique_paths(cls, value: list[ManifestFileEntry]) -> list[ManifestFileEntry]:
        paths = [entry.path for entry in value]
        if len(paths) != len(set(paths)):
            raise ValueError("files must have unique paths")
        sorted_paths = sorted(paths)
        if paths != sorted_paths:
            raise ValueError("files must be deterministically sorted by path")
        return value


class SubmissionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_uid: SubmissionUid
    name: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    reference: Annotated[str, AfterValidator(lambda value: validate_http_url(value, "reference"))]
    contact_email: Annotated[str, AfterValidator(validate_email)]
    submitted_tasks: int = Field(ge=1)
    task_network_filename: str = Field(min_length=1)


class SubmissionInternalMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    submission_uid: SubmissionUid
    submission_mode: SubmissionMode
    source_sha: str | None = None
    generated_at_utc: UtcZ
    manifest_sha256: Sha256Hex
    submission_package_checksum: Sha256Hex
    submission_package_checksum_algo: str = Field(min_length=1)


class SubmissionUploadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pr_url: str = Field(min_length=1)
    pr_number: int = Field(ge=1)
    submission_uid: SubmissionUid
    hf_repo: str = Field(min_length=1)
    submission_dir: str = Field(min_length=1)
    tasks_submitted: int = Field(ge=1)
