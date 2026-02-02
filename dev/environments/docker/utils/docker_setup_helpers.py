"""Shared utilities for Docker volume setup.

This module provides common functions used by site-specific setup modules
for Docker volume operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dev.utils import logging_utils

if TYPE_CHECKING:
    from invoke.context import Context


def volume_exists(ctx: Context, name: str) -> bool:
    """Check if Docker volume exists."""
    result = ctx.run(f"docker volume ls -q -f name=^{name}$", hide=True, warn=True)
    return bool(result and result.stdout.strip())


def volume_is_empty(ctx: Context, name: str) -> bool:
    """Check if Docker volume is empty (has no files)."""
    result = ctx.run(
        f"docker run --rm -v {name}:/vol:ro alpine sh -c 'ls -A /vol | head -1'",
        hide=True,
        warn=True,
    )
    return not (result and result.stdout.strip())


def create_volume(ctx: Context, name: str) -> None:
    """Create Docker volume if not exists."""
    if volume_exists(ctx, name):
        logging_utils.print_info(f"Volume {name} already exists")
        return

    with logging_utils.StepContext.create(f"docker volume create {name}", desc="Creating volume"):
        ctx.run(f"docker volume create {name}", hide=True)


def get_volume_name(prefix: str, site: str, suffix: str) -> str:
    """Get full volume name: {prefix}-{site}-{suffix}."""
    return f"{prefix}-{site}-{suffix}"
