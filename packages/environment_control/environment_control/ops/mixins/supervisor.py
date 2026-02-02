"""Supervisor mixin for container operations."""

from __future__ import annotations

import logging
import time
from typing import ClassVar, Optional

from ..types import CommandExecutor, ExecLog, OpsConfig, Result, ServiceState


class SupervisorMixin:
    """Mixin providing supervisord operations.

    Requires the class to have:
    - `run_cmd` classmethod (provided by BaseOps)
    - `expected_services` class attribute (defined by BaseOps)

    Include this mixin for environments managed by supervisord.
    """

    expected_services: ClassVar[frozenset[str]]  # Required by mixin, defined by BaseOps

    @classmethod
    def is_supervisor_running(
        cls,
        socket_path: str,
        exec_cmd: Optional[CommandExecutor] = None,
    ) -> Result:
        """Check if supervisord is running by testing for its socket.

        Args:
            socket_path: Path to the supervisord socket (e.g., /run/supervisord.sock).
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with success=True if socket exists (supervisor running),
            False otherwise.
        """
        cmd = f"test -S {socket_path}"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)  # type: ignore[attr-defined]
        return Result(
            success=returncode == 0,
            value=returncode == 0,
            exec_logs=[ExecLog(cmd, returncode, stdout, stderr)],
        )

    @classmethod
    def wait_for_supervisord(
        cls,
        exec_cmd: Optional[CommandExecutor] = None,
        config: OpsConfig | None = None,
        poll_interval: float = 2.0,
    ) -> Result:
        """Wait for supervisord to be ready.

        Polls until the supervisord socket exists or timeout is reached.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            config: Configuration for timeout. Defaults to OpsConfig.from_env().
            poll_interval: Seconds between checks.

        Returns:
            Result with success=True if supervisord is ready, False if timeout.
        """
        logger = logging.getLogger(__name__)
        cfg = config or OpsConfig.from_env()
        all_logs: list[ExecLog] = []
        deadline = time.time() + cfg.timeout_sec
        socket_path = "/run/supervisord.sock"

        cmd = f"test -S {socket_path}"
        logger.info("Waiting for supervisord socket (%s)...", socket_path)

        while time.time() < deadline:
            returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)  # type: ignore[attr-defined]
            all_logs.append(ExecLog(cmd, returncode, stdout, stderr))

            if returncode == 0:
                elapsed = cfg.timeout_sec - (deadline - time.time())
                logger.info("Supervisord ready after %.1fs", elapsed)
                return Result(success=True, exec_logs=all_logs)

            time.sleep(poll_interval)

        logger.error("Supervisord socket not ready after %ds", cfg.timeout_sec)
        return Result(success=False, exec_logs=all_logs)

    @classmethod
    def _run_supervisor(
        cls,
        subcommand: str,
        exec_cmd: Optional[CommandExecutor] = None,
    ) -> Result:
        """Run a supervisorctl command after waiting for supervisord.

        Args:
            subcommand: The supervisorctl subcommand (e.g., "status", "start all").
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with exec_logs including wait and command execution.
        """
        logger = logging.getLogger(__name__)

        # Wait for supervisord first
        wait_result = cls.wait_for_supervisord(exec_cmd=exec_cmd)
        if not wait_result.success:
            logger.error("Supervisord is not running, cannot execute: supervisorctl %s", subcommand)
            return Result(success=False, exec_logs=wait_result.exec_logs)

        # Run the supervisorctl command
        cmd = f"supervisorctl {subcommand}"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)  # type: ignore[attr-defined]

        return Result(
            success=returncode == 0,
            value=(returncode, stdout, stderr),
            exec_logs=[*wait_result.exec_logs, ExecLog(cmd, returncode, stdout, stderr)],
        )

    @classmethod
    def supervisor_status(cls, exec_cmd: Optional[CommandExecutor] = None) -> Result:
        """Get status of all supervisord services.

        Returns dict mapping service name to ServiceState (RUNNING, STOPPED, FAILED).
        Note: RUNNING means process is up, not necessarily healthy.

        supervisorctl exit codes:
        - 0: All processes RUNNING
        - 3: At least one process is not RUNNING (stopped, exited, etc.)
        - Other: supervisorctl error
        """
        result = cls._run_supervisor("status", exec_cmd=exec_cmd)

        # _run_supervisor returns success=False for non-zero exit codes,
        # but we need the output to parse even when some processes are stopped (exit code 3)
        if result.value is None:
            # supervisord not running or other critical error
            return Result(success=False, value={}, exec_logs=result.exec_logs)

        returncode, stdout, _stderr = result.value
        services: dict[str, ServiceState] = {}

        # Exit code 0 or 3 are both valid - just different states
        if returncode in (0, 3):
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        status = parts[1].upper()
                        try:
                            services[parts[0]] = ServiceState(status)
                        except ValueError:
                            services[parts[0]] = ServiceState.UNKNOWN

        # Success if we were able to get status (exit code 0 or 3)
        return Result(success=returncode in (0, 3), value=services, exec_logs=result.exec_logs)

    @classmethod
    def supervisor_start(cls, exec_cmd: Optional[CommandExecutor] = None) -> Result:
        """Start all supervisord services."""
        result = cls._run_supervisor("start all", exec_cmd=exec_cmd)
        return Result(success=result.success, exec_logs=result.exec_logs)

    @classmethod
    def supervisor_stop(cls, exec_cmd: Optional[CommandExecutor] = None, exclude_env_ctrl: bool = True) -> Result:
        """Stop supervisord services.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            exclude_env_ctrl: If True (default), keeps env-ctrl running so the API
                remains accessible. Set to False to stop all services including env-ctrl.

        Returns:
            Result indicating success/failure with exec_logs.
        """
        # Get services to stop (all except env-ctrl-init which auto-exits)
        status_result = cls.supervisor_status(exec_cmd)
        if not status_result.success:
            return Result(success=False, exec_logs=status_result.exec_logs)

        all_logs: list[ExecLog] = list(status_result.exec_logs)
        services = status_result.value or {}

        # Filter out env-ctrl if we want to keep it running
        env_ctrl_svc = "env-ctrl"
        services_to_stop = [
            svc
            for svc in services
            if svc != "env-ctrl-init"  # Never try to stop init (auto-exits)
            and (not exclude_env_ctrl or svc != env_ctrl_svc)
        ]

        if not services_to_stop:
            return Result(success=True, exec_logs=all_logs)

        # Stop services one by one to ensure proper shutdown
        cmd = f"supervisorctl stop {' '.join(services_to_stop)}"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)  # type: ignore[attr-defined]
        all_logs.append(ExecLog(cmd, returncode, stdout, stderr))

        return Result(success=returncode == 0, exec_logs=all_logs)

    @classmethod
    def services_running(cls, exec_cmd: Optional[CommandExecutor] = None) -> Result:
        """Check if all expected services are running.

        Returns dict of expected services with their states.
        Uses _get_expected_services() to include optional env-ctrl if enabled.
        """
        result = cls.supervisor_status(exec_cmd)
        if not result.success or result.value is None:
            return Result(
                success=False,
                value={},
                exec_logs=result.exec_logs,
            )

        # Use dynamic expected services (includes env-ctrl if enabled)
        expected_svcs = cls._get_expected_services()  # type: ignore[attr-defined]
        expected = {svc: result.value.get(svc, ServiceState.UNKNOWN) for svc in expected_svcs}

        all_running = all(state == ServiceState.RUNNING for state in expected.values())

        return Result(
            success=all_running,
            value=expected,
            exec_logs=result.exec_logs,
        )
