"""Canonical leaderboard submission record types."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._validators import (
    validate_email,
    validate_http_url,
    validate_model_name,
    validate_rfc3339_utc_z,
    validate_sha256_hex,
)
from .submission_payload import SubmissionLeaderboard


class CanonicalSubmissionStatus(StrEnum):
    ACCEPTED = "accepted"


class EvaluationSummary(BaseModel):
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
    evaluator_version: str = Field(min_length=1)


class CanonicalSubmissionRecord(BaseModel):
    """Canonical accepted submission record stored at submissions/<submission_id>.json."""

    model_config = ConfigDict(extra="forbid")

    submission_id: int = Field(ge=1)
    submission_uid: str | None = None
    github_pr_number: int | None = Field(default=None, ge=1)
    github_pr_url: str | None = Field(default=None, min_length=1)

    source_repository_id: int | None = Field(default=None, ge=1)
    source_repository_full_name: str | None = Field(default=None, min_length=1)
    github_pr_author_id: int | None = Field(default=None, ge=1)
    github_pr_author_login: str | None = Field(default=None, min_length=1)

    eval_completed_at_utc: str
    evaluator_version: str = Field(min_length=1)
    status: CanonicalSubmissionStatus = CanonicalSubmissionStatus.ACCEPTED

    hf_repo: str = Field(min_length=1)
    hf_path: str = Field(min_length=1)
    hf_revision: str = Field(min_length=1)
    hf_pr_number: int | None = Field(default=None, ge=1)
    hf_head_sha: str | None = None
    hf_pr_url: str | None = None

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

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_keys(cls, value: Any) -> Any:
        """Normalize legacy canonical record keys to the current schema."""
        if not isinstance(value, dict):
            return value

        payload = dict(value)

        if "evaluator_version" not in payload and "webarena_verified_version" in payload:
            payload["evaluator_version"] = payload["webarena_verified_version"]

        if "hf_revision" not in payload and "huggingface_dataset_revision" in payload:
            payload["hf_revision"] = payload["huggingface_dataset_revision"]

        if "hf_repo" not in payload and "huggingface_dataset_repo" in payload:
            legacy_repo = payload["huggingface_dataset_repo"]
            if isinstance(legacy_repo, str):
                marker = "/submissions/"
                if marker in legacy_repo:
                    prefix, suffix = legacy_repo.split(marker, maxsplit=1)
                    payload["hf_repo"] = prefix
                    payload["hf_path"] = f"submissions/{suffix}"
                else:
                    payload["hf_repo"] = legacy_repo

        payload.setdefault("status", CanonicalSubmissionStatus.ACCEPTED)
        return payload

    @field_validator("eval_completed_at_utc")
    @classmethod
    def validate_eval_completed_timestamp(cls, value: str) -> str:
        """Validate eval completion timestamp format."""
        return validate_rfc3339_utc_z(value, "eval_completed_at_utc")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate model/team name format."""
        return validate_model_name(value, "name")

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        """Validate reference URL format."""
        return validate_http_url(value, "reference")

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
        return validate_sha256_hex(value, "checksum")
