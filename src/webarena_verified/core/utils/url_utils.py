"""Shared URL utility functions for query parameter handling.

This module provides utilities for:
- Extracting base64-encoded query parameters from URL paths
- Normalizing query strings to immutable QueryParams format
"""

import base64
import re
from types import MappingProxyType
from urllib.parse import parse_qs, unquote

from webarena_verified.types.common import QueryParams


def extract_base64_query(path: str) -> tuple[str, list[str]]:
    """Extract and decode base64-encoded query parameters from URL path.

    Searches for URL-safe base64-like segments in the path, attempts to decode them,
    and returns both a cleaned path (with base64 segments removed) and a list of
    decoded query strings.

    Args:
        path: URL path that may contain base64-encoded segments

    Returns:
        Tuple of (cleaned_path, [decoded_query_strings])
        - cleaned_path: Path with base64 segments removed
        - decoded_query_strings: List of decoded query strings (e.g., ["key=value&foo=bar"])

    Example:
        >>> path = "/api/dXNlcj1hZG1pbiZwYXNzPTEyMw/data"
        >>> extract_base64_query(path)
        ("/api/data", ["user=admin&pass=123"])
    """
    if not path:
        return path, []

    # Pattern: look for URL-safe base64-like segments (entire segment)
    # Must be at least 4 characters, can end with 0-2 padding chars (=)
    base64_pattern = re.compile(r"^[A-Za-z0-9_-]{4,}={0,2}$")

    segments = path.split("/")
    decoded_queries: list[str] = []

    for idx, segment in enumerate(segments):
        # Skip empty segments or segments that don't match base64 pattern
        if not segment or not base64_pattern.match(segment):
            continue

        # Add padding if needed (base64 requires length divisible by 4)
        padded = segment + "=" * ((4 - len(segment) % 4) % 4)

        try:
            # Decode base64
            decoded_bytes = base64.urlsafe_b64decode(padded)
            decoded_str = decoded_bytes.decode("utf-8")
        except Exception:
            # Not valid base64 or UTF-8, skip this segment
            continue

        # Check if decoded string looks like a query string (contains '=')
        if "=" not in decoded_str:
            continue

        # Unquote and clean the query string
        query_string = unquote(decoded_str).strip()
        if query_string:
            # Remove leading '?' or '&' if present
            decoded_queries.append(query_string.lstrip("?&"))
            # Mark segment for removal
            segments[idx] = ""

    # Reconstruct cleaned path without base64 segments
    cleaned_segments = [segment for segment in segments if segment]

    if cleaned_segments:
        cleaned_path = "/".join(cleaned_segments)
        # Preserve leading/trailing slashes from original path
        if path.startswith("/"):
            cleaned_path = "/" + cleaned_path
        if path.endswith("/") and cleaned_path and not cleaned_path.endswith("/"):
            cleaned_path += "/"
    else:
        # All segments removed - preserve leading slash if present
        cleaned_path = "/" if path.startswith("/") else ""

    return cleaned_path, decoded_queries


def normalize_query(query_string: str) -> QueryParams:
    """Parse and normalize query parameters to QueryParams format.

    Converts a URL query string into the standardized QueryParams format:
    - Keys are unquoted parameter names
    - Values are immutable tuples of sorted, unquoted parameter values
    - Preserves all values for duplicate parameters (e.g., "tag=a&tag=b")

    Args:
        query_string: URL query string (without leading '?')

    Returns:
        dict[str, tuple[str, ...]] with sorted values for each key

    Example:
        >>> normalize_query("tag=python&tag=code&user=admin")
        {"tag": ("code", "python"), "user": ("admin",)}

        >>> normalize_query("")
        {}
    """
    if not query_string:
        return MappingProxyType({})

    # Parse query string (handles duplicates as lists, keeps blank values)
    parsed = parse_qs(query_string, keep_blank_values=True)

    normalized: dict[str, tuple[str, ...]] = {}
    for key, values in parsed.items():
        # Unquote key and values
        normalized_key = unquote(key)
        # Sort values for consistent ordering and convert to tuple (immutable)
        normalized_values = tuple(sorted(unquote(value) for value in values))
        normalized[normalized_key] = normalized_values

    return MappingProxyType(normalized)
