"""Published leaderboard data types."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from ._validators import (
    validate_probability,
    validate_probability_or_missing_sentinel,
    validate_rfc3339_utc_z,
    validate_sha256_hex,
)

OverallScore = Annotated[float, AfterValidator(lambda v: validate_probability(v, "overall_score"))]
SiteScore = Annotated[float, AfterValidator(lambda v: validate_probability_or_missing_sentinel(v, "site_score"))]


class LeaderboardRow(BaseModel):
    """Single leaderboard entry row."""

    model_config = ConfigDict(extra="allow")

    rank: int = Field(ge=1)
    submission_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    overall_score: OverallScore

    shopping_score: SiteScore
    reddit_score: SiteScore
    gitlab_score: SiteScore
    wikipedia_score: SiteScore
    map_score: SiteScore
    shopping_admin_score: SiteScore

    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    webarena_verified_version: str = Field(min_length=1)
    checksum: str

    @field_validator("checksum")
    @classmethod
    def validate_checksum(cls, value: str) -> str:
        """Validate checksum hash format."""
        return validate_sha256_hex(value, "checksum")


class LeaderboardTableFile(BaseModel):
    """Published table file for either full or hard board."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    generated_at_utc: str
    leaderboard: Literal["full", "hard"]
    rows: list[LeaderboardRow]

    @field_validator("generated_at_utc")
    @classmethod
    def validate_generated_at_utc(cls, value: str) -> str:
        """Validate table timestamp format."""
        return validate_rfc3339_utc_z(value, "generated_at_utc")
