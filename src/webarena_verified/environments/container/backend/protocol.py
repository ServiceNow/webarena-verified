"""Container backend protocol definition.

Defines the interface for container operations that can be implemented
by different container runtimes (Docker, Podman, etc.).
"""

from __future__ import annotations

from typing import Protocol


class ContainerBackend(Protocol):
    """Protocol for container backend implementations.

    Defines the interface for container operations that can be implemented
    by different container runtimes (Docker, Podman, etc.).
    """

    def container_exists(self, *, name: str) -> bool:
        """Check if a container exists (running or stopped).

        Args:
            name: Container name to check.

        Returns:
            True if container exists, False otherwise.
        """
        ...

    def container_running(self, *, name: str) -> bool:
        """Check if a container is currently running.

        Args:
            name: Container name to check.

        Returns:
            True if container is running, False otherwise.
        """
        ...

    def container_remove(self, *, name: str) -> None:
        """Remove a container if it exists.

        Args:
            name: Container name to remove.
        """
        ...

    def container_run(
        self,
        *,
        name: str,
        image: str,
        port_mappings: dict[int, int],
        volume_mappings: dict[str, str],
    ) -> None:
        """Run a container with the given configuration.

        Args:
            name: Container name.
            image: Docker image to run.
            port_mappings: Host port -> container port mappings.
            volume_mappings: Volume name -> container path mappings.

        Raises:
            RuntimeError: If container fails to start.
        """
        ...

    def get_container_ports(self, *, name: str) -> dict[int, int]:
        """Get the published port mappings for a running container.

        Args:
            name: Container name.

        Returns:
            Dict mapping container port to host port.
            Returns empty dict if container not found or not running.
        """
        ...

    def find_free_port(self) -> int:
        """Find and return an available TCP port.

        Returns:
            An available port number.
        """
        ...


__all__ = ["ContainerBackend"]
