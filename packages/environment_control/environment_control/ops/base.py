"""Base operations for containerized environments.

This module is stdlib-only and can be used both:
- Inside container: by environment_control
- Outside container: by invoke tasks (wrapping commands with docker exec)
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from .types import CommandExecutor, ExecLog, OpsConfig, Result


class BaseOps(ABC):
    """Abstract base class for container environment operations.

    Subclasses must implement site-specific health checks and initialization,
    and define the `expected_services` class attribute.

    All operations take an optional `exec_cmd` executor function that executes
    commands and returns (returncode, stdout, stderr). If not provided, defaults
    to subprocess execution.
    """

    # --- Class attributes (must be defined by subclasses) ---

    expected_services: ClassVar[frozenset[str]]
    """Services expected to be running for this environment to be healthy."""

    cleanup_paths: ClassVar[list[str]] = []
    """Paths to remove during image cleanup. Subclasses define site-specific paths."""

    # --- env-ctrl configuration ---

    _ENV_CTRL_SERVICE: ClassVar[str] = "env-ctrl"
    """Name of the optional environment control service."""

    _ENV_CTRL_ENABLE_VAR: ClassVar[str] = "WA_ENV_CTRL_ENABLE"
    """Environment variable to enable/disable env-ctrl."""

    _ENV_CTRL_AVAILABLE_VAR: ClassVar[str] = "WA_ENV_CTRL_AVAILABLE"
    """Environment variable indicating env-ctrl is installed in the image."""

    # --- env-ctrl methods ---

    @classmethod
    def _is_env_ctrl_enabled(cls) -> bool:
        """Check if env-ctrl is enabled via environment variable.

        Returns False if WA_ENV_CTRL_AVAILABLE is not 'true' (not installed).
        Otherwise returns True if WA_ENV_CTRL_ENABLE is 'true' (case-insensitive).
        Defaults to True if WA_ENV_CTRL_ENABLE is not set.
        """
        if os.environ.get(cls._ENV_CTRL_AVAILABLE_VAR, "false").lower() != "true":
            return False
        return os.environ.get(cls._ENV_CTRL_ENABLE_VAR, "true").lower() == "true"

    @classmethod
    def _get_expected_services(cls) -> frozenset[str]:
        """Get expected services, including env-ctrl if enabled.

        Returns the base expected_services plus env-ctrl service
        if WA_ENV_CTRL_ENABLE is true.
        """
        if cls._is_env_ctrl_enabled():
            return cls.expected_services | {cls._ENV_CTRL_SERVICE}
        return cls.expected_services

    # --- Public API ---

    @classmethod
    def init(
        cls,
        exec_cmd: CommandExecutor | None = None,
        config: OpsConfig | None = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> Result:
        """Initialize environment with global retry.

        Calls _init() and retries the entire initialization from scratch on failure.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            config: Configuration for retry count etc. Defaults to OpsConfig.from_env().
            dry_run: If True, preview changes without applying them.
            **kwargs: Passed to _init() for site-specific parameters.
        """
        cfg = config or OpsConfig.from_env()
        all_logs: list[ExecLog] = []

        for attempt in range(cfg.retry_count + 1):
            result = cls._init(exec_cmd=exec_cmd, dry_run=dry_run, **kwargs)
            all_logs.extend(result.exec_logs)

            if result.success:
                return Result(success=True, value=result.value, exec_logs=all_logs)

            # Failed - wait before retry (unless dry-run or last attempt)
            if dry_run or attempt >= cfg.retry_count:
                break
            time.sleep(cfg.retry_delay_sec)

        # All retries exhausted
        return Result(success=False, exec_logs=all_logs)

    @classmethod
    def start(
        cls,
        exec_cmd: CommandExecutor | None = None,
        config: OpsConfig | None = None,
        wait: bool = False,
        **kwargs: Any,
    ) -> Result:
        """Start environment services.

        Calls _start() to start services. If wait=True, polls get_health()
        until healthy or timeout.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            config: Configuration for timeout etc. Defaults to OpsConfig.from_env().
            wait: If True, wait for services to become healthy.
            **kwargs: Passed to _start() for site-specific parameters.
        """
        all_logs: list[ExecLog] = []

        result = cls._start(exec_cmd=exec_cmd, **kwargs)
        all_logs.extend(result.exec_logs)

        if not result.success:
            return Result(success=False, exec_logs=all_logs)

        if wait:
            wait_result = cls._wait_until_healthy(exec_cmd=exec_cmd, config=config)
            all_logs.extend(wait_result.exec_logs)
            if not wait_result.success:
                return Result(success=False, exec_logs=all_logs)

        return Result(success=True, exec_logs=all_logs)

    @classmethod
    def stop(
        cls,
        exec_cmd: CommandExecutor | None = None,
        config: OpsConfig | None = None,
        wait: bool = False,
        **kwargs: Any,
    ) -> Result:
        """Stop environment services.

        Calls _stop() to stop services. If wait=True, polls until services
        are stopped or timeout.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            config: Configuration for timeout etc. Defaults to OpsConfig.from_env().
            wait: If True, wait for services to stop.
            **kwargs: Passed to _stop() for site-specific parameters.
        """
        all_logs: list[ExecLog] = []

        result = cls._stop(exec_cmd=exec_cmd, **kwargs)
        all_logs.extend(result.exec_logs)

        if not result.success:
            return Result(success=False, exec_logs=all_logs)

        if wait:
            wait_result = cls._wait_until_stopped(exec_cmd=exec_cmd, config=config)
            all_logs.extend(wait_result.exec_logs)
            if not wait_result.success:
                return Result(success=False, exec_logs=all_logs)

        return Result(success=True, exec_logs=all_logs)

    @classmethod
    def restart(
        cls,
        exec_cmd: CommandExecutor | None = None,
        config: OpsConfig | None = None,
        wait: bool = False,
        **kwargs: Any,
    ) -> Result:
        """Restart environment services (stop + start).

        Stops services (waiting for them to stop), then starts them.
        If wait=True, waits for services to become healthy after starting.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            config: Configuration for timeout etc. Defaults to OpsConfig.from_env().
            wait: If True, wait for services to become healthy after starting.
            **kwargs: Passed to _stop() and _start() for site-specific parameters.
        """
        all_logs: list[ExecLog] = []

        # Stop and wait for services to stop
        stop_result = cls.stop(exec_cmd=exec_cmd, config=config, wait=True, **kwargs)
        all_logs.extend(stop_result.exec_logs)

        if not stop_result.success:
            return Result(success=False, exec_logs=all_logs)

        # Start services (optionally wait for healthy)
        start_result = cls.start(exec_cmd=exec_cmd, config=config, wait=wait, **kwargs)
        all_logs.extend(start_result.exec_logs)

        if not start_result.success:
            return Result(success=False, exec_logs=all_logs)

        return Result(success=True, exec_logs=all_logs)

    @classmethod
    def get_health(
        cls,
        exec_cmd: CommandExecutor | None = None,
        config: OpsConfig | None = None,
        **kwargs: Any,
    ) -> Result:
        """Get environment health with retry.

        Calls _get_health() and retries on failure.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            config: Configuration for retry count etc. Defaults to OpsConfig.from_env().
            **kwargs: Passed to _get_health() for site-specific parameters.
        """
        cfg = config or OpsConfig.from_env()
        all_logs: list[ExecLog] = []
        result: Result | None = None

        for _attempt in range(cfg.retry_count + 1):
            result = cls._get_health(exec_cmd=exec_cmd, **kwargs)
            all_logs.extend(result.exec_logs)

            if result.success:
                return Result(success=True, value=result.value, exec_logs=all_logs)
            # Failed, will retry (if attempts remain)

        # All retries exhausted
        return Result(success=False, value=result.value if result else None, exec_logs=all_logs)

    @classmethod
    def cleanup(
        cls,
        exec_cmd: CommandExecutor | None = None,
        config: OpsConfig | None = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> Result:
        """Remove cleanup_paths to reduce image size.

        Executes rm -rf on each path in cleanup_paths. This is a best-effort
        operation - individual path failures don't fail the overall cleanup.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            config: Configuration. Defaults to OpsConfig.from_env().
            dry_run: If True, preview changes without applying them.
            **kwargs: Additional arguments (unused, for API consistency).

        Returns:
            Result with exec_logs for each cleanup command.
        """
        if dry_run:
            return Result(
                success=True,
                value={
                    "dry_run": True,
                    "paths_to_delete": cls.cleanup_paths,
                    "path_count": len(cls.cleanup_paths),
                },
                exec_logs=[],
            )

        all_logs: list[ExecLog] = []

        for path in cls.cleanup_paths:
            cmd = f"rm -rf {path}"
            returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd, config)
            all_logs.append(ExecLog(cmd, returncode, stdout, stderr))

        # Cleanup always succeeds (best effort)
        return Result(success=True, exec_logs=all_logs)

    @classmethod
    def _run_entrypoint(cls, exec_cmd: CommandExecutor | None = None, **kwargs: Any) -> Result:
        """Run container entrypoint to start services. Override in subclass.

        Called when supervisor is not running (e.g., container started with custom cmd).
        Default implementation is a no-op.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            **kwargs: Site-specific parameters.

        Returns:
            Result indicating if entrypoint was started successfully.
        """
        return Result(
            success=True,
            value={"message": "No entrypoint configured"},
            exec_logs=[],
        )

    # --- Abstract methods (must be implemented by subclasses) ---

    @classmethod
    @abstractmethod
    def _init(
        cls, exec_cmd: CommandExecutor | None = None, base_url: str = "", dry_run: bool = False, **kwargs: Any
    ) -> Result:
        """Site-specific initialization logic.

        Subclasses implement this with their init commands.
        Should fail fast on first error - retry is handled by init().

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            base_url: Base URL for the site (e.g., "http://localhost:7780").
            dry_run: If True, preview changes without applying them.
            **kwargs: Site-specific parameters.
        """
        ...

    @classmethod
    @abstractmethod
    def _start(cls, exec_cmd: CommandExecutor | None = None, **kwargs: Any) -> Result:
        """Site-specific start logic.

        Subclasses implement this to start their services.
        """
        ...

    @classmethod
    @abstractmethod
    def _stop(cls, exec_cmd: CommandExecutor | None = None, **kwargs: Any) -> Result:
        """Site-specific stop logic.

        Subclasses implement this to stop their services.
        """
        ...

    @classmethod
    @abstractmethod
    def _get_health(cls, exec_cmd: CommandExecutor | None = None, **kwargs: Any) -> Result:
        """Site-specific health check logic.

        Subclasses implement this with their health check commands.
        Should fail fast on first error - retry is handled by get_health().
        """
        ...

    # --- Shared helpers ---

    @classmethod
    def _wait_until_healthy(
        cls,
        exec_cmd: CommandExecutor | None = None,
        config: OpsConfig | None = None,
        poll_interval: float = 2.0,
    ) -> Result:
        """Wait until environment is healthy.

        Polls _get_health() until success or timeout.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            config: Configuration for timeout. Defaults to OpsConfig.from_env().
            poll_interval: Seconds between health checks.
        """
        cfg = config or OpsConfig.from_env()
        all_logs: list[ExecLog] = []
        deadline = time.time() + cfg.timeout_sec
        logger = logging.getLogger(__name__)

        while time.time() < deadline:
            result = cls._get_health(exec_cmd=exec_cmd)
            all_logs.extend(result.exec_logs)

            if result.success:
                return Result(success=True, exec_logs=all_logs)

            # Log what's not healthy
            if result.value and hasattr(result.value, "services"):
                unhealthy = [
                    f"{name}={state.name}" for name, state in result.value.services.items() if state.name != "HEALTHY"
                ]
                if unhealthy:
                    logger.info("Waiting for services: %s", ", ".join(unhealthy))

            time.sleep(poll_interval)

        return Result(success=False, exec_logs=all_logs)

    @classmethod
    def _wait_until_stopped(
        cls,
        exec_cmd: CommandExecutor | None = None,
        config: OpsConfig | None = None,
        poll_interval: float = 1.0,
    ) -> Result:
        """Wait until environment services are stopped.

        Polls _get_health() until failure (services down) or timeout.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            config: Configuration for timeout. Defaults to OpsConfig.from_env().
            poll_interval: Seconds between checks.
        """
        cfg = config or OpsConfig.from_env()
        all_logs: list[ExecLog] = []
        deadline = time.time() + cfg.timeout_sec

        while time.time() < deadline:
            result = cls._get_health(exec_cmd=exec_cmd)
            all_logs.extend(result.exec_logs)

            if not result.success:
                # Services are down
                return Result(success=True, exec_logs=all_logs)

            time.sleep(poll_interval)

        return Result(success=False, exec_logs=all_logs)

    @classmethod
    def _check_http(cls, url: str, exec_cmd: CommandExecutor | None = None) -> Result:
        """Check if HTTP endpoint is responding.

        Args:
            url: URL to check
            exec_cmd: Optional executor function. If None, uses subprocess.

        Returns:
            Result with bool indicating if endpoint responded successfully.
        """
        cmd = f"curl -sf --max-time 10 {url}"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        # Log failure details for debugging
        if returncode != 0:
            logger = logging.getLogger(__name__)
            logger.debug("curl failed: exit=%d, stderr=%s", returncode, stderr[:200] if stderr else "")
        return Result(
            success=returncode == 0,
            value=returncode == 0,
            exec_logs=[ExecLog(cmd, returncode, stdout, stderr)],
        )

    @classmethod
    def _run_cmd(
        cls,
        cmd: str,
        exec_cmd: CommandExecutor | None = None,
        config: OpsConfig | None = None,
    ) -> tuple[int, str, str]:
        """Execute a command and return (returncode, stdout, stderr).

        Args:
            cmd: Command string to execute
            exec_cmd: Optional executor function. If None, uses subprocess.
            config: Configuration for timeout etc. Defaults to OpsConfig.from_env().

        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        if exec_cmd is not None:
            return exec_cmd(cmd)

        cfg = config or OpsConfig.from_env()
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=cfg.timeout_sec)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {cfg.timeout_sec}s"
