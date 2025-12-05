"""Utility functions for parsing network event content from HAR format."""

import json
import re
import zipfile
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

if TYPE_CHECKING:
    from webarena_verified.types.tracing import NetworkEvent


def parse_har_content(content: dict[str, Any]) -> dict[str, Any] | None:
    """Parse HAR content based on MIME type.

    Handles POST data and response content from HAR format:
    - application/x-www-form-urlencoded: dict with form parameters (first value only)
    - application/json: parsed JSON object (if it's a dict)
    - multipart/form-data: dict with form fields extracted from multipart boundaries
    - None: if content empty, or unsupported mimeType, or JSON is not an object

    Args:
        content: HAR content object with 'mimeType' and 'text' fields

    Returns:
        Parsed content as dict, or None if unable to parse
    """
    mime_type = content.get("mimeType", "")
    text = content.get("text", "")

    if not text:
        return None

    # Handle form-encoded data
    if "application/x-www-form-urlencoded" in mime_type:
        parsed = parse_qs(text, keep_blank_values=True)
        # Convert dict[str, list[str]] to dict[str, str] (first value only)
        return {k: v[0] if v else "" for k, v in parsed.items()}

    # Handle JSON data
    if "application/json" in mime_type:
        try:
            parsed = json.loads(text)
            # Only return if it's a dict, otherwise None
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Handle multipart/form-data
    if "multipart/form-data" in mime_type:
        # Extract boundary from mime type
        boundary_match = re.search(r"boundary=([^;\s]+)", mime_type)
        if boundary_match:
            boundary = boundary_match.group(1)
            return parse_multipart_form_data(text, boundary)

    return None


def parse_multipart_form_data(text: str, boundary: str) -> dict[str, str]:
    """Parse multipart/form-data content.

    Args:
        text: Raw multipart form data text
        boundary: Boundary string from Content-Type header

    Returns:
        dict[str, str]: Parsed form fields (first value only for each field)
    """
    result = {}

    # Split by boundary (add -- prefix as per RFC 2046)
    parts = text.split(f"--{boundary}")

    for part in parts:
        part = part.strip()
        # Skip empty parts and closing boundary marker
        if not part or part == "--":
            continue

        # Split headers from body
        if "\r\n\r\n" in part:
            headers, body = part.split("\r\n\r\n", 1)
        elif "\n\n" in part:
            headers, body = part.split("\n\n", 1)
        else:
            continue

        # Extract field name from Content-Disposition header
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                # Parse: Content-Disposition: form-data; name="fieldname"
                match = re.search(r'name="([^"]+)"', line)
                if match:
                    field_name = match.group(1)
                    # Clean up body (remove trailing \r\n)
                    field_value = body.rstrip("\r\n")
                    result[field_name] = field_value
                break

    return result


def load_playwright_trace(trace_path: Path) -> tuple["NetworkEvent", ...]:
    """Load NetworkEvent objects from Playwright trace file.

    Args:
        trace_path: Path to Playwright trace file (.zip or directory containing trace.network)

    Returns:
        Tuple of NetworkEvent objects from the trace

    Raises:
        FileNotFoundError: If trace file does not exist
    """
    # Avoid circular import
    from webarena_verified.types.tracing import NetworkEvent

    file_name = "trace.network"

    if trace_path.suffix == ".zip":
        with zipfile.ZipFile(trace_path, "r") as zip_ref:
            raw_data = zip_ref.read(file_name).decode("utf-8")
    else:
        trace_file = trace_path / file_name if trace_path.is_dir() else trace_path
        if not trace_file.exists():
            raise FileNotFoundError(f"Trace file {str(trace_file)!r} does not exist.")
        raw_data = trace_file.read_text(errors="ignore")

    data = []
    for line in raw_data.splitlines():
        item = json.loads(line)
        if item["type"] == "resource-snapshot":
            data.append(NetworkEvent(data=MappingProxyType(item["snapshot"])))

    return tuple(data)


def load_har_trace(har_path: Path) -> tuple["NetworkEvent", ...]:
    """Load NetworkEvent objects from HAR (HTTP Archive) file.

    HAR format: {"log": {"entries": [{"request": {...}, "response": {...}}, ...]}}

    Args:
        har_path: Path to HAR file (.har or .json)

    Returns:
        Tuple of NetworkEvent objects from HAR entries

    Raises:
        FileNotFoundError: If HAR file does not exist
        ValueError: If HAR format is invalid or contains no entries
    """
    # Avoid circular import
    from webarena_verified.types.tracing import NetworkEvent

    if not har_path.exists():
        raise FileNotFoundError(f"HAR file not found: {har_path}")

    har_data = json.loads(har_path.read_text())

    # Validate HAR structure
    if "log" not in har_data:
        raise ValueError("Invalid HAR format: missing 'log' field")
    if "entries" not in har_data["log"]:
        raise ValueError("Invalid HAR format: missing 'log.entries' field")

    entries = har_data["log"]["entries"]
    if not entries:
        raise ValueError("HAR file contains no entries")

    # Convert HAR entries to NetworkEvent objects
    # HAR entries already have the correct structure with request/response fields
    data = []
    for entry in entries:
        data.append(NetworkEvent(data=MappingProxyType(entry)))

    return tuple(data)


def load_trace_from_content(content: list[dict[str, Any]]) -> tuple[bool, tuple["NetworkEvent", ...]]:
    """Load NetworkEvent objects from raw trace content.

    Auto-detects format: Playwright uses "type": "resource-snapshot",
    HAR uses direct request/response structure.

    Args:
        content: List of trace event dictionaries (Playwright or HAR format)

    Returns:
        Tuple of (is_playwright, events) where is_playwright indicates the detected format

    Raises:
        ValueError: If content is empty, format is unknown, or no valid events found
    """
    # Avoid circular import
    from webarena_verified.types.tracing import NetworkEvent

    if not content:
        raise ValueError("Trace content list is empty")

    data = []
    first_item = content[0]

    # Detect format from first item
    if "type" in first_item and first_item["type"] == "resource-snapshot":
        # Playwright format
        for item in content:
            if item.get("type") == "resource-snapshot" and "snapshot" in item:
                data.append(NetworkEvent(data=MappingProxyType(item["snapshot"])))
        is_playwright = True
    elif "request" in first_item and "response" in first_item:
        # HAR format (entries list) - already has correct structure
        for entry in content:
            data.append(NetworkEvent(data=MappingProxyType(entry)))
        is_playwright = False
    else:
        raise ValueError(
            "Unknown trace format. Expected Playwright format with 'type': 'resource-snapshot' "
            "or HAR format with 'request' and 'response' fields"
        )

    if not data:
        raise ValueError(
            "No valid trace events found. Ensure format is correct: "
            'Playwright: {"type": "resource-snapshot", "snapshot": {...}} '
            'or HAR: {"request": {...}, "response": {...}}'
        )

    return is_playwright, tuple(data)
