"""Types for submission summary data."""

from pydantic import BaseModel


class SummaryMetadata(BaseModel):
    """Metadata about the submission creation."""

    created_at: str
    total_valid_tasks: int
    output_directories: list[str]


class PackagingSummary(BaseModel):
    """Summary of packaging results."""

    tasks_packaged: int
    tasks_with_issues: int
    duplicate_tasks: int
    unknown_tasks: int
    missing_from_output: int


class PackagedTasks(BaseModel):
    """Information about successfully packaged tasks."""

    task_ids: list[int]
    count: int
    expected_count: int


class MissingFileCategory(BaseModel):
    """Details about a category of missing files."""

    task_ids: list[int]
    count: int
    file: str | None = None
    files: list[str] | None = None
    description: str | None = None


class DuplicateTasks(BaseModel):
    """Information about duplicate tasks."""

    description: str
    task_ids: list[int]
    count: int
    details: dict[str, list[str]]


class UnknownTasks(BaseModel):
    """Information about unknown tasks."""

    description: str
    task_ids: list[int]
    count: int
    details: dict[str, str]


class MissingFromOutput(BaseModel):
    """Information about tasks missing from output."""

    description: str
    task_ids: list[int]
    count: int


class MissingFiles(BaseModel):
    """Information about all missing file categories."""

    missing_agent_response_only: MissingFileCategory
    missing_network_har_only: MissingFileCategory
    missing_both_files: MissingFileCategory
    invalid_har_files: MissingFileCategory
    empty_agent_response: MissingFileCategory


class SubmissionIssues(BaseModel):
    """All issues found during submission creation."""

    missing_files: MissingFiles
    duplicate_tasks: DuplicateTasks
    unknown_tasks: UnknownTasks
    missing_from_output: MissingFromOutput


class SubmissionSummary(BaseModel):
    """Complete submission summary data."""

    metadata: SummaryMetadata
    packaging_summary: PackagingSummary
    packaged_tasks: PackagedTasks
    issues: SubmissionIssues
