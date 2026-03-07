"""Submission intake contracts for leaderboard-submissions."""

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from ._validators import (
    validate_email,
    validate_relative_repo_path,
    validate_rfc3339_utc_z,
    validate_sha256_hex,
    validate_http_url,
    validate_model_name,
)

Name = Annotated[str, Field(min_length=1), AfterValidator(lambda value: validate_model_name(value, "name"))]
ReferenceURL = Annotated[str, Field(min_length=1), AfterValidator(lambda value: validate_http_url(value, "reference"))]
CreatedAtUTC = Annotated[str, AfterValidator(lambda value: validate_rfc3339_utc_z(value, "created_at_utc"))]
ContactEmail = Annotated[str, AfterValidator(validate_email)]
ManifestPath = Annotated[
    str,
    Field(min_length=1),
    AfterValidator(lambda value: validate_relative_repo_path(value, "path")),
]
ManifestSha256 = Annotated[str, AfterValidator(lambda value: validate_sha256_hex(value, "sha256"))]


class SubmissionLeaderboard(StrEnum):
    """Allowed leaderboard targets for intake and canonical records."""

    HARD = "hard"
    FULL = "full"
    BOTH = "both"


class IntakePackagingSummary(BaseModel):
    """Packaging summary embedded in submission.json."""

    model_config = ConfigDict(extra="forbid")

    tasks_packaged: int = Field(ge=0)
    tasks_with_issues: int = Field(ge=0)
    duplicate_tasks: int = Field(ge=0)
    unknown_tasks: int = Field(ge=0)
    missing_from_output: int = Field(ge=0)


class IntakeSubmission(BaseModel):
    """Intake payload contract stored in inbox submission.json."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    leaderboard: SubmissionLeaderboard
    reference: ReferenceURL
    created_at_utc: CreatedAtUTC
    packaging_summary: IntakePackagingSummary
    version: str | None = None
    contact_info: ContactEmail | None = None


class IntakeManifestFile(BaseModel):
    """One path/hash/size entry from intake manifest.json."""

    model_config = ConfigDict(extra="forbid")

    path: ManifestPath
    sha256: ManifestSha256
    size_bytes: int = Field(ge=0)


class IntakeManifest(BaseModel):
    """Intake manifest contract stored in inbox manifest.json."""

    model_config = ConfigDict(extra="forbid")

    created_at_utc: CreatedAtUTC
    schema_version: str = Field(min_length=1)
    files: list[IntakeManifestFile] = Field(min_length=1)

    @field_validator("files")
    @classmethod
    def validate_unique_paths(cls, value: list[IntakeManifestFile]) -> list[IntakeManifestFile]:
        """Reject duplicate file entries by path."""
        paths = [entry.path for entry in value]
        if len(paths) != len(set(paths)):
            raise ValueError("files must contain unique path entries")
        return value
