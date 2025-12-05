"""Patch system interfaces and models for WebArena environments."""

from webarena_verified.environments import SiteInstanceHandler
from webarena_verified.types.environment import SiteInstanceCommandResult

__all__ = [
    "SiteInstanceCommandResult",
    "SiteInstanceHandler",
]
