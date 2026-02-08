"""Shared validators for leaderboard types."""

import re

RFC3339_UTC_Z_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def validate_rfc3339_utc_z(value: str, field_name: str) -> str:
    """Validate a timestamp is RFC3339 UTC with trailing Z."""
    if not RFC3339_UTC_Z_PATTERN.match(value):
        raise ValueError(f"{field_name} must be RFC3339 UTC ending with 'Z' (e.g. 2026-02-07T12:00:00Z)")
    return value


def validate_sha256_hex(value: str, field_name: str) -> str:
    """Validate a lowercase 64-char SHA256 hex string."""
    if not SHA256_HEX_PATTERN.match(value):
        raise ValueError(f"{field_name} must be a lowercase 64-character SHA256 hex string")
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
