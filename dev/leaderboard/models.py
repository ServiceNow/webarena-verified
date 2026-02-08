"""Pydantic models used by leaderboard development validators."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dev.leaderboard import constants


def validate_rfc3339_utc_z(value: str, field_name: str) -> str:
    """Validate a timestamp is RFC3339 UTC with trailing Z."""
    if not constants.RFC3339_UTC_Z_PATTERN.match(value):
        raise ValueError(f"{field_name} must be RFC3339 UTC ending with 'Z' (e.g. 2026-02-07T12:00:00Z)")
    return value


def validate_sha256_hex(value: str, field_name: str) -> str:
    """Validate a lowercase 64-char SHA256 hex string."""
    if not constants.SHA256_HEX_PATTERN.match(value):
        raise ValueError(f"{field_name} must be a lowercase 64-character SHA256 hex string")
    return value


class SubmissionStatus(StrEnum):
    """Allowed submission states."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class SubmissionRecord(BaseModel):
    """Control-plane submission record stored in main branch."""

    model_config = ConfigDict(extra="allow")

    submission_id: str = Field(min_length=1)
    status: SubmissionStatus

    hf_repo: str = Field(min_length=1)
    hf_pr_id: int
    hf_pr_url: str = Field(min_length=1)

    created_at_utc: str
    updated_at_utc: str

    github_pr_url: str | None = None
    processed_at_utc: str | None = None
    result_reason: str | None = None

    @field_validator("created_at_utc")
    @classmethod
    def validate_created_at_utc(cls, value: str) -> str:
        """Validate created timestamp format."""
        return validate_rfc3339_utc_z(value, "created_at_utc")

    @field_validator("updated_at_utc")
    @classmethod
    def validate_updated_at_utc(cls, value: str) -> str:
        """Validate updated timestamp format."""
        return validate_rfc3339_utc_z(value, "updated_at_utc")

    @model_validator(mode="after")
    def validate_state_fields(self) -> "SubmissionRecord":
        """Enforce status-dependent required fields."""
        if self.status == SubmissionStatus.PENDING:
            if self.processed_at_utc is not None:
                raise ValueError("processed_at_utc must be null when status=pending")
            return self

        if self.processed_at_utc is None:
            raise ValueError("processed_at_utc is required when status is terminal")

        if self.status == SubmissionStatus.REJECTED and not self.result_reason:
            raise ValueError("result_reason is required when status=rejected")

        return self

    @model_validator(mode="after")
    def validate_optional_timestamps(self) -> "SubmissionRecord":
        """Validate optional processed timestamp when provided."""
        if self.processed_at_utc is not None:
            self.processed_at_utc = validate_rfc3339_utc_z(self.processed_at_utc, "processed_at_utc")
        return self


class SubmissionMetadata(BaseModel):
    """Metadata contract stored in payload metadata.json."""

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
        if not constants.NAME_PATTERN.match(value):
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
        if not constants.EMAIL_PATTERN.match(value):
            raise ValueError("contact_info must be a valid email address")
        return value


class SubmissionPayloadManifest(BaseModel):
    """Payload manifest contract stored in payload manifest.json."""

    model_config = ConfigDict(extra="allow")

    submission_id: str = Field(min_length=1)
    archive_file: Literal["submission-payload.tar.gz"]
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


class SubmissionArtifacts(BaseModel):
    """Derived HF artifact file paths and URLs for a submission."""

    model_config = ConfigDict(frozen=True)

    ref: str
    submission_root: str

    archive_file: str
    checksum_file: str
    metadata_file: str
    manifest_file: str

    archive_remote_path: str
    checksum_remote_path: str
    metadata_remote_path: str
    manifest_remote_path: str

    @classmethod
    def from_record(cls, record: SubmissionRecord) -> "SubmissionArtifacts":
        """Build derived artifact paths and URLs from submission record linkage."""
        ref = f"refs/pr/{record.hf_pr_id}"
        submission_root = f"submissions/accepted/{record.submission_id}"

        archive_file = constants.HF_SUBMISSION_ARCHIVE_FILE
        checksum_file = constants.HF_SUBMISSION_SHA256_FILE
        metadata_file = constants.HF_SUBMISSION_METADATA_FILE
        manifest_file = constants.HF_SUBMISSION_MANIFEST_FILE

        archive_remote_path = f"{submission_root}/{archive_file}"
        checksum_remote_path = f"{submission_root}/{checksum_file}"
        metadata_remote_path = f"{submission_root}/{metadata_file}"
        manifest_remote_path = f"{submission_root}/{manifest_file}"

        return cls(
            ref=ref,
            submission_root=submission_root,
            archive_file=archive_file,
            checksum_file=checksum_file,
            metadata_file=metadata_file,
            manifest_file=manifest_file,
            archive_remote_path=archive_remote_path,
            checksum_remote_path=checksum_remote_path,
            metadata_remote_path=metadata_remote_path,
            manifest_remote_path=manifest_remote_path,
        )
