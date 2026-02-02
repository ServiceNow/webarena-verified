"""Container manager for WebArena Docker containers.

This module provides the ContainerManager class for starting, stopping,
and managing Docker containers for WebArena sites.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from webarena_verified.environments.env_ctrl_client import EnvCtrlDockerClient

from .defaults import get_container_config
from .utils import container_exists, container_remove, container_running, find_free_port, get_container_ports

if TYPE_CHECKING:
    from webarena_verified.types.config import ContainerConfig
    from webarena_verified.types.task import WebArenaSite


class ContainerStatus(StrEnum):
    """Status of a Docker container."""

    RUNNING = "running"
    STOPPED = "stopped"
    NOT_FOUND = "not_found"


@dataclass
class ContainerStartResult:
    """Result from starting a container.

    Attributes:
        container_name: Name of the started container.
        url: URL to access the site (e.g., "http://localhost:8080").
        env_ctrl_url: URL to access the env-ctrl API (e.g., "http://localhost:8877").
        host_port: Host port mapped to the container's web service.
        env_ctrl_host_port: Host port mapped to the container's env-ctrl port.
    """

    container_name: str
    url: str
    env_ctrl_url: str
    host_port: int
    env_ctrl_host_port: int


@dataclass
class ContainerStatusResult:
    """Result from checking container status.

    Attributes:
        container_name: Name of the container.
        status: Current status of the container.
        url: URL to access the site (if running).
        env_ctrl_url: URL to access the env-ctrl API (if running).
    """

    container_name: str
    status: ContainerStatus
    url: str | None = None
    env_ctrl_url: str | None = None


class ContainerManager:
    """Manages Docker containers for WebArena sites.

    Provides methods to start, stop, and check status of containers
    for individual WebArena sites.

    Args:
        site: WebArena site to manage.
        config: Optional container configuration override.
            If None, uses the default config for the site.

    Example:
        >>> manager = ContainerManager(WebArenaSite.SHOPPING)
        >>> result = manager.start(port=8080)
        >>> print(f"Site running at: {result.url}")
        >>> manager.stop()
    """

    def __init__(
        self,
        site: WebArenaSite,
        config: ContainerConfig | None = None,
    ) -> None:
        self.site = site
        self.config = get_container_config(site, config)
        self.container_name = f"webarena-verified-{site.value}"

    def start(
        self,
        port: int | None = None,
        env_ctrl_port: int | None = None,
        hostname: str = "localhost",
        wait: bool = True,
        timeout: int = 120,
    ) -> ContainerStartResult:
        """Start the container and optionally wait for services.

        If a container with the same name already exists, it will be removed
        before starting a new one.

        Args:
            port: Host port for the site. If None, auto-assigns a free port.
            env_ctrl_port: Host port for env-ctrl API. If None, auto-assigns a free port.
            hostname: Hostname for constructing URLs (default: "localhost").
            wait: If True, wait for services to be ready before returning.
            timeout: Timeout in seconds for waiting (only used with wait=True).

        Returns:
            ContainerStartResult with URLs and port information.

        Raises:
            RuntimeError: If container fails to start or services don't become ready.
        """
        # Remove existing container if present
        container_remove(self.container_name)

        # Determine ports
        host_port = port if port is not None else find_free_port()
        host_env_ctrl_port = env_ctrl_port if env_ctrl_port is not None else find_free_port()

        # Build docker run command
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            self.container_name,
            "-p",
            f"{host_port}:{self.config.container_port}",
            "-p",
            f"{host_env_ctrl_port}:{self.config.env_ctrl_port}",
        ]

        # Add volume mounts
        for volume_name, mount_path in self.config.volumes.items():
            cmd.extend(["-v", f"{volume_name}:{mount_path}"])

        cmd.append(self.config.docker_img)

        # Start container
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to start container: {result.stderr}")

        url = f"http://{hostname}:{host_port}"
        env_ctrl_url = f"http://{hostname}:{host_env_ctrl_port}"

        # Wait for services if requested
        if wait:
            self._wait_and_configure(host_port, timeout, hostname)

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
        container_remove(self.container_name)

    def status(self) -> ContainerStatusResult:
        """Get container status and URLs if running.

        Returns:
            ContainerStatusResult with current status and URLs (if running).
        """
        if not container_exists(self.container_name):
            return ContainerStatusResult(
                container_name=self.container_name,
                status=ContainerStatus.NOT_FOUND,
            )

        if not container_running(self.container_name):
            return ContainerStatusResult(
                container_name=self.container_name,
                status=ContainerStatus.STOPPED,
            )

        # Get port mappings
        ports = get_container_ports(self.container_name)

        url = None
        env_ctrl_url = None

        # Look for the web service port
        container_port_key = f"{self.config.container_port}/tcp"
        if container_port_key in ports:
            url = f"http://localhost:{ports[container_port_key]}"

        # Look for env-ctrl port
        env_ctrl_port_key = f"{self.config.env_ctrl_port}/tcp"
        if env_ctrl_port_key in ports:
            env_ctrl_url = f"http://localhost:{ports[env_ctrl_port_key]}"

        return ContainerStatusResult(
            container_name=self.container_name,
            status=ContainerStatus.RUNNING,
            url=url,
            env_ctrl_url=env_ctrl_url,
        )

    def is_running(self) -> bool:
        """Check if container is currently running.

        Returns:
            True if container is running, False otherwise.
        """
        return container_running(self.container_name)

    def _wait_and_configure(self, port: int, timeout: int, hostname: str) -> None:
        """Wait for services and configure the container.

        Args:
            port: Host port for the site.
            timeout: Timeout in seconds.
            hostname: Hostname for base URL.

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
        base_url = f"http://{hostname}:{port}/"
        init_result = client.init(base_url=base_url)
        if not init_result.success:
            # Log warning but don't fail - some sites might not need init
            pass


__all__ = [
    "ContainerManager",
    "ContainerStartResult",
    "ContainerStatus",
    "ContainerStatusResult",
]
