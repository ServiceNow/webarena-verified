from pydantic import BaseModel


class SubmitResult(BaseModel):
    """Result of submitting a package to the HuggingFace leaderboard dataset."""

    pr_url: str
    pr_number: int
    submission_uid: str
    hf_repo: str
    submission_dir: str
    tasks_submitted: int
