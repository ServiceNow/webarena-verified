from enum import StrEnum


class SubmissionControlStatus(StrEnum):
    PENDING = "pending"
    VALIDATING = "validating"
    EVALUATING = "evaluating"
    ACCEPTED_PENDING_PUBLISH = "accepted_pending_publish"
    PUBLISHED = "published"
    REJECTED = "rejected"
    FAILED_RETRYABLE = "failed_retryable"
    SUPERSEDED = "superseded"
