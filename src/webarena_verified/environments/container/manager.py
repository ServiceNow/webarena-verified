"""Container manager for WebArena Docker containers.

This module provides the ContainerManager class for starting, stopping,
and managing Docker containers for WebArena sites.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from webarena_verified.environments.env_ctrl_client import EnvCtrlDockerClient, HttpClient
from webarena_verified.types.container import ContainerStartResult, ContainerStatus, ContainerStatusResult

from .backend import ContainerBackend, get_default_backend
from .config import get_container_config

if TYPE_CHECKING:
    from webarena_verified.types.config import ContainerConfig
    from webarena_verified.types.task import WebArenaSite


class ContainerManager:
    """Manages Docker containers for WebArena sites.

    Provides methods to start, stop, and check status of containers
    for individual WebArena sites.

    Args:
        site: WebArena site to manage.
        config: Optional container configuration override.
            If None, uses the default config for the site.
        backend: Optional container backend. If None, uses Docker.
        hostname: Hostname for constructing URLs (default: "localhost").

    Example:
        >>> manager = ContainerManager(site=WebArenaSite.SHOPPING)
        >>> result = manager.start(port=8080)
        >>> print(f"Site running at: {result.url}")
        >>> manager.stop()
    """

    def __init__(
        self,
        *,
        site: WebArenaSite,
        config: ContainerConfig | None = None,
        backend: ContainerBackend | None = None,
        hostname: str = "localhost",
    ) -> None:
        self.site = site
        self.config = get_container_config(site=site, user_config=config)
        self.container_name = f"webarena_verified_{site.value}"
        self.backend = backend or get_default_backend()
        self.hostname = hostname

    def start(
        self,
        *,
        port: int | None = None,
        env_ctrl_port: int | None = None,
        wait: bool = True,
        timeout: int = 120,
    ) -> ContainerStartResult:
        """Start the container and optionally wait for services.

        If a container with the same name already exists, it will be removed
        before starting a new one.

        Args:
            port: Host port for the site. If None, auto-assigns a free port.
            env_ctrl_port: Host port for env-ctrl API. If None, auto-assigns a free port.
            wait: If True, wait for services to be ready before returning.
            timeout: Timeout in seconds for waiting (only used with wait=True).

        Returns:
            ContainerStartResult with URLs and port information.

        Raises:
            RuntimeError: If container fails to start or services don't become ready.
        """
        # Remove existing container if present
        self.backend.container_remove(name=self.container_name)

        # Determine ports
        host_port = port if port is not None else self.backend.find_free_port()
        host_env_ctrl_port = env_ctrl_port if env_ctrl_port is not None else self.backend.find_free_port()

        # Build port and volume mappings
        port_mappings = {
            host_port: self.config.container_port,
            host_env_ctrl_port: self.config.env_ctrl_port,
        }

        # Run container
        self.backend.container_run(
            name=self.container_name,
            image=self.config.docker_img,
            port_mappings=port_mappings,
            volume_mappings=self.config.volumes,
        )

        url = f"http://{self.hostname}:{host_port}"
        env_ctrl_url = f"http://{self.hostname}:{host_env_ctrl_port}"

        # Wait for services if requested
        if wait:
            self._wait_and_configure(port=host_port, timeout=timeout)

        return ContainerStartResult(
            container_name=self.container_name,
            url=url,
            env_ctrl_url=env_ctrl_url,
            host_port=host_port,
            env_ctrl_host_port=host_env_ctrl_port,
        )

    def stop(self) -> None:
        """Stop and remove the container.

        Does nothing if container doesn't exist.
        """
        self.backend.container_remove(name=self.container_name)

    def status(self) -> ContainerStatusResult:
        """Get container status and URLs if running.

        First checks Docker state, then queries env-ctrl if running.

        Returns:
            ContainerStatusResult with current status and URLs (if running).
        """
        # Check Docker state first
        if not self.backend.container_exists(name=self.container_name):
            return ContainerStatusResult(
                container_name=self.container_name,
                status=ContainerStatus.NOT_FOUND,
            )

        if not self.backend.container_running(name=self.container_name):
            return ContainerStatusResult(
                container_name=self.container_name,
                status=ContainerStatus.STOPPED,
            )

        # Get port mappings
        ports = self.backend.get_container_ports(name=self.container_name)

        url = None
        env_ctrl_url = None
        env_ctrl_status = None

        # Look for the web service port
        if self.config.container_port in ports:
            host_port = ports[self.config.container_port]
            url = f"http://{self.hostname}:{host_port}"

        # Look for env-ctrl port and query status
        if self.config.env_ctrl_port in ports:
            host_env_ctrl_port = ports[self.config.env_ctrl_port]
            env_ctrl_url = f"http://{self.hostname}:{host_env_ctrl_port}"

            # Query env-ctrl for detailed status
            try:
                client = HttpClient(base_url=env_ctrl_url, timeout=10)
                result = client.status()
                if result.get("success"):
                    env_ctrl_status = result
            except Exception:
                # env-ctrl not responding, but container is running
                pass

        return ContainerStatusResult(
            container_name=self.container_name,
            status=ContainerStatus.RUNNING,
            url=url,
            env_ctrl_url=env_ctrl_url,
            env_ctrl_status=env_ctrl_status,
        )

    def is_running(self) -> bool:
        """Check if container is currently running.

        Returns:
            True if container is running, False otherwise.
        """
        return self.backend.container_running(name=self.container_name)

    def _wait_and_configure(self, *, port: int, timeout: int) -> None:
        """Wait for services and configure the container.

        Args:
            port: Host port for the site.
            timeout: Timeout in seconds.

        Raises:
            RuntimeError: If services don't become ready within timeout.
        """
        # Client timeout should be longer than wait timeout
        client = EnvCtrlDockerClient.create(self.container_name, timeout=timeout + 60)

        # Wait for services to be ready
        result = client.start(wait=True, timeout=timeout)
        if not result.success:
            raise RuntimeError(f"Services failed to start: {result.message}")

        # Configure base URL
        base_url = f"http://{self.hostname}:{port}/"
        client.init(base_url=base_url)


__all__ = [
    "ContainerManager",
]
