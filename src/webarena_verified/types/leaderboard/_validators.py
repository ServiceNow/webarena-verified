"""Shared validators for leaderboard types."""

import re
from pathlib import PurePosixPath

RFC3339_UTC_Z_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SUBMISSION_NAME_MAX_LENGTH = 64


def validate_rfc3339_utc_z(value: str, field_name: str = "timestamp") -> str:
    """Validate a timestamp is RFC3339 UTC with trailing Z."""
    if not RFC3339_UTC_Z_PATTERN.match(value):
        raise ValueError(f"{field_name} must be RFC3339 UTC ending with 'Z' (e.g. 2026-02-07T12:00:00Z)")
    return value


def validate_sha256_hex(value: str, field_name: str = "sha256") -> str:
    """Validate a lowercase 64-char SHA256 hex string."""
    if not SHA256_HEX_PATTERN.match(value):
        raise ValueError(f"{field_name} must be a lowercase 64-character SHA256 hex string")
    return value


def validate_relative_repo_path(value: str, field_name: str = "path") -> str:
    """Validate a repo-relative POSIX path without traversal segments."""
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")

    path = PurePosixPath(value)
    if path.is_absolute():
        raise ValueError(f"{field_name} must be a relative path")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"{field_name} must not contain '..' segments")
    if any(part in {"", "."} for part in path.parts):
        raise ValueError(f"{field_name} must not contain empty or '.' segments")

    return value


def validate_submission_name(value: str, field_name: str = "name") -> str:
    if len(value) > SUBMISSION_NAME_MAX_LENGTH:
        raise ValueError(f"{field_name} must be at most {SUBMISSION_NAME_MAX_LENGTH} characters")
    return value


def validate_model_name(value: str, field_name: str = "model") -> str:
    if not MODEL_PATTERN.match(value):
        raise ValueError(f"{field_name} must match ^[A-Za-z0-9._-]+$ (e.g. MySystem-v1)")
    return value


def validate_http_url(value: str, field_name: str) -> str:
    """Validate HTTP(S) URL shape."""
    if not value.startswith(("http://", "https://")):
        raise ValueError(f"{field_name} must be an http(s) URL")
    return value


def validate_email(value: str, field_name: str = "contact_email") -> str:
    """Validate email address format."""
    if not EMAIL_PATTERN.match(value):
        raise ValueError(f"{field_name} must be a valid email address")
    return value


def validate_probability(value: float, field_name: str) -> float:
    """Validate probability-style score in [0, 1]."""
    if 0 <= value <= 1:
        return value
    raise ValueError(f"{field_name} must be within [0, 1]")


def validate_probability_or_missing_sentinel(value: float, field_name: str) -> float:
    """Validate score in [0, 1] or sentinel -1 for unavailable values."""
    if value == -1:
        return value
    if 0 <= value <= 1:
        return value
    raise ValueError(f"{field_name} must be within [0, 1] or exactly -1")
