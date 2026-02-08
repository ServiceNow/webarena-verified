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


class HFDiscussionStatus(StrEnum):
    """Allowed Hugging Face discussion statuses used by the sync flow."""

    OPEN = "open"


class HFDiscussionState(BaseModel):
    """Minimal discussion state payload consumed from HF HTTP endpoint."""

    model_config = ConfigDict(extra="ignore")

    status: str | None = None
    is_closed: bool | None = Field(default=None, alias="isClosed")
    closed_at: str | None = Field(default=None, alias="closedAt")


class SubmissionRecord(BaseModel):
    """Control-plane submission record stored in main branch."""

    model_config = ConfigDict(extra="forbid")

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
    initial_head_sha: str | None = None
    processed_head_sha: str | None = None

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
    def validate_state_fields(self) -> SubmissionRecord:
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
    def validate_optional_timestamps(self) -> SubmissionRecord:
        """Validate optional processed timestamp when provided."""
        if self.processed_at_utc is not None:
            self.processed_at_utc = validate_rfc3339_utc_z(self.processed_at_utc, "processed_at_utc")
        return self


class SubmissionMetadata(BaseModel):
    """Metadata contract stored in payload submission_metadata.json."""

    model_config = ConfigDict(extra="forbid")

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


class SubmissionArtifacts(BaseModel):
    """Derived HF artifact file paths and URLs for a submission."""

    model_config = ConfigDict(frozen=True)

    ref: str
    submission_root: str

    archive_file: str
    metadata_file: str

    @classmethod
    def from_record(cls, record: SubmissionRecord) -> SubmissionArtifacts:
        """Build derived artifact paths and URLs from submission record linkage."""
        ref = f"refs/pr/{record.hf_pr_id}"
        submission_root = f"submissions/accepted/{record.submission_id}"

        archive_file = constants.HF_SUBMISSION_ARCHIVE_FILE
        metadata_file = constants.HF_SUBMISSION_METADATA_FILE

        return cls(
            ref=ref,
            submission_root=submission_root,
            archive_file=archive_file,
            metadata_file=metadata_file,
        )

    def remote_path_for(self, file_name: str) -> str:
        """Build remote path under submission root for a known file name."""
        return f"{self.submission_root}/{file_name}"


class SubmissionPayloadFiles(BaseModel):
    """Downloaded bytes for required submission files."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    payload_archive: bytes
    metadata: bytes


class SubmissionManifest(BaseModel):
    """System-generated manifest for accepted payload + metadata inputs."""

    model_config = ConfigDict(extra="forbid")

    manifest_version: Literal[1]
    submission_id: str = Field(min_length=1)
    hf_pr_id: int
    hf_pr_url: str = Field(min_length=1)

    payload_file: Literal["submission-payload.tar.gz"]
    payload_sha256: str
    payload_size_bytes: int = Field(gt=0)

    metadata_file: Literal["submission_metadata.json"]
    metadata_sha256: str
    metadata_size_bytes: int = Field(gt=0)

    submission_checksum: str

    @field_validator("payload_sha256", "metadata_sha256", "submission_checksum")
    @classmethod
    def validate_sha_fields(cls, value: str) -> str:
        """Validate generated SHA256 fields."""
        return validate_sha256_hex(value, "generated manifest sha256 field")


class DiscoverMatrixItem(BaseModel):
    """One matrix entry for a single discovered HF PR."""

    model_config = ConfigDict(extra="forbid")

    hf_pr_id: int
    hf_head_sha: str = Field(min_length=1)


class DiscoverMatrix(BaseModel):
    """GitHub Actions matrix payload for discovered HF PRs."""

    model_config = ConfigDict(extra="forbid")

    include: list[DiscoverMatrixItem]


class DiscoverResult(BaseModel):
    """Structured discovery result emitted to CI outputs."""

    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    matrix: DiscoverMatrix


class SubmissionsManfiest(BaseModel):
    """Deterministic submissions.json document shape."""

    model_config = ConfigDict(extra="forbid")

    generated_at_utc: str
    count: int = Field(ge=0)
    records: list[SubmissionRecord]

    @field_validator("generated_at_utc")
    @classmethod
    def validate_generated_at_utc(cls, value: str) -> str:
        """Validate document generation timestamp format."""
        return validate_rfc3339_utc_z(value, "generated_at_utc")
