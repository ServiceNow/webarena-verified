"""Data models for WebArena Verified dataset management."""

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

if TYPE_CHECKING:
    from .task import WebArenaVerifiedTask


class TaskSubset(BaseModel):
    """Represents a subset of tasks from the WebArena Verified dataset.

    A task subset is defined by a list of task IDs and includes a checksum
    for integrity verification. Subsets are stored in JSON files in the
    assets/dataset/subsets/ directory.

    Example JSON:
        ```json
        {
            "description": "All shopping-related tasks",
            "task_ids": [0, 1, 2, 3, 4, 5, 6],
            "checksum": "a1b2c3d4e5f6..."
        }
        ```
    """

    description: str | None = None
    """Optional description of this task subset."""

    task_ids: list[int]
    """List of task IDs in this subset (must be unique and non-empty)."""

    checksum: str
    """SHA256 hash of sorted task_ids for integrity verification."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    @field_validator("task_ids")
    @classmethod
    def validate_task_ids(cls, v: list[int]) -> list[int]:
        """Validate that task_ids list is non-empty and contains unique values."""
        if not v:
            raise ValueError("task_ids must not be empty")
        if len(v) != len(set(v)):
            raise ValueError("task_ids must contain unique values (no duplicates)")
        return v

    @model_validator(mode="after")
    def validate_checksum(self) -> Self:
        """Validate that the checksum matches the computed checksum of task_ids."""
        expected_checksum = self.compute_checksum(self.task_ids)
        if self.checksum != expected_checksum:
            raise ValueError(
                f"Checksum mismatch: expected {expected_checksum}, got {self.checksum}. "
                f"The task_ids may have been modified. Use 'webarena-verified subset-recompute-checksum' to update."
            )
        return self

    @staticmethod
    def compute_checksum(task_ids: list[int]) -> str:
        """Compute SHA256 checksum of sorted task IDs.

        Args:
            task_ids: List of task IDs

        Returns:
            Hexadecimal SHA256 checksum string
        """
        # Sort task_ids to ensure order-independent checksum
        sorted_ids = sorted(task_ids)
        # Convert to JSON string for consistent serialization
        json_str = json.dumps(sorted_ids, separators=(",", ":"))
        # Compute SHA256 hash
        return hashlib.sha256(json_str.encode()).hexdigest()

    @classmethod
    def from_file(cls, path: Path, name: str | None = None) -> Self:
        """Load TaskSubset from a JSON file.

        Args:
            path: Path to the subset JSON file
            name: Optional name for the subset (derived from filename if not provided)

        Returns:
            TaskSubset instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file content is invalid or checksum doesn't match
        """
        if not path.exists():
            raise FileNotFoundError(f"Subset file not found: {path}")

        try:
            content = json.loads(path.read_text())
            return cls.model_validate(content)
        except Exception as e:
            raise ValueError(f"Failed to load subset from {path}: {e}") from e

    @classmethod
    def from_tasks(cls, tasks: list["WebArenaVerifiedTask"], description: str | None = None) -> Self:
        """Create TaskSubset from a list of tasks.

        Args:
            tasks: List of WebArenaVerifiedTask instances
            description: Optional description for the subset

        Returns:
            TaskSubset instance with task IDs and computed checksum
        """
        task_ids = [task.task_id for task in tasks]
        checksum = cls.compute_checksum(task_ids)
        return cls(description=description, task_ids=task_ids, checksum=checksum)

    def to_dict(self) -> dict[str, Any]:
        """Convert TaskSubset to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "description": self.description,
            "task_ids": self.task_ids,
            "checksum": self.checksum,
        }
