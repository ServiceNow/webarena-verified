"""Submission intake contracts for leaderboard-submissions."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from ._validators import (
    validate_created_at_utc,
    validate_email,
    validate_manifest_path,
    validate_manifest_sha256,
    validate_model_name,
    validate_reference_url,
)

Name = Annotated[str, Field(min_length=1), AfterValidator(validate_model_name)]
ReferenceURL = Annotated[str, Field(min_length=1), AfterValidator(validate_reference_url)]
CreatedAtUTC = Annotated[str, AfterValidator(validate_created_at_utc)]
ContactEmail = Annotated[str, AfterValidator(validate_email)]
ManifestPath = Annotated[str, Field(min_length=1), AfterValidator(validate_manifest_path)]
ManifestSha256 = Annotated[str, AfterValidator(validate_manifest_sha256)]


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
    leaderboard: Literal["hard", "full", "both"]
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
