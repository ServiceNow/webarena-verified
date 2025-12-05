"""JSON string data type for normalized comparison."""

import json
from typing import Any

from .base import NormalizedType


class JsonString(NormalizedType[str]):
    """JSON string normalization with sorted keys.

    This type parses JSON strings and normalizes them to a compact format with sorted keys
    at the top level. This allows structural comparison of JSON objects regardless of key
    ordering or whitespace formatting.

    Input must be a string containing valid JSON. Non-string inputs will raise ValueError.

    Alternatives: To specify alternative valid values, pass a list of 2+ JSON strings:
        JsonString(['{"a": 1}', '{"b": 2}'])  # Two alternative JSON objects

    Examples:
        >>> JsonString('{"b": 1, "a": 2}')
        JsonString('{"a":2,"b":1}')

        >>> JsonString('[2, 1, 3]')
        JsonString('[2,1,3]')

        >>> JsonString('[]')
        JsonString('[]')
    """

    def _type_normalize(self, value: Any) -> str:
        """Normalize JSON string to a compact format with sorted keys.

        Args:
            value: Must be a string containing valid JSON

        Returns:
            Compact JSON string with sorted keys (at top level only)

        Raises:
            ValueError: If value is not a string, is empty, or is invalid JSON
        """
        # Only accept strings
        if not isinstance(value, str):
            raise ValueError(f"JsonString only accepts string input. Got {type(value).__name__}: {value!r}")

        # Handle empty strings
        if not value:
            raise ValueError("JSON string is empty")

        # Parse JSON string
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {value!r}") from e

        # Dump to compact string with sorted keys (top-level only)
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
