"""Utilities for detecting regex patterns in configuration values."""

from typing import Any


def is_regexp(value: Any) -> bool:
    """Check if a value is a regex pattern (string starting with ^ and ending with $).

    Args:
        value: The value to check (can be any type)

    Returns:
        True if value is a string pattern starting with ^ and ending with $, False otherwise

    Examples:
        >>> is_regexp("^hello$")
        True
        >>> is_regexp("hello")
        False
        >>> is_regexp(123)
        False
    """
    return isinstance(value, str) and len(value) >= 2 and value.startswith("^") and value.endswith("$")
