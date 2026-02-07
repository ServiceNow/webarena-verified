"""Leaderboard publish manifest types."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._validators import validate_rfc3339_utc_z, validate_sha256_hex


class LeaderboardManifest(BaseModel):
    """Atomic manifest pointing to a full/hard generation pair."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    generated_at_utc: str
    full_file: str = Field(min_length=1)
    hard_file: str = Field(min_length=1)
    full_sha256: str
    hard_sha256: str

    @field_validator("generated_at_utc")
    @classmethod
    def validate_generated_at_utc(cls, value: str) -> str:
        """Validate manifest timestamp format."""
        return validate_rfc3339_utc_z(value, "generated_at_utc")

    @field_validator("full_sha256")
    @classmethod
    def validate_full_sha256(cls, value: str) -> str:
        """Validate full file hash format."""
        return validate_sha256_hex(value, "full_sha256")

    @field_validator("hard_sha256")
    @classmethod
    def validate_hard_sha256(cls, value: str) -> str:
        """Validate hard file hash format."""
        return validate_sha256_hex(value, "hard_sha256")
