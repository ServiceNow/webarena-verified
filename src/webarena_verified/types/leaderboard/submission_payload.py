"""Submission intake contracts for leaderboard-submissions."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._validators import validate_relative_repo_path, validate_rfc3339_utc_z, validate_sha256_hex

NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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

    name: str = Field(min_length=1)
    leaderboard: Literal["hard", "full", "both"]
    reference: str = Field(min_length=1)
    created_at_utc: str
    packaging_summary: IntakePackagingSummary
    version: str | None = None
    contact_info: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate model/team name format."""
        if not NAME_PATTERN.match(value):
            raise ValueError("name must match ^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$")
        return value

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        """Validate reference URL format."""
        if not value.startswith(("http://", "https://")):
            raise ValueError("reference must be an http(s) URL")
        return value

    @field_validator("created_at_utc")
    @classmethod
    def validate_created_at_utc(cls, value: str) -> str:
        """Validate created timestamp format."""
        return validate_rfc3339_utc_z(value, "created_at_utc")

    @field_validator("contact_info")
    @classmethod
    def validate_contact_info(cls, value: str | None) -> str | None:
        """Validate optional contact email format."""
        if value is None:
            return None
        if not EMAIL_PATTERN.match(value):
            raise ValueError("contact_info must be a valid email address")
        return value


class IntakeManifestFile(BaseModel):
    """One path/hash/size entry from intake manifest.json."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    sha256: str
    size_bytes: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """Validate manifest file path safety and relativeness."""
        return validate_relative_repo_path(value, "path")

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        """Validate file SHA256 format."""
        return validate_sha256_hex(value, "sha256")


class IntakeManifest(BaseModel):
    """Intake manifest contract stored in inbox manifest.json."""

    model_config = ConfigDict(extra="forbid")

    created_at_utc: str
    schema_version: str = Field(min_length=1)
    files: list[IntakeManifestFile] = Field(min_length=1)

    @field_validator("created_at_utc")
    @classmethod
    def validate_created_at_utc(cls, value: str) -> str:
        """Validate created timestamp format."""
        return validate_rfc3339_utc_z(value, "created_at_utc")

    @field_validator("files")
    @classmethod
    def validate_unique_paths(cls, value: list[IntakeManifestFile]) -> list[IntakeManifestFile]:
        """Reject duplicate file entries by path."""
        paths = [entry.path for entry in value]
        if len(paths) != len(set(paths)):
            raise ValueError("files must contain unique path entries")
        return value


class SubmissionMetadata(BaseModel):
    """Legacy HF payload metadata contract (transitional)."""

    model_config = ConfigDict(extra="allow")

    submission_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    leaderboard: Literal["hard", "full", "both"]
    reference: str = Field(min_length=1)
    created_at_utc: str
    version: str | None = None
    contact_info: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate model/team name format."""
        if not NAME_PATTERN.match(value):
            raise ValueError("name must match ^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$")
        return value

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        """Validate reference URL format."""
        if not value.startswith(("http://", "https://")):
            raise ValueError("reference must be an http(s) URL")
        return value

    @field_validator("created_at_utc")
    @classmethod
    def validate_created_at_utc(cls, value: str) -> str:
        """Validate created timestamp format."""
        return validate_rfc3339_utc_z(value, "created_at_utc")

    @field_validator("contact_info")
    @classmethod
    def validate_contact_info(cls, value: str | None) -> str | None:
        """Validate optional contact email format."""
        if value is None:
            return None
        if not EMAIL_PATTERN.match(value):
            raise ValueError("contact_info must be a valid email address")
        return value


class SubmissionPayloadManifest(BaseModel):
    """Legacy HF payload manifest contract (transitional)."""

    model_config = ConfigDict(extra="allow")

    submission_id: str = Field(min_length=1)
    archive_file: Literal["payload.tar.zst"]
    archive_sha256: str
    archive_size_bytes: int = Field(gt=0)
    created_at_utc: str
    hf_pr_id: int | None
    hf_pr_url: str | None

    @field_validator("archive_sha256")
    @classmethod
    def validate_archive_sha256(cls, value: str) -> str:
        """Validate archive SHA256 format."""
        return validate_sha256_hex(value, "archive_sha256")

    @field_validator("created_at_utc")
    @classmethod
    def validate_created_at_utc(cls, value: str) -> str:
        """Validate created timestamp format."""
        return validate_rfc3339_utc_z(value, "created_at_utc")
