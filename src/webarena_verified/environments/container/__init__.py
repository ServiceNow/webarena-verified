"""Container management for WebArena Docker environments.

This package provides utilities for managing Docker containers for WebArena sites,
including starting, stopping, and checking status of containers.
"""

from webarena_verified.types.container import ContainerStartResult, ContainerStatus, ContainerStatusResult

from .backend import ContainerBackend, DockerBackend, get_default_backend
from .defaults import DEFAULT_CONTAINER_CONFIGS, get_container_config, get_sites_with_setup
from .manager import ContainerManager

__all__ = [
    "DEFAULT_CONTAINER_CONFIGS",
    "ContainerBackend",
    "ContainerManager",
    "ContainerStartResult",
    "ContainerStatus",
    "ContainerStatusResult",
    "DockerBackend",
    "get_container_config",
    "get_default_backend",
    "get_sites_with_setup",
]
