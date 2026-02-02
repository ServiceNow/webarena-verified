"""Environment control client package.

Provides HTTP and Docker exec clients for interacting with environment control
servers running inside Docker containers.
"""

from webarena_verified.types.environment import EnvCtrlResult

from .base import EnvCtrlClientProtocol
from .docker_client import EnvCtrlDockerClient
from .http_client import HttpClient

# Alias for backwards compatibility
EnvCtrlClient = HttpClient

__all__ = [
    "EnvCtrlClient",
    "EnvCtrlClientProtocol",
    "EnvCtrlDockerClient",
    "EnvCtrlResult",
    "HttpClient",
]
