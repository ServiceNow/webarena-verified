from pydantic import BaseModel, ConfigDict, Field

from .submission_control_status import SubmissionControlStatus


class SubmissionStatusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SubmissionControlStatus
    at_utc: str = Field(min_length=1)
    reason: str | None = None
    run_sha: str | None = None
    latest_sha: str | None = None
    run_url: str | None = None
