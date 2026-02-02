"""Default container configurations for WebArena sites.

This module re-exports container configuration from types.config for backwards compatibility.
"""

from __future__ import annotations

from webarena_verified.environments.container.config import (
    DEFAULT_CONTAINER_CONFIGS,
    get_container_config,
    get_sites_with_setup,
)

__all__ = [
    "DEFAULT_CONTAINER_CONFIGS",
    "get_container_config",
    "get_sites_with_setup",
]
