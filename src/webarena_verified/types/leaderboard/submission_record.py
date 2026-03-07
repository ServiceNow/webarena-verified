"""Canonical leaderboard submission record types."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._validators import (
    validate_checksum,
    validate_email,
    validate_eval_completed_at_utc,
    validate_model_name,
    validate_reference_url,
)
from .submission_payload import SubmissionLeaderboard


class CanonicalSubmissionRecord(BaseModel):
    """Canonical accepted submission record stored at submissions/<submission_id>.json."""

    model_config = ConfigDict(extra="forbid")

    submission_id: int = Field(ge=1)
    github_pr_number: int = Field(ge=1)
    github_pr_url: str = Field(min_length=1)

    source_repository_id: int = Field(ge=1)
    source_repository_full_name: str = Field(min_length=1)
    github_pr_author_id: int = Field(ge=1)
    github_pr_author_login: str = Field(min_length=1)

    eval_completed_at_utc: str
    webarena_verified_version: str = Field(min_length=1)

    huggingface_dataset_repo: str = Field(min_length=1)
    huggingface_dataset_revision: str = Field(min_length=1)

    name: str = Field(min_length=1)
    leaderboard: SubmissionLeaderboard
    reference: str = Field(min_length=1)
    model_version: str | None = None
    contact_info: str | None = None

    overall_score: float = Field(ge=0)
    shopping_score: float = Field(ge=0)
    reddit_score: float = Field(ge=0)
    gitlab_score: float = Field(ge=0)
    wikipedia_score: float = Field(ge=0)
    map_score: float = Field(ge=0)
    shopping_admin_score: float = Field(ge=0)

    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    checksum: str

    @field_validator("eval_completed_at_utc")
    @classmethod
    def validate_eval_completed_timestamp(cls, value: str) -> str:
        """Validate eval completion timestamp format."""
        return validate_eval_completed_at_utc(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate model/team name format."""
        return validate_model_name(value)

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        """Validate reference URL format."""
        return validate_reference_url(value)

    @field_validator("contact_info")
    @classmethod
    def validate_contact_info(cls, value: str | None) -> str | None:
        """Validate optional contact email format."""
        if value is None:
            return None
        return validate_email(value)

    @field_validator("checksum")
    @classmethod
    def validate_checksum_sha(cls, value: str) -> str:
        """Validate checksum hash format."""
        return validate_checksum(value)

    @model_validator(mode="after")
    def validate_submission_identity(self) -> "CanonicalSubmissionRecord":
        """Enforce canonical identity mapping submission_id == github_pr_number."""
        if self.submission_id != self.github_pr_number:
            raise ValueError("submission_id must equal github_pr_number")
        return self
