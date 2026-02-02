"""Environment control package for Docker containers.

This package provides CLI, REST API, and Python client interfaces for
controlling Docker container environments.

Example usage:
    # CLI
    env-ctrl status
    env-ctrl start --wait

    # Python API
    from environment_control.ops import get_ops_class
    ops = get_ops_class("shopping_admin")
    result = ops.get_health()
"""

from __future__ import annotations

from .ops import BaseOps, DummyOps, ExecLog, Health, OpsConfig, Result, ServiceState, ShoppingAdminOps, get_ops_class

__version__ = "0.1.0"

__all__ = [
    "BaseOps",
    "DummyOps",
    "ExecLog",
    "Health",
    "OpsConfig",
    "Result",
    "ServiceState",
    "ShoppingAdminOps",
    "get_ops_class",
]
