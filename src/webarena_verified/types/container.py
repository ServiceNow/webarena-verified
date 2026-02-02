"""Container-related type definitions for WebArena environments."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ContainerStatus(StrEnum):
    """Status of a Docker container."""

    RUNNING = "running"
    STOPPED = "stopped"
    NOT_FOUND = "not_found"


class ContainerStartResult(BaseModel):
    """Result from starting a container.

    Attributes:
        container_name: Name of the started container.
        url: URL to access the site (e.g., "http://localhost:8080").
        env_ctrl_url: URL to access the env-ctrl API (e.g., "http://localhost:8877").
        host_port: Host port mapped to the container's web service.
        env_ctrl_host_port: Host port mapped to the container's env-ctrl port.
    """

    model_config = ConfigDict(frozen=True)

    container_name: str = Field(description="Name of the started container")
    url: str = Field(description="URL to access the site")
    env_ctrl_url: str = Field(description="URL to access the env-ctrl API")
    host_port: int = Field(description="Host port mapped to the container's web service")
    env_ctrl_host_port: int = Field(description="Host port mapped to the container's env-ctrl port")


class ContainerStatusResult(BaseModel):
    """Result from checking container status.

    Attributes:
        container_name: Name of the container.
        status: Current status of the container.
        url: URL to access the site (if running).
        env_ctrl_url: URL to access the env-ctrl API (if running).
        env_ctrl_status: Status from env-ctrl client (if running and reachable).
    """

    model_config = ConfigDict(frozen=True)

    container_name: str = Field(description="Name of the container")
    status: ContainerStatus = Field(description="Current status of the container")
    url: str | None = Field(default=None, description="URL to access the site (if running)")
    env_ctrl_url: str | None = Field(default=None, description="URL to access the env-ctrl API (if running)")
    env_ctrl_status: dict | None = Field(default=None, description="Status from env-ctrl client (if running)")


__all__ = [
    "ContainerStartResult",
    "ContainerStatus",
    "ContainerStatusResult",
]
