"""Types for container operations.

This module is stdlib-only and can be used both:
- Inside container: by environment_control
- Outside container: by invoke tasks (wrapping commands with docker exec)
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar


@dataclass
class ExecLog:
    """Log of a single command execution."""

    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """Return True if command exited with code 0."""
        return self.returncode == 0

    @property
    def output(self) -> str:
        """Combined stdout and stderr."""
        if self.stdout and self.stderr:
            return f"{self.stdout}\n{self.stderr}"
        return self.stdout or self.stderr


class ServiceState(str, Enum):
    """State of a service or component.

    Supervisor states (exact match): RUNNING, STOPPED, STARTING, BACKOFF, STOPPING, EXITED, FATAL, UNKNOWN
    Custom states: HEALTHY, UNHEALTHY (for application-level health checks)
    """

    # Supervisor states (exact match)
    RUNNING = "RUNNING"  # Process is running (but not necessarily healthy)
    STOPPED = "STOPPED"  # Process is not running (expected stop)
    STARTING = "STARTING"  # Process is starting up
    BACKOFF = "BACKOFF"  # Process entered STARTING but exited too quickly
    STOPPING = "STOPPING"  # Process is stopping
    EXITED = "EXITED"  # Process exited (expected or not)
    FATAL = "FATAL"  # Process could not start successfully
    UNKNOWN = "UNKNOWN"  # Could not determine state
    # Custom states (application-level)
    HEALTHY = "HEALTHY"  # Running AND responding correctly
    UNHEALTHY = "UNHEALTHY"  # Running but not responding correctly


@dataclass
class Health:
    """Health status for an environment."""

    services: dict[str, ServiceState]  # {service_name: state}

    # States considered acceptable (service is up and working)
    OK_STATES: ClassVar[frozenset[ServiceState]] = frozenset(
        {
            ServiceState.RUNNING,  # Process running (no app-level check available)
            ServiceState.HEALTHY,  # Process running AND app-level check passed
        }
    )

    @property
    def is_healthy(self) -> bool:
        """True if all services are in an acceptable state (RUNNING or HEALTHY)."""
        return all(state in self.OK_STATES for state in self.services.values())


@dataclass
class Result:
    """Result of an operation. No Generic - use Any for value."""

    success: bool
    value: Any = None
    exec_logs: list[ExecLog] = field(default_factory=list)

    def to_dict(self, max_output_len: int = 200) -> dict[str, Any]:
        """Convert to dict for JSON serialization.

        Args:
            max_output_len: Maximum length for stdout/stderr before truncation.
        """
        # Handle Health objects
        value = self.value
        if isinstance(value, Health):
            value = {"services": {k: v.value for k, v in value.services.items()}}

        def clean_output(text: str) -> str:
            """Strip whitespace and truncate long output."""
            text = text.strip()
            if len(text) > max_output_len:
                return text[:max_output_len] + "... (truncated)"
            return text

        # Extract message from value if it's a dict with a message key
        message = ""
        if isinstance(value, dict) and "message" in value:
            # Copy dict to avoid mutating self.value
            value = dict(value)
            message = value.pop("message", "")

        return {
            "success": self.success,
            "message": message,
            "details": {
                "value": value,
                "exec_logs": [
                    {
                        "command": log.command,
                        "returncode": log.returncode,
                        "stdout": clean_output(log.stdout),
                        "stderr": clean_output(log.stderr),
                    }
                    for log in self.exec_logs
                ],
            },
        }


# Type alias for command executor
# Takes command string, returns (returncode, stdout, stderr)
CommandExecutor = Callable[[str], tuple[int, str, str]]


@dataclass(frozen=True)
class OpsConfig:
    """Configuration for container operations.

    All values can be overridden via environment variables.
    """

    timeout_sec: int = 180  # WA_ENV_CTRL_CMD_TIMEOUT_SEC
    retry_count: int = 2  # WA_ENV_CTRL_CMD_RETRY_COUNT
    retry_delay_sec: int = 5  # WA_ENV_CTRL_RETRY_DELAY_SEC

    @classmethod
    def from_env(cls) -> "OpsConfig":
        """Load configuration from environment variables with defaults."""

        def get_int(env_var: str, default: int) -> int:
            val = os.environ.get(env_var)
            if val is not None:
                try:
                    return int(val)
                except ValueError:
                    pass
            return default

        return cls(
            timeout_sec=get_int("WA_ENV_CTRL_CMD_TIMEOUT_SEC", cls.timeout_sec),
            retry_count=get_int("WA_ENV_CTRL_CMD_RETRY_COUNT", cls.retry_count),
            retry_delay_sec=get_int("WA_ENV_CTRL_RETRY_DELAY_SEC", cls.retry_delay_sec),
        )
