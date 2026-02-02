"""Utility functions for Docker container operations.

This module provides low-level utilities for interacting with Docker containers,
including port allocation and container state management.
"""

from __future__ import annotations

import socket
import subprocess


def find_free_port() -> int:
    """Find and return an available TCP port.

    Uses the OS to allocate a free port by binding to port 0,
    which lets the OS choose an available port.

    Returns:
        An available port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def container_exists(name: str) -> bool:
    """Check if a Docker container exists (running or stopped).

    Args:
        name: Container name to check.

    Returns:
        True if container exists, False otherwise.
    """
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == name


def container_running(name: str) -> bool:
    """Check if a Docker container is currently running.

    Args:
        name: Container name to check.

    Returns:
        True if container is running, False otherwise.
    """
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == name


def container_remove(name: str) -> None:
    """Remove a Docker container if it exists.

    Forces removal of the container even if running.

    Args:
        name: Container name to remove.
    """
    if container_exists(name):
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True,
            check=True,
        )


def get_container_ports(name: str) -> dict[str, int]:
    """Get the published port mappings for a running container.

    Args:
        name: Container name.

    Returns:
        Dict mapping container port (e.g., "80/tcp") to host port.
        Returns empty dict if container not found or not running.
    """
    result = subprocess.run(
        ["docker", "port", name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}

    ports = {}
    for line in result.stdout.strip().split("\n"):
        if "->" in line:
            # Format: "80/tcp -> 0.0.0.0:8080"
            container_port, host_mapping = line.split(" -> ")
            # Extract just the port number from "0.0.0.0:8080"
            host_port = int(host_mapping.rsplit(":", 1)[1])
            ports[container_port] = host_port
    return ports


def run_docker_command(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    """Run a docker command and return the result.

    Args:
        args: Command arguments (without 'docker' prefix).
        timeout: Optional timeout in seconds.

    Returns:
        CompletedProcess with stdout, stderr, and returncode.

    Raises:
        subprocess.TimeoutExpired: If command times out.
        FileNotFoundError: If docker is not installed.
    """
    cmd = ["docker", *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
