from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from webarena_verified.submission.models import (
    RelativePath,
    Sha256Hex,
    SubmissionMode,
    SubmissionUid,
    UtcZ,
)
from webarena_verified.types.leaderboard._validators import validate_http_url


class ScoreField(StrEnum):
    OVERALL = "overall"
    SHOPPING = "shopping"
    SHOPPING_ADMIN = "shopping_admin"
    GITLAB = "gitlab"
    MAP = "map"
    REDDIT = "reddit"
    MULTISITE = "multisite"
    GITLAB_REDDIT = "gitlab_reddit"


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


class IngestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_uid: SubmissionUid
    leaderboard_latest_path: str = Field(min_length=1)
    full_artifact_path: str = Field(min_length=1)
    hard_artifact_path: str = Field(min_length=1)
