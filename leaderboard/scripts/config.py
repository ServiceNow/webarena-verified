"""Leaderboard scripts configuration.

Centralises runtime settings for the leaderboard pipeline.  Values can
be overridden through environment variables with the ``WA_LEADERBOARD_``
prefix (double-underscore delimiter for nested fields).

Example::

    export WA_LEADERBOARD_DEFAULT_MANIFEST_URL="https://example.com/latest.json"
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class LeaderboardScriptsConfig(BaseSettings):
    """Runtime configuration for leaderboard ingest and build scripts."""

    model_config = SettingsConfigDict(env_prefix="WA_LEADERBOARD_")

    default_manifest_url: str = (
        "https://raw.githubusercontent.com/ServiceNow/webarena-verified/leaderboard-submissions/leaderboard/latest.json"
    )


@lru_cache
def get_config() -> LeaderboardScriptsConfig:
    """Return the cached leaderboard scripts configuration."""
    return LeaderboardScriptsConfig()
