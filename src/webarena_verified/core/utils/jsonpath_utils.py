"""JSONPath utilities for extracting values from nested data structures.

This module provides helpers for using JSONPath expressions to extract specific
values from nested dictionaries, particularly useful for validating deeply nested
post_data and response_content in network events.
"""

import json
import logging
import re
from typing import Any

from jsonpath_ng.exceptions import JsonPathParserError
from jsonpath_ng.ext import parse

from .pattern_utils import is_regexp

logger = logging.getLogger(__name__)


def is_regexp_jsonpath_key(key: str) -> bool:
    r"""Check if a key is a JSONPath-style regex pattern ($.^....$).

    This format combines JSONPath prefix with regex for clarity/consistency.
    The "$." prefix indicates a special key (like JSONPath), while the
    "^...$" portion is the regex pattern for key matching.

    Args:
        key: The key to check

    Returns:
        True if the key matches the $.^...$ pattern

    Examples:
        >>> is_regexp_jsonpath_key("$.^reply_to_submission_\\d+\\[comment\\]$")
        True
        >>> is_regexp_jsonpath_key("^reply_to_submission_\\d+\\[comment\\]$")
        False
        >>> is_regexp_jsonpath_key("$.note.note")
        False
    """
    return isinstance(key, str) and key.startswith("$.^") and key.endswith("$")


def is_jsonpath_key(key: str) -> bool:
    r"""Check if a key is a JSONPath expression or regex pattern.

    Detects:
    - JSONPath: "$." prefix (e.g., "$.note.note")
    - Regex JSONPath: "$.^" prefix with "$" suffix (e.g., "$.^pattern$")
    - Legacy regex: "^" prefix with "$" suffix (e.g., "^pattern$")

    Args:
        key: The key to check

    Returns:
        True if the key is a JSONPath expression or regex pattern, False otherwise

    Examples:
        >>> is_jsonpath_key("$.note.note")
        True
        >>> is_jsonpath_key("user_id")
        False
        >>> is_jsonpath_key("$")
        True
        >>> is_jsonpath_key("$.^reply_to_submission_\\d+\\[comment\\]$")
        True
        >>> is_jsonpath_key("^reply_to_submission_\\d+\\[comment\\]$")
        True
    """
    return isinstance(key, str) and (key.startswith("$") or is_regexp(key))


def deserialize_nested_json(data):
    """
    Recursively deserialize JSON string fields.

    Args:
        data: The data structure to process
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    result[key] = value  # Keep original if not valid JSON
            else:
                result[key] = deserialize_nested_json(value)
        return result
    elif isinstance(data, list):
        return [deserialize_nested_json(item) for item in data]
    else:
        return data


def _extract_by_regex_key(data: dict | list, pattern: str, strict: bool) -> Any:
    r"""Extract values from data by matching keys with a regex pattern.

    This is used when the path is a regex pattern (starts with ^ and ends with $)
    instead of a JSONPath expression. Only works on dict data at the root level.

    Args:
        data: Dictionary or list to search
        pattern: Regular expression pattern to match against keys
        strict: If True, raise error when not exactly 1 match.
                If False, return None when != 1 match.

    Returns:
        The extracted value if exactly 1 match found, or None in non-strict mode
        when matches != 1

    Raises:
        ValueError: In strict mode, if matches != 1 or if data is not a dict

    Examples:
        >>> data = {"reply_to_submission_2[comment]": "good book!"}
        >>> _extract_by_regex_key(data, r"^reply_to_submission_\d+\[comment\]$", strict=False)
        'good book!'
    """
    if not isinstance(data, dict):
        if strict:
            raise ValueError(f"Regex key matching requires dict data, got {type(data).__name__}")
        logger.debug(f"Regex key matching requires dict data, got {type(data).__name__}")
        return None

    try:
        regex = re.compile(pattern)
    except re.error as e:
        error_msg = f"Invalid regex pattern '{pattern}': {e}"
        if strict:
            raise ValueError(error_msg) from e
        logger.warning(error_msg)
        return None

    # Find all matching keys
    matches = [(key, value) for key, value in data.items() if regex.match(key)]

    if len(matches) == 1:
        return matches[0][1]  # Return the value
    elif len(matches) > 1:
        # Return tuple for multiple matches in non-strict mode
        if not strict:
            return tuple(value for _, value in matches)
        raise ValueError(f"Regex pattern '{pattern}' matched {len(matches)} keys, expected exactly 1")

    # No matches
    if strict:
        raise ValueError(f"Regex pattern '{pattern}' matched 0 keys, expected exactly 1")

    logger.debug(f"Regex pattern '{pattern}' matched 0 keys")
    return None


def extract_jsonpath_value(data: dict | list, path: str, strict: bool) -> Any:
    """Extract value from data using JSONPath expression or regex key matching.

    Supports two modes:
    1. JSONPath mode (default): Standard JSONPath expressions (e.g., "$.note.note")
    2. Regex mode: Pattern starts with ^ and ends with $ (e.g., "^reply_to_submission_\\d+\\[comment\\]$")
       - Matches top-level dictionary keys using regex
       - Useful when key names are dynamic or contain special characters

    Behavior depends on strict mode:
    - strict=True: Raises ValueError if matches != 1 (for validating expected config)
    - strict=False: Returns None if matches != 1 (for extracting actual values)

    Args:
        data: Dictionary or list to query
        path: JSONPath expression or regex pattern
        strict: If True, raise error when not exactly 1 match.
                If False, return None when != 1 match (or tuple for multiple with filter expressions).

    Returns:
        - Single value: if exactly 1 match found (and no filter expression in path)
        - Tuple: if multiple matches found, or filter expression used in JSONPath
        - None: in non-strict mode when 0 matches

    Raises:
        ValueError: In strict mode, if matches != 1 or invalid JSONPath/regex syntax
        JsonPathParserError: If the JSONPath expression is malformed

    Examples:
        JSONPath mode:
        >>> data = {"note": {"noteable_type": "MergeRequest", "note": "lgtm"}}
        >>> extract_jsonpath_value(data, "$.note.note", strict=True)
        'lgtm'

        >>> data = {"user_id": "123"}
        >>> extract_jsonpath_value(data, "$.note.note", strict=False)
        None

        Regex mode (JSONPath-style):
        >>> data = {"reply_to_submission_2[comment]": "good book!"}
        >>> extract_jsonpath_value(data, "$.^reply_to_submission_\\d+\\[comment\\]$", strict=False)
        'good book!'

        Regex mode (legacy):
        >>> data = {"reply_to_submission_2[comment]": "good book!"}
        >>> extract_jsonpath_value(data, "^reply_to_submission_\\d+\\[comment\\]$", strict=False)
        'good book!'
    """
    # Handle $.^regex$ format - strip "$." prefix and use regex matching
    if is_regexp_jsonpath_key(path):
        regex_pattern = path[2:]  # Remove "$." prefix, leaving "^....$"
        return _extract_by_regex_key(data, regex_pattern, strict)

    # Auto-detect pure regex pattern mode (legacy support)
    if is_regexp(path):
        return _extract_by_regex_key(data, path, strict)

    # Standard JSONPath mode
    try:
        jsonpath_expr = parse(path)
    except JsonPathParserError as e:
        error_msg = f"Invalid JSONPath expression '{path}': {e}"
        if strict:
            raise ValueError(error_msg) from e
        logger.warning(error_msg)
        return None

    matches = jsonpath_expr.find(data)
    if not matches:
        # Try deserializing nested JSON strings in common fields
        deserialized_data = deserialize_nested_json(data)
        matches = jsonpath_expr.find(deserialized_data)

    if len(matches) == 1 and "?(" not in path:
        # $() marks a filter expression which may validly return multiple matches
        return matches[0].value
    elif len(matches) >= 1:
        return tuple(m.value for m in matches)

    if strict:
        raise ValueError(f"JSONPath '{path}' matched {len(matches)} values, expected exactly 1")

    # Non-strict mode: return None for 0 or multiple matches
    if len(matches) == 0:
        logger.debug(f"JSONPath '{path}' matched 0 values in actual data")
    else:
        logger.debug(f"JSONPath '{path}' matched {len(matches)} values, expected exactly 1")

    return None
