from pydantic import BaseModel, Field


class HFDispatchContext(BaseModel):
    event_id: str = Field(min_length=1)
    hf_repo: str = Field(min_length=1)
    hf_pr_number: int = Field(ge=1)
    hf_head_sha: str = Field(min_length=1)
    hf_pr_url: str | None = None
    event_scope: str | None = None
    event_action: str | None = None
    event_ts: str | None = None
