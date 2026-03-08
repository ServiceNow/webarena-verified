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


class ScoreField(StrEnum):
    OVERALL = "overall"
    SHOPPING = "shopping"
    SHOPPING_ADMIN = "shopping_admin"
    GITLAB = "gitlab"
    MAP = "map"
    REDDIT = "reddit"
    MULTISITE = "multisite"
    GITLAB_REDDIT = "gitlab_reddit"


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


class OverallCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    failed_or_error_count: int = Field(ge=0)
    expected_total: int = Field(ge=0, default=0)
    missing_count: int = Field(ge=0, default=0)


class SiteCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    failed_or_error_count: int = Field(ge=0)
    expected_total: int = Field(ge=0, default=0)
    missing_count: int = Field(ge=0, default=0)


class EvaluationSummaryCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall: OverallCounts
    per_site: dict[str, SiteCounts]


class EvaluationScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall: float = Field(ge=0.0, le=1.0)
    shopping: float = Field(ge=0.0, le=1.0)
    shopping_admin: float = Field(ge=0.0, le=1.0)
    gitlab: float = Field(ge=0.0, le=1.0)
    map: float = Field(ge=0.0, le=1.0)
    reddit: float = Field(ge=0.0, le=1.0)
    multisite: float = Field(ge=0.0, le=1.0)
    gitlab_reddit: float = Field(ge=0.0, le=1.0)


class EvaluationSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: UtcZ
    webarena_verified_version: str = Field(min_length=1)
    webarena_verified_evaluator_checksum: str = Field(min_length=1)
    webarena_verified_data_checksum: str = Field(min_length=1)
    summary: EvaluationSummaryCounts
    scores: EvaluationScores


class SubmissionEvaluationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_uid: SubmissionUid
    submission_mode: SubmissionMode
    generated_at_utc: UtcZ
    source_sha: str = Field(min_length=1)
    source: Annotated[str, AfterValidator(lambda value: validate_http_url(value, "source"))]
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    scores: EvaluationScores


class LeaderboardRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    submission_uid: SubmissionUid
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    overall: float = Field(ge=0.0, le=1.0)
    shopping: float = Field(ge=0.0, le=1.0)
    shopping_admin: float = Field(ge=0.0, le=1.0)
    gitlab: float = Field(ge=0.0, le=1.0)
    map: float = Field(ge=0.0, le=1.0)
    reddit: float = Field(ge=0.0, le=1.0)
    multisite: float = Field(ge=0.0, le=1.0)
    gitlab_reddit: float = Field(ge=0.0, le=1.0)
    source: Annotated[str, AfterValidator(lambda value: validate_http_url(value, "source"))]


class LeaderboardGenerationArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_id: str = Field(min_length=1)
    leaderboard: SubmissionMode
    generated_at_utc: UtcZ
    rows_count: int = Field(ge=0)
    rows: list[LeaderboardRow]
    checksum: Sha256Hex
    checksum_algo: str = Field(min_length=1)


class LeaderboardLatestArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    generated_at_utc: UtcZ
    full_file: RelativePath
    hard_file: RelativePath
    full_sha256: Sha256Hex
    hard_sha256: Sha256Hex
    checksum: Sha256Hex
    checksum_algo: str = Field(min_length=1)


class SubmissionUploadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pr_url: str = Field(min_length=1)
    pr_number: int = Field(ge=1)
    submission_uid: SubmissionUid
    hf_repo: str = Field(min_length=1)
    submission_dir: str = Field(min_length=1)
    tasks_submitted: int = Field(ge=1)


class IngestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_uid: SubmissionUid
    leaderboard_latest_path: str = Field(min_length=1)
    full_artifact_path: str = Field(min_length=1)
    hard_artifact_path: str = Field(min_length=1)
