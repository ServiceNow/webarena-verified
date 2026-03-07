"""Canonical leaderboard submission record types."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from ._validators import (
    validate_email,
    validate_http_url,
    validate_model_name,
    validate_probability,
    validate_probability_or_missing_sentinel,
    validate_rfc3339_utc_z,
    validate_sha256_hex,
)


def _validate_reference(value: str) -> str:
    return validate_http_url(value, "reference")


def _validate_eval_completed_at_utc(value: str) -> str:
    return validate_rfc3339_utc_z(value, "eval_completed_at_utc")


def _validate_checksum(value: str) -> str:
    return validate_sha256_hex(value, "checksum")


def _validate_name(value: str) -> str:
    return validate_model_name(value)


def _validate_contact_info(value: str) -> str:
    return validate_email(value)


def _validate_overall_score(value: float) -> float:
    return validate_probability(value, "overall_score")


def _validate_site_score(value: float) -> float:
    return validate_probability_or_missing_sentinel(value, "site_score")


SubmissionID = Annotated[int, Field(ge=1)]
ReferenceURL = Annotated[str, Field(min_length=1), AfterValidator(_validate_reference)]
Name = Annotated[str, Field(min_length=1), AfterValidator(_validate_name)]
EvalCompletedAtUTC = Annotated[str, AfterValidator(_validate_eval_completed_at_utc)]
Checksum = Annotated[str, AfterValidator(_validate_checksum)]
ContactEmail = Annotated[str, AfterValidator(_validate_contact_info)]
OverallScore = Annotated[float, AfterValidator(_validate_overall_score)]
SiteScore = Annotated[float, AfterValidator(_validate_site_score)]


class CanonicalSubmissionRecord(BaseModel):
    """Canonical accepted submission record stored at submissions/<submission_id>.json."""

    model_config = ConfigDict(extra="forbid")

    submission_id: SubmissionID
    github_pr_number: SubmissionID
    github_pr_url: str = Field(min_length=1)

    source_repository_id: int = Field(ge=1)
    source_repository_full_name: str = Field(min_length=1)
    github_pr_author_id: int = Field(ge=1)
    github_pr_author_login: str = Field(min_length=1)

    status: Literal["accepted"] = "accepted"
    eval_completed_at_utc: EvalCompletedAtUTC
    evaluator_version: str = Field(min_length=1)

    hf_repo: str = Field(min_length=1)
    hf_path: str = Field(min_length=1)
    hf_revision: str = Field(min_length=1)

    name: Name
    leaderboard: Literal["hard", "full", "both"]
    reference: ReferenceURL
    version: str | None = None
    contact_info: ContactEmail | None = None

    overall_score: OverallScore
    shopping_score: SiteScore
    reddit_score: SiteScore
    gitlab_score: SiteScore
    wikipedia_score: SiteScore
    map_score: SiteScore
    shopping_admin_score: SiteScore

    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    checksum: Checksum

    @model_validator(mode="after")
    def validate_submission_identity(self) -> "CanonicalSubmissionRecord":
        """Enforce canonical identity mapping submission_id == github_pr_number."""
        if self.submission_id != self.github_pr_number:
            raise ValueError("submission_id must equal github_pr_number")
        return self
