"""Submission control-plane record types."""

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._validators import (
    validate_probability,
    validate_probability_or_missing_sentinel,
    validate_rfc3339_utc_z,
    validate_sha256_hex,
)

NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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

    status: Literal["accepted"] = "accepted"
    eval_completed_at_utc: str
    evaluator_version: str = Field(min_length=1)

    hf_repo: str = Field(min_length=1)
    hf_path: str = Field(min_length=1)
    hf_revision: str = Field(min_length=1)

    name: str = Field(min_length=1)
    leaderboard: Literal["hard", "full", "both"]
    reference: str = Field(min_length=1)
    version: str | None = None
    contact_info: str | None = None

    overall_score: float
    shopping_score: float
    reddit_score: float
    gitlab_score: float
    wikipedia_score: float
    map_score: float
    shopping_admin_score: float

    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    checksum: str

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

    @field_validator("contact_info")
    @classmethod
    def validate_contact_info(cls, value: str | None) -> str | None:
        """Validate optional contact email format."""
        if value is None:
            return None
        if not EMAIL_PATTERN.match(value):
            raise ValueError("contact_info must be a valid email address")
        return value

    @field_validator("eval_completed_at_utc")
    @classmethod
    def validate_eval_completed_at_utc(cls, value: str) -> str:
        """Validate eval completion timestamp format."""
        return validate_rfc3339_utc_z(value, "eval_completed_at_utc")

    @field_validator("checksum")
    @classmethod
    def validate_checksum(cls, value: str) -> str:
        """Validate checksum hash format."""
        return validate_sha256_hex(value, "checksum")

    @field_validator("overall_score")
    @classmethod
    def validate_overall_score(cls, value: float) -> float:
        """Validate overall score in [0, 1]."""
        return validate_probability(value, "overall_score")

    @field_validator(
        "shopping_score",
        "reddit_score",
        "gitlab_score",
        "wikipedia_score",
        "map_score",
        "shopping_admin_score",
    )
    @classmethod
    def validate_site_score(cls, value: float) -> float:
        """Validate per-site score in [0, 1] or sentinel -1."""
        return validate_probability_or_missing_sentinel(value, "site_score")

    @model_validator(mode="after")
    def validate_submission_identity(self) -> "CanonicalSubmissionRecord":
        """Enforce canonical identity mapping submission_id == github_pr_number."""
        if self.submission_id != self.github_pr_number:
            raise ValueError("submission_id must equal github_pr_number")
        return self
