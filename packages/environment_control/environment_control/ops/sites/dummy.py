"""Dummy environment operations for testing.

No external dependencies - returns configurable results based on environment variables.
"""

from __future__ import annotations

import os
from typing import Any, ClassVar, Optional

from ..base import BaseOps
from ..types import CommandExecutor, ExecLog, Health, Result, ServiceState


class DummyOps(BaseOps):
    """Dummy ops for testing - no external dependencies.

    Behavior is controlled via environment variables:
        DUMMY_HEALTHY: "1" (default) for healthy, "0" for unhealthy
        DUMMY_INIT_FAIL: "0" (default) for success, "1" for failure
        DUMMY_START_FAIL: "0" (default) for success, "1" for failure
        DUMMY_STOP_FAIL: "0" (default) for success, "1" for failure

    Usage:
        WA_ENV_CTRL_TYPE=dummy env-ctrl status
        DUMMY_HEALTHY=0 WA_ENV_CTRL_TYPE=dummy env-ctrl status  # unhealthy
    """

    expected_services: ClassVar[frozenset[str]] = frozenset({"service-a", "service-b", "service-c"})

    # Track running state (class-level for simplicity)
    _running: ClassVar[bool] = True

    @classmethod
    def _get_health(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Return health based on DUMMY_HEALTHY env var and running state."""
        # If stopped, return unhealthy
        if not cls._running:
            services = {
                "service-a": ServiceState.STOPPED,
                "service-b": ServiceState.STOPPED,
                "service-c": ServiceState.STOPPED,
            }
            return Result(
                success=False,
                value=Health(services=services),
                exec_logs=[ExecLog("dummy-health-check", 1, "services stopped", "")],
            )

        healthy = os.environ.get("DUMMY_HEALTHY", "1") == "1"

        if healthy:
            services = {
                "service-a": ServiceState.HEALTHY,
                "service-b": ServiceState.HEALTHY,
                "service-c": ServiceState.RUNNING,
            }
        else:
            services = {
                "service-a": ServiceState.UNHEALTHY,
                "service-b": ServiceState.STOPPED,
                "service-c": ServiceState.RUNNING,
            }

        return Result(
            success=healthy,
            value=Health(services=services),
            exec_logs=[ExecLog("dummy-health-check", 0 if healthy else 1, "dummy output", "")],
        )

    @classmethod
    def _init(
        cls, exec_cmd: Optional[CommandExecutor] = None, base_url: str = "", dry_run: bool = False, **kwargs: Any
    ) -> Result:
        """Return init result based on DUMMY_INIT_FAIL env var."""
        if dry_run:
            return Result(
                success=True,
                value={
                    "dry_run": True,
                    "message": "Dummy init - no operations",
                    "commands_to_run": [],
                    "command_count": 0,
                },
                exec_logs=[],
            )

        fail = os.environ.get("DUMMY_INIT_FAIL", "0") == "1"

        return Result(
            success=not fail,
            exec_logs=[ExecLog("dummy-init", 1 if fail else 0, "dummy init output", "")],
        )

    @classmethod
    def _start(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Return start result based on DUMMY_START_FAIL env var."""
        fail = os.environ.get("DUMMY_START_FAIL", "0") == "1"

        if not fail:
            cls._running = True

        return Result(
            success=not fail,
            exec_logs=[ExecLog("dummy-start", 1 if fail else 0, "dummy start output", "")],
        )

    @classmethod
    def _stop(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Return stop result based on DUMMY_STOP_FAIL env var."""
        fail = os.environ.get("DUMMY_STOP_FAIL", "0") == "1"

        if not fail:
            cls._running = False

        return Result(
            success=not fail,
            exec_logs=[ExecLog("dummy-stop", 1 if fail else 0, "dummy stop output", "")],
        )
