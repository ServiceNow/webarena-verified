"""Environment-related type definitions for WebArena Verified."""

from typing import Any

from pydantic import BaseModel, Field


class SiteInstanceCommandResult(BaseModel):
    """Result from executing a command on a site instance.

    Attributes:
        stdout: Standard output from the command
        stderr: Standard error from the command
        returncode: Exit code of the command (0 indicates success)
    """

    stdout: str = Field(default="", description="Standard output from the command")
    stderr: str = Field(default="", description="Standard error from the command")
    returncode: int = Field(description="Exit code of the command (0 indicates success)")

    @property
    def success(self) -> bool:
        """Check if command executed successfully (returncode == 0)."""
        return self.returncode == 0


class EnvCtrlResult(BaseModel):
    """Result from env-ctrl CLI commands.

    Attributes:
        success: Whether the command succeeded.
        message: Human-readable message describing the result.
        details: Additional details (varies by command).
    """

    success: bool = Field(description="Whether the command succeeded")
    message: str = Field(default="", description="Human-readable message describing the result")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details (varies by command)")


__all__ = [
    "EnvCtrlResult",
    "SiteInstanceCommandResult",
]
