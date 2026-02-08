"""Submission control-plane record types."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._validators import validate_rfc3339_utc_z


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

    github_pr_number: int | None = None
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
