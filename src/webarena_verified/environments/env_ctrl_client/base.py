"""Base protocol for environment control clients."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EnvCtrlClientProtocol(Protocol):
    """Protocol defining the interface for environment control clients.

    Both HTTP and Docker exec clients implement this interface, allowing
    callers to use either interchangeably.
    """

    def init(self) -> dict[str, Any]:
        """Initialize the environment.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        ...

    def status(self) -> dict[str, Any]:
        """Get environment status.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        ...

    def is_ready(self) -> dict[str, Any]:
        """Check if environment is ready.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        ...

    def start(self, wait: bool = False) -> dict[str, Any]:
        """Start the environment.

        Args:
            wait: If True, wait until environment is ready.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        ...

    def stop(self) -> dict[str, Any]:
        """Stop the environment.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        ...

    def restart(self, wait: bool = False) -> dict[str, Any]:
        """Restart the environment.

        Args:
            wait: If True, wait until environment is ready after restart.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        ...

    def wait_until_ready(
        self,
        timeout: float = 60.0,
        interval: float = 1.0,
    ) -> dict[str, Any]:
        """Poll until the environment is ready or timeout is reached.

        Args:
            timeout: Maximum time to wait in seconds.
            interval: Time between polls in seconds.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        ...

    def cleanup(self) -> dict[str, Any]:
        """Run cleanup to remove logs, caches, temp files.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        ...

    def patch(self) -> dict[str, Any]:
        """Apply patches from staging directory.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        ...

    def optimize(self) -> dict[str, Any]:
        """Optimize assets (compress images, etc.).

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        ...

    def config(self) -> dict[str, Any]:
        """Get build config (commit_env, cleanup_paths, etc.).

        Returns:
            Dict with build configuration.
        """
        ...
