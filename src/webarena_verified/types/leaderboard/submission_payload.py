"""Submission payload contracts used by submission PR CI validation."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._validators import validate_rfc3339_utc_z, validate_sha256_hex

NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SubmissionMetadata(BaseModel):
    """Metadata contract stored in payload metadata.json."""

    model_config = ConfigDict(extra="allow")

    submission_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    leaderboard: Literal["hard", "full", "both"]
    reference: str = Field(min_length=1)
    created_at_utc: str
    version: str | None = None
    contact_info: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate model/team name format."""
        if not NAME_PATTERN.match(value):
            raise ValueError("name must match ^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$")
        return value

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        """Validate reference URL format."""
        if not value.startswith(("http://", "https://")):
            raise ValueError("reference must be an http(s) URL")
        return value

    @field_validator("created_at_utc")
    @classmethod
    def validate_created_at_utc(cls, value: str) -> str:
        """Validate created timestamp format."""
        return validate_rfc3339_utc_z(value, "created_at_utc")

    @field_validator("contact_info")
    @classmethod
    def validate_contact_info(cls, value: str | None) -> str | None:
        """Validate optional contact email format."""
        if value is None:
            return None
        if not EMAIL_PATTERN.match(value):
            raise ValueError("contact_info must be a valid email address")
        return value


class SubmissionPayloadManifest(BaseModel):
    """Payload manifest contract stored in payload manifest.json."""

    model_config = ConfigDict(extra="allow")

    submission_id: str = Field(min_length=1)
    archive_file: Literal["payload.tar.zst"]
    archive_sha256: str
    archive_size_bytes: int = Field(gt=0)
    created_at_utc: str
    hf_pr_id: int | None
    hf_pr_url: str | None

    @field_validator("archive_sha256")
    @classmethod
    def validate_archive_sha256(cls, value: str) -> str:
        """Validate archive SHA256 format."""
        return validate_sha256_hex(value, "archive_sha256")

    @field_validator("created_at_utc")
    @classmethod
    def validate_created_at_utc(cls, value: str) -> str:
        """Validate created timestamp format."""
        return validate_rfc3339_utc_z(value, "created_at_utc")
