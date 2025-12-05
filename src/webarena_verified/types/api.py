"""Types for evaluator API."""

from copy import deepcopy
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel


# -----------------------------------------------------------------------
# Evaluator API types
# -----------------------------------------------------------------------
class TaskEvalInput(BaseModel):
    """Input for evaluating a single task. Supports both file paths and raw content.

    Attributes:
        task_id: Unique task identifier
        agent_response: Agent's response as JSON string or path to JSON file
        trace: Network trace as list of events or path to trace file (.zip, .har, .json)

    Examples:
        Create from files:
        >>> input = TaskEvalInput(
        ...     task_id=1,
        ...     agent_response=Path("response.json"),
        ...     trace=Path("trace.zip")
        ... )
        >>> # Or use convenience constructor
        >>> input = TaskEvalInput.from_files(1, Path("response.json"), Path("trace.zip"))

        Create from content:
        >>> input = TaskEvalInput(
        ...     task_id=1,
        ...     agent_response='{"action": "retrieve", "status": "SUCCESS"}',
        ...     trace=[{"type": "resource-snapshot", "snapshot": {...}}]
        ... )
        >>> # Or use convenience constructor
        >>> input = TaskEvalInput.from_content(1, response_str, trace_events)

        Supports Playwright and HAR formats:
        >>> input = TaskEvalInput(task_id=1, agent_response=..., trace=Path("trace.har"))
    """

    task_id: int
    agent_response: str
    trace: list[dict[str, Any]] | Path

    @classmethod
    def from_files(cls, task_id: int, agent_response_file: Path, trace_file: Path) -> Self:
        """Create TaskEvalInput from file paths.

        Args:
            task_id: Task identifier
            agent_response_file: Path to agent response JSON file
            trace_file: Path to trace file (.zip or directory)

        Returns:
            TaskEvalInput instance configured to read from files
        """
        return cls(
            task_id=task_id,
            agent_response=agent_response_file.read_text(),
            trace=trace_file,
        )

    @classmethod
    def from_content(cls, task_id: int, agent_response: str, trace_events: list[dict[str, Any]]) -> Self:
        """Create TaskEvalInput from raw content.

        Args:
            task_id: Task identifier
            agent_response: Raw agent response JSON string
            trace_events: List of parsed trace event dictionaries

        Returns:
            TaskEvalInput instance configured with raw content
        """
        if not isinstance(agent_response, str):
            agent_response = str(agent_response)

        return cls(
            task_id=task_id,
            agent_response=agent_response,
            trace=deepcopy(trace_events),
        )
