"""Utility to trim network log files by removing skipped resource types.

This module provides functionality to reduce HAR file sizes by removing entries
for static resources (CSS, JS, images, fonts) that are not evaluated during
task evaluation. It also sanitizes sensitive authorization headers from the
remaining entries while preserving Cookie and Set-Cookie headers.
"""

import json
import re
from pathlib import Path
from typing import Any

from webarena_verified.core.utils.network_event_utils import load_har_trace

# Sensitive header patterns to sanitize (case-insensitive)
# Note: Cookie and Set-Cookie don't match these patterns and are preserved
SENSITIVE_HEADER_PATTERNS = [
    r"^authorization$",
    r"^x-api-key$",
    r"^x-auth-token$",
    r"^x-api-secret$",
    r"auth",
    r"token",
    r"key",
    r"secret",
]


def _is_sensitive_header(header_name: str) -> bool:
    """Check if a header name is sensitive and should be sanitized.

    Args:
        header_name: Header name to check

    Returns:
        True if header should be sanitized, False otherwise
    """
    header_lower = header_name.lower()
    return any(re.search(pattern, header_lower) for pattern in SENSITIVE_HEADER_PATTERNS)


def _sanitize_headers(headers: list[dict[str, str]]) -> int:
    """Sanitize sensitive headers by redacting their values.

    Modifies headers in-place to redact sensitive values while preserving structure.

    Args:
        headers: List of header dicts with 'name' and 'value' keys

    Returns:
        Number of headers sanitized
    """
    sanitized_count = 0
    for header in headers:
        if _is_sensitive_header(header["name"]):
            header["value"] = "[REDACTED]"
            sanitized_count += 1
    return sanitized_count


def _sanitize_har_entries(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Sanitize sensitive headers from HAR entries.

    Args:
        entries: List of HAR entry dicts

    Returns:
        Dict with sanitization statistics:
        - request_headers_sanitized: Number of request headers sanitized
        - response_headers_sanitized: Number of response headers sanitized
    """
    request_headers_sanitized = 0
    response_headers_sanitized = 0

    for entry in entries:
        # Sanitize request headers
        if "request" in entry and "headers" in entry["request"]:
            request_headers_sanitized += _sanitize_headers(entry["request"]["headers"])

        # Sanitize response headers
        if "response" in entry and "headers" in entry["response"]:
            response_headers_sanitized += _sanitize_headers(entry["response"]["headers"])

    return {
        "request_headers_sanitized": request_headers_sanitized,
        "response_headers_sanitized": response_headers_sanitized,
    }


def trim_har_file(input_path: Path, output_path: Path) -> dict[str, Any]:
    """Trim HAR file by removing entries for skipped resource types and sanitizing sensitive headers.

    Uses NetworkEvent.is_evaluation_event logic to identify which entries
    to keep. Only evaluation events are preserved in the trimmed file.

    After filtering, sanitizes sensitive authorization headers from remaining entries:
    - Authorization (Bearer tokens, Basic auth, etc.)
    - X-API-Key, X-Auth-Token, X-API-Secret
    - Any header containing "auth", "token", "key", "secret" (case-insensitive)

    Note: Cookie and Set-Cookie headers are preserved and NOT sanitized.

    Args:
        input_path: Path to input HAR file
        output_path: Path to output trimmed HAR file

    Returns:
        Dict with statistics about the trimming and sanitization operation:
        - original_entries: Number of entries in original file
        - trimmed_entries: Number of entries in trimmed file
        - removed_entries: Number of entries removed
        - request_headers_sanitized: Number of request headers sanitized
        - response_headers_sanitized: Number of response headers sanitized
        - original_size: Size of original file in bytes
        - trimmed_size: Size of trimmed file in bytes
        - reduction_percent: Percentage reduction in file size

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If input file is not valid HAR format
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input HAR file not found: {input_path}")

    # Load HAR file
    har_data = json.loads(input_path.read_text())

    # Validate HAR structure
    if "log" not in har_data:
        raise ValueError("Invalid HAR format: missing 'log' field")
    if "entries" not in har_data["log"]:
        raise ValueError("Invalid HAR format: missing 'log.entries' field")

    original_entries = har_data["log"]["entries"]
    original_count = len(original_entries)

    # Load NetworkEvent objects to use is_evaluation_event logic
    network_events = load_har_trace(input_path)

    # Filter entries - keep only evaluation events
    # Use the same logic as NetworkTrace.evaluation_events
    trimmed_entries = [
        entry for event, entry in zip(network_events, original_entries, strict=True) if event.is_evaluation_event
    ]
    trimmed_count = len(trimmed_entries)
    removed_count = original_count - trimmed_count

    # Sanitize sensitive headers from trimmed entries
    sanitization_stats = _sanitize_har_entries(trimmed_entries)

    # Update HAR data with trimmed entries
    har_data["log"]["entries"] = trimmed_entries

    # Write trimmed HAR file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(har_data, indent=2))

    # Calculate file sizes
    original_size = input_path.stat().st_size
    trimmed_size = output_path.stat().st_size
    reduction_percent = ((original_size - trimmed_size) / original_size * 100) if original_size > 0 else 0

    return {
        "original_entries": original_count,
        "trimmed_entries": trimmed_count,
        "removed_entries": removed_count,
        "request_headers_sanitized": sanitization_stats["request_headers_sanitized"],
        "response_headers_sanitized": sanitization_stats["response_headers_sanitized"],
        "original_size": original_size,
        "trimmed_size": trimmed_size,
        "reduction_percent": reduction_percent,
    }
