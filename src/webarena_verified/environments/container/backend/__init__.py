"""Container backend abstraction for WebArena environments.

This package provides a Protocol for container backends and a Docker implementation.
This allows for future support of other container runtimes (e.g., Podman).
"""

from .docker import DockerBackend
from .protocol import ContainerBackend

# Default backend instance
_default_backend: ContainerBackend = DockerBackend()


def get_default_backend() -> ContainerBackend:
    """Get the default container backend (Docker)."""
    return _default_backend


__all__ = [
    "ContainerBackend",
    "DockerBackend",
    "get_default_backend",
]
