from pydantic import BaseModel

from .submission_control import SubmissionControlStatus


class HFIngestResult(BaseModel):
    submission_id: int
    submission_uid: str
    control_record_path: str
    canonical_record_path: str | None = None
    status: SubmissionControlStatus
