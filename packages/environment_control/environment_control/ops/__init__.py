"""Operations module for container environments.

This module provides the base class, types, and site-specific implementations
for container environment operations.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from .base import BaseOps
from .mixins import SupervisorMixin
from .sites import DummyOps, GitlabOps, MapOps, RedditOps, ShoppingAdminOps, ShoppingOps, WikipediaOps
from .types import CommandExecutor, ExecLog, Health, OpsConfig, Result, ServiceState

logger = logging.getLogger(__name__)

# Simple registry mapping environment type names to their Ops classes
_OPS_CLASSES: dict[str, type[BaseOps]] = {
    "shopping_admin": ShoppingAdminOps,
    "dummy": DummyOps,
    "gitlab": GitlabOps,
    "map": MapOps,
    "reddit": RedditOps,
    "shopping": ShoppingOps,
    "wikipedia": WikipediaOps,
}


def get_ops_class(env_type: Optional[str] = None) -> type[BaseOps]:
    """Get an Ops class by environment type.

    Args:
        env_type: Environment type name. If not provided, reads from
                  WA_ENV_CTRL_TYPE environment variable.

    Returns:
        The Ops class for the requested environment type.

    Raises:
        ValueError: If the environment type is unknown or not specified.
    """
    if env_type is None:
        env_type = os.environ.get("WA_ENV_CTRL_TYPE")
        logger.debug("Using WA_ENV_CTRL_TYPE from environment: %s", env_type)

    if env_type is None:
        logger.error("Environment type not specified")
        raise ValueError(
            "Environment type not specified. Set WA_ENV_CTRL_TYPE environment variable "
            f"or pass env_type parameter. Available types: {list(_OPS_CLASSES.keys())}"
        )

    if env_type not in _OPS_CLASSES:
        logger.error("Unknown environment type: %s", env_type)
        raise ValueError(f"Unknown environment type: {env_type}. Available types: {list(_OPS_CLASSES.keys())}")

    logger.debug("Returning ops class for: %s", env_type)
    return _OPS_CLASSES[env_type]


def list_ops() -> dict[str, type[BaseOps]]:
    """Get a copy of the registered environment ops.

    Returns:
        Dict mapping environment type names to their Ops classes.
    """
    return dict(_OPS_CLASSES)


__all__ = [
    "BaseOps",
    "CommandExecutor",
    "DummyOps",
    "ExecLog",
    "GitlabOps",
    "Health",
    "MapOps",
    "OpsConfig",
    "RedditOps",
    "Result",
    "ServiceState",
    "ShoppingAdminOps",
    "ShoppingOps",
    "SupervisorMixin",
    "WikipediaOps",
    "get_ops_class",
    "list_ops",
]
