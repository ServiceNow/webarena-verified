from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SubmissionControlStatus(StrEnum):
    PENDING = "pending"
    VALIDATING = "validating"
    EVALUATING = "evaluating"
    ACCEPTED_PENDING_PUBLISH = "accepted_pending_publish"
    PUBLISHED = "published"
    REJECTED = "rejected"
    FAILED_RETRYABLE = "failed_retryable"
    SUPERSEDED = "superseded"


class SubmissionStatusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SubmissionControlStatus
    at_utc: str = Field(min_length=1)
    reason: str | None = None
    run_sha: str | None = None
    latest_sha: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        payload.pop("run_url", None)
        return payload


class SubmissionControlRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: int = Field(ge=1)
    submission_uid: str = Field(min_length=1)

    hf_repo: str = Field(min_length=1)
    hf_pr_number: int = Field(ge=1)
    hf_head_sha: str = Field(min_length=1)
    hf_pr_url: str | None = None

    status: SubmissionControlStatus
    status_history: list[SubmissionStatusEvent] = Field(default_factory=list)

    processed_event_ids: list[str] = Field(default_factory=list)
    retry_count: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        payload.pop("github_publish_pr_number", None)
        payload.pop("github_publish_merge_sha", None)
        payload.pop("requires_manual_override", None)
        return payload


class HFDispatchContext(BaseModel):
    event_id: str = Field(min_length=1)
    hf_repo: str = Field(min_length=1)
    hf_pr_number: int = Field(ge=1)
    hf_head_sha: str = Field(min_length=1)
    hf_pr_url: str | None = None


class HFIngestResult(BaseModel):
    submission_id: int
    submission_uid: str
    control_record_path: str
    canonical_record_path: str | None = None
    status: SubmissionControlStatus


__all__ = [
    "HFDispatchContext",
    "HFIngestResult",
    "SubmissionControlRecord",
    "SubmissionControlStatus",
    "SubmissionStatusEvent",
]
