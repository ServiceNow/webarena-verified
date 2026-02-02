"""Docker exec client for the environment control CLI.

This module provides a client that executes env-ctrl CLI commands via
docker exec, allowing control of environments without requiring network access.
"""

import json
import subprocess
import time

from webarena_verified.types.environment import EnvCtrlResult


class EnvCtrlDockerClient:
    """Client that executes env-ctrl CLI commands via docker exec.

    Args:
        container_name: Name of the Docker container to exec into.
        timeout: Command timeout in seconds. Defaults to 30.
    """

    def __init__(
        self,
        container_name: str,
        timeout: int = 30,
    ) -> None:
        self._container_name = container_name
        self._timeout = timeout

    @classmethod
    def create(
        cls,
        container_name: str,
        timeout: int = 30,
    ) -> "EnvCtrlDockerClient":
        """Create a new client instance.

        Args:
            container_name: Name of the Docker container to exec into.
            timeout: Command timeout in seconds. Defaults to 30.

        Returns:
            New EnvCtrlDockerClient instance.
        """
        return cls(container_name, timeout)

    def run_command(self, *args: str) -> EnvCtrlResult:
        """Run arbitrary env-ctrl command with pass-through args.

        This method allows running any env-ctrl command with any arguments,
        providing full CLI pass-through capability.

        Args:
            *args: Command and arguments to pass to env-ctrl.
                   Example: ("--verbose", "status") or ("start", "--wait", "--timeout", "120")

        Returns:
            EnvCtrlResult with success, message, and details.

        Raises:
            ConnectionError: If unable to connect to the Docker container.
            RuntimeError: If the command fails or returns invalid output.

        Example:
            >>> client = EnvCtrlDockerClient("shopping_admin")
            >>> client.run_command("--verbose", "status")
            EnvCtrlResult(success=True, message='Environment is running', details={...})
        """
        cmd = [
            "docker",
            "exec",
            self._container_name,
            "env-ctrl",
            *args,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            return EnvCtrlResult(
                success=False,
                message=f"Command timed out after {self._timeout}s",
                details={"timeout": self._timeout, "command": " ".join(cmd)},
            )
        except FileNotFoundError as e:
            raise ConnectionError("Docker command not found. Is Docker installed?") from e
        except Exception as e:
            raise RuntimeError(f"Failed to execute docker command: {e}") from e

        # Try to parse JSON output (from --verbose flag)
        output = result.stdout.strip()
        if output:
            try:
                parsed = json.loads(output)
                return EnvCtrlResult.model_validate(parsed)
            except json.JSONDecodeError:
                pass

        # Fall back to constructing response from exit code and output
        if result.returncode == 0:
            return EnvCtrlResult(
                success=True,
                message=output or "Command completed successfully",
                details={},
            )
        error_output = result.stderr.strip() or result.stdout.strip()
        return EnvCtrlResult(
            success=False,
            message=error_output or f"Command failed with exit code {result.returncode}",
            details={"exit_code": result.returncode},
        )

    def _run_cli(self, command: str, *extra_args: str) -> EnvCtrlResult:
        """Run an env-ctrl command with --verbose flag for JSON output.

        Args:
            command: The env-ctrl subcommand (e.g., "status", "start").
            *extra_args: Additional arguments to pass to the command.

        Returns:
            EnvCtrlResult with success, message, and details.
        """
        return self.run_command("--verbose", command, *extra_args)

    def _run_setup_cli(self, op: str, *extra_args: str) -> EnvCtrlResult:
        """Run an env-ctrl command with --verbose flag for setup operations.

        Args:
            op: The operation (e.g., "init", "patch", "cleanup").
            *extra_args: Additional arguments to pass to the command.

        Returns:
            EnvCtrlResult with success, message, and details.
        """
        return self.run_command("--verbose", op, *extra_args)

    def init(self, base_url: str | None = None) -> EnvCtrlResult:
        """Initialize the environment.

        Args:
            base_url: Base URL for the environment (e.g., "http://localhost:8080/").

        Returns:
            EnvCtrlResult with success, message, and details.
        """
        if base_url is not None:
            return self._run_setup_cli("init", "--base-url", base_url)
        return self._run_setup_cli("init")

    def status(self) -> EnvCtrlResult:
        """Get environment status.

        Returns:
            EnvCtrlResult with success, message, and details.
        """
        return self._run_cli("status")

    def start(self, wait: bool = False, timeout: int | None = None) -> EnvCtrlResult:
        """Start the environment.

        Args:
            wait: If True, wait until environment is ready.
            timeout: Timeout in seconds for waiting (only used with wait=True).

        Returns:
            EnvCtrlResult with success, message, and details.
        """
        args = []
        if wait:
            args.append("--wait")
            if timeout is not None:
                args.extend(["--timeout", str(timeout)])
        return self._run_cli("start", *args)

    def stop(self) -> EnvCtrlResult:
        """Stop the environment.

        Returns:
            EnvCtrlResult with success, message, and details.
        """
        return self._run_cli("stop")

    def restart(self, wait: bool = False, timeout: int | None = None) -> EnvCtrlResult:
        """Restart the environment.

        Args:
            wait: If True, wait until environment is ready.
            timeout: Timeout in seconds for waiting (only used with wait=True).

        Returns:
            EnvCtrlResult with success, message, and details.
        """
        args = []
        if wait:
            args.append("--wait")
            if timeout is not None:
                args.extend(["--timeout", str(timeout)])
        return self._run_cli("restart", *args)

    def wait_until_ready(
        self,
        timeout: float = 60.0,
        interval: float = 1.0,
    ) -> EnvCtrlResult:
        """Poll until the environment is ready or timeout is reached.

        Args:
            timeout: Maximum time to wait in seconds.
            interval: Time between polls in seconds.

        Returns:
            EnvCtrlResult with success, message, and details.
        """
        start_time = time.time()
        last_result = EnvCtrlResult(
            success=False,
            message="Timeout waiting for environment",
            details={},
        )

        while time.time() - start_time < timeout:
            try:
                result = self.status()
                if result.success:
                    return result
                last_result = result
            except (ConnectionError, RuntimeError) as e:
                last_result = EnvCtrlResult(
                    success=False,
                    message=str(e),
                    details={},
                )

            time.sleep(interval)

        elapsed = time.time() - start_time
        return EnvCtrlResult(
            success=False,
            message=f"Timeout after {elapsed:.1f}s waiting for environment",
            details={
                "last_result": last_result.model_dump(),
                "timeout": timeout,
                "elapsed": elapsed,
            },
        )

    def analyze_disk(self, top: int = 20) -> EnvCtrlResult:
        """Analyze disk usage in container.

        Args:
            top: Number of largest entries to return.

        Returns:
            EnvCtrlResult with success, message, and details containing disk usage output.
        """
        cmd = [
            "docker",
            "exec",
            self._container_name,
            "sh",
            "-c",
            f"du -ah / 2>/dev/null | sort -rh | head -n {top}",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout)
            return EnvCtrlResult(
                success=True,
                message="Disk analysis complete",
                details={
                    "output": result.stdout,
                    "top": top,
                },
            )
        except subprocess.TimeoutExpired:
            return EnvCtrlResult(
                success=False,
                message=f"Analysis timed out after {self._timeout}s",
                details={},
            )
