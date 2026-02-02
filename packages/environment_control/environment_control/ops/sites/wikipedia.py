"""Wikipedia environment operations using kiwix-serve."""

from __future__ import annotations

from typing import Any, ClassVar, Optional

from ..base import BaseOps
from ..mixins import SupervisorMixin
from ..types import CommandExecutor, ExecLog, Health, Result, ServiceState


class WikipediaOps(SupervisorMixin, BaseOps):
    """Operations for Wikipedia environment using kiwix-serve.

    Wikipedia runs on kiwix-serve managed by supervisord.
    Services: kiwix-serve (HTTP server), env-ctrl (control API).
    """

    # Supervisor-managed services (env-ctrl is added dynamically via _get_expected_services if enabled)
    expected_services: ClassVar[frozenset[str]] = frozenset(["kiwix-serve"])

    # No cleanup needed - using external kiwix-serve image
    cleanup_paths: ClassVar[list[str]] = []

    @classmethod
    def _init(
        cls, exec_cmd: Optional[CommandExecutor] = None, base_url: str = "", dry_run: bool = False, **kwargs: Any
    ) -> Result:
        """Initialize Wikipedia environment.

        Kiwix-serve doesn't require any initialization - it serves the ZIM file directly.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            base_url: Base URL (unused - kiwix-serve is stateless).
            dry_run: If True, preview changes without applying them.
        """
        if dry_run:
            return Result(
                success=True,
                value={
                    "dry_run": True,
                    "message": "No initialization required - kiwix-serve is stateless",
                    "commands_to_run": [],
                    "command_count": 0,
                },
                exec_logs=[],
            )
        return Result(
            success=True,
            exec_logs=[ExecLog("init", 0, "No initialization required - kiwix-serve is stateless", "")],
        )

    @classmethod
    def _start(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Start kiwix-serve via supervisorctl."""
        cmd = "supervisorctl start kiwix-serve"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd=exec_cmd)
        log = ExecLog(cmd, returncode, stdout, stderr)
        if returncode == 0 or "already started" in stderr.lower() or "already started" in stdout.lower():
            return Result(success=True, exec_logs=[log])
        return Result(success=False, exec_logs=[log])

    @classmethod
    def _stop(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Stop kiwix-serve via supervisorctl."""
        cmd = "supervisorctl stop kiwix-serve"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd=exec_cmd)
        log = ExecLog(cmd, returncode, stdout, stderr)
        if returncode == 0 or "not running" in stderr.lower() or "not running" in stdout.lower():
            return Result(success=True, exec_logs=[log])
        return Result(success=False, exec_logs=[log])

    @classmethod
    def _get_health(
        cls, exec_cmd: Optional[CommandExecutor] = None, http_url: Optional[str] = None, **kwargs: Any
    ) -> Result:
        """Check if all expected services are healthy via supervisorctl status."""
        result = cls.services_running(exec_cmd=exec_cmd)

        if not result.success or result.value is None:
            return Result(success=False, value=Health(services={}), exec_logs=result.exec_logs)

        # Convert to Health object and check all expected services
        services: dict[str, ServiceState] = result.value
        health = Health(services=services)

        return Result(success=health.is_healthy, value=health, exec_logs=result.exec_logs)
