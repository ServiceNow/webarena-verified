from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

# Public type for external agent responses (no lists - agents return single values)
PublicResultItem = str | int | float | bool | dict[str, Any] | None

# Internal type for evaluation (includes lists to support alternatives in expected values)
# Supports nested lists for alternatives like [["item1", "item2"], ["item3", "item4"]]
InternalResultItem = PublicResultItem | list[str | int | float | bool | dict[str, Any] | None]


class MainObjectiveType(StrEnum):
    """Used to indicate the overall type of work performed to attain the task objective.

    Attributes:
        RETRIEVE: Use retrieving data is the main objective of the task
        MUTATE: Use when creating, updating, or deleting data or state is the main objective of the task
        NAVIGATE: Use when navigating or browsing to show a specific page or location is the main objective of the task
    """

    RETRIEVE = "RETRIEVE"
    MUTATE = "MUTATE"
    NAVIGATE = "NAVIGATE"


# Backward compatibility alias
PerformedOperation = MainObjectiveType


class Status(StrEnum):
    """Used to indicate the outcome of the task execution.

    Attributes:
        SUCCESS: Use when the task objective was fully achieved
        ACTION_NOT_ALLOWED_ERROR: Use when the platform does not support the requested action or is not allowed in the current context or state
        NOT_FOUND_ERROR: Use when the target entity or resource could not be located after retry attempts
        PERMISSION_DENIED_ERROR: Use when the current user lacks permission to perform the action
        DATA_VALIDATION_ERROR: Use when required input data was missing or invalid
        UNKNOWN_ERROR: Use when an unexpected failure doesn't match other categories
    """

    SUCCESS = "SUCCESS"
    ACTION_NOT_ALLOWED_ERROR = "ACTION_NOT_ALLOWED_ERROR"
    PERMISSION_DENIED_ERROR = "PERMISSION_DENIED_ERROR"
    NOT_FOUND_ERROR = "NOT_FOUND_ERROR"
    DATA_VALIDATION_ERROR = "DATA_VALIDATION_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class FinalAgentResponse(BaseModel):
    """Final response format for agent task execution.

    The agent must respond with valid JSON containing the task type, task outcome status,
    retrieved data (for retrieve operations), and error details (when applicable).

    Attributes:
        task_type (required): The type of task performed (RETRIEVE, MUTATE, or NAVIGATE)
        status (required): The outcome of the task execution
        retrieved_data: Array of items for 'retrieve' operations, null for 'mutate' and 'navigate' operations.
            Returns empty array if no items found. All items must be the same type (either all primitives of the same type, or all objects with the same keys).
            Use appropriate data type formats (e.g., numbers for amounts/counts, true/false for booleans, not strings).
            For list of objects, the user instruction contains the format specification.
        error_details: Null when status is 'SUCCESS'. Otherwise, explains used to explain the failure reason concisely.
    """

    task_type: MainObjectiveType = Field(validation_alias=AliasChoices("task_type", "performed_operation"))
    status: Status
    retrieved_data: list[PublicResultItem] | None = None
    error_details: str | None = None

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_case(cls, data: Any) -> Any:
        """Normalize task_type and status to uppercase for case-insensitive parsing."""
        if isinstance(data, dict):
            # Handle new field name and legacy field name
            if "task_type" in data and isinstance(data["task_type"], str):
                data["task_type"] = data["task_type"].upper()
            if "performed_operation" in data and isinstance(data["performed_operation"], str):
                data["performed_operation"] = data["performed_operation"].upper()
            if "status" in data and isinstance(data["status"], str):
                data["status"] = data["status"].upper()
        return data

    @property
    def is_retrieve(self) -> bool:
        """Check if the task type is RETRIEVE."""
        return self.task_type == MainObjectiveType.RETRIEVE

    @property
    def is_navigate(self) -> bool:
        """Check if the task type is NAVIGATE."""
        return self.task_type == MainObjectiveType.NAVIGATE

    @property
    def is_mutate(self) -> bool:
        """Check if the task type is MUTATE."""
        return self.task_type == MainObjectiveType.MUTATE


class _FinalAgentResponse(FinalAgentResponse):
    """Internal version for loading expected values with alternatives.

    Used only when parsing task definitions that may contain alternative
    values (e.g., ["success", "ok"] means either is acceptable).
    Never exposed to public users - the public schema comes from FinalAgentResponse.
    """

    retrieved_data: list[InternalResultItem] | None = None

    @classmethod
    def model_json_schema(cls, **kwargs: Any) -> dict[str, Any]:
        """Return public schema from parent class to hide internal implementation."""
        return FinalAgentResponse.model_json_schema(**kwargs)
