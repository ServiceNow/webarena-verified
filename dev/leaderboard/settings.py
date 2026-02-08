"""Settings models for leaderboard automation workflows."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class HFSyncSettings(BaseSettings):
    """Environment-backed settings for HF sync workflow."""

    model_config = SettingsConfigDict(extra="ignore")

    leaderboard_hf_repo: str = Field(alias="LEADERBOARD_HF_REPO")
    hf_token: str = Field(alias="HF_TOKEN")
    github_output: str | None = Field(default=None, alias="GITHUB_OUTPUT")
    merge_comment_template_path: str = Field(
        default="dev/leaderboard/templates/merge_comment.md",
        alias="LEADERBOARD_MERGE_COMMENT_TEMPLATE_PATH",
    )
    stale_rejection_template_path: str = Field(
        default="dev/leaderboard/templates/stale_rejection_message.md",
        alias="LEADERBOARD_STALE_REJECTION_TEMPLATE_PATH",
    )
    mutated_pr_rejection_template_path: str = Field(
        default="dev/leaderboard/templates/mutated_pr_rejection_message.md",
        alias="LEADERBOARD_MUTATED_PR_REJECTION_TEMPLATE_PATH",
    )

    @field_validator("leaderboard_hf_repo", "hf_token")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        """Ensure required string settings are not blank."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("must be non-empty")
        return stripped


@lru_cache(maxsize=1)
def get_hf_sync_settings() -> HFSyncSettings:
    """Load and cache validated HF sync settings from environment."""
    try:
        return HFSyncSettings.model_validate(
            {
                "LEADERBOARD_HF_REPO": os.environ.get("LEADERBOARD_HF_REPO"),
                "HF_TOKEN": os.environ.get("HF_TOKEN"),
                "GITHUB_OUTPUT": os.environ.get("GITHUB_OUTPUT"),
                "LEADERBOARD_MERGE_COMMENT_TEMPLATE_PATH": os.environ.get(
                    "LEADERBOARD_MERGE_COMMENT_TEMPLATE_PATH",
                    "dev/leaderboard/templates/merge_comment.md",
                ),
                "LEADERBOARD_STALE_REJECTION_TEMPLATE_PATH": os.environ.get(
                    "LEADERBOARD_STALE_REJECTION_TEMPLATE_PATH",
                    "dev/leaderboard/templates/stale_rejection_message.md",
                ),
                "LEADERBOARD_MUTATED_PR_REJECTION_TEMPLATE_PATH": os.environ.get(
                    "LEADERBOARD_MUTATED_PR_REJECTION_TEMPLATE_PATH",
                    "dev/leaderboard/templates/mutated_pr_rejection_message.md",
                ),
            }
        )
    except ValidationError as exc:
        raise RuntimeError(f"Invalid HF sync settings: {exc}") from exc
