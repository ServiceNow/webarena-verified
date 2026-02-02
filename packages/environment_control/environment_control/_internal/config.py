"""Configuration management for environment_control package."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Config:
    """Configuration for the environment control server."""

    env_type: Optional[str] = None
    port: int = 8877
    site_url: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Config":
        """Read configuration from environment variables."""
        return cls(
            env_type=os.environ.get("WA_ENV_CTRL_TYPE"),
            port=int(os.environ.get("WA_ENV_CTRL_PORT", cls.port)),
            site_url=os.environ.get("WA_ENV_CTRL_EXTERNAL_SITE_URL"),
        )


# Backwards compatibility
def get_config() -> Config:
    """Read configuration from environment variables."""
    return Config.from_env()
