"""Types for submission package creation."""

from pydantic import BaseModel


class SubmissionResult(BaseModel):
    """Result of submission creation.

    Attributes:
        output_path: Path to the created submission folder
        tasks_packaged: List of task IDs successfully packaged
        missing_agent_response: List of task IDs missing only agent_response.json
        missing_network_har: List of task IDs missing only network.har
        missing_both_files: List of task IDs missing both required files
        invalid_har_files: List of task IDs with invalid/empty HAR files
        empty_agent_response: List of task IDs with empty agent response files
        duplicate_task_ids: List of task IDs found in multiple directories
        unknown_task_ids: List of task IDs not in dataset
        missing_task_ids: List of valid task IDs with no output directory
        summary_file: Path to summary.json file within the package
    """

    output_path: str
    tasks_packaged: list[int]
    missing_agent_response: list[int]
    missing_network_har: list[int]
    missing_both_files: list[int]
    invalid_har_files: list[int]
    empty_agent_response: list[int]
    duplicate_task_ids: list[int]
    unknown_task_ids: list[int]
    missing_task_ids: list[int]
    summary_file: str
