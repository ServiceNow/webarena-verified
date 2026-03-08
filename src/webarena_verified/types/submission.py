"""Types for submission package creation."""

from pydantic import BaseModel


class PackagedTaskStats(BaseModel):
    """Task packaging stats for a leaderboard scope."""

    valid: int
    incomplete: int
    missing: int
    expected: int


class SubmissionResult(BaseModel):
    """Result of submission creation.

    Attributes:
        output_path: Path to the created submission folder
        tasks_packaged: List of task IDs successfully packaged
        packaged_tasks: Packaging counts keyed by leaderboard (full and/or hard)
    """

    output_path: str
    tasks_packaged: list[int]
    packaged_tasks: dict[str, PackagedTaskStats]
