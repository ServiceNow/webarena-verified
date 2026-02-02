"""Container management for WebArena Docker environments.

This package provides utilities for managing Docker containers for WebArena sites,
including starting, stopping, and checking status of containers.
"""

from .defaults import (
    DEFAULT_CONTAINER_CONFIGS,
    ENV_CTRL_CONTAINER_PORT,
    VOLUME_PREFIX,
    get_container_config,
    get_sites_with_setup,
    get_volume_name,
)
from .manager import ContainerManager, ContainerStartResult, ContainerStatus, ContainerStatusResult
from .utils import container_exists, container_remove, container_running, find_free_port, get_container_ports

__all__ = [
    "DEFAULT_CONTAINER_CONFIGS",
    "ENV_CTRL_CONTAINER_PORT",
    "VOLUME_PREFIX",
    "ContainerManager",
    "ContainerStartResult",
    "ContainerStatus",
    "ContainerStatusResult",
    "container_exists",
    "container_remove",
    "container_running",
    "find_free_port",
    "get_container_config",
    "get_container_ports",
    "get_sites_with_setup",
    "get_volume_name",
]
