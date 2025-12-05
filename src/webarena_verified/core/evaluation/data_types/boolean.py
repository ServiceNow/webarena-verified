"""Boolean normalization from various formats."""

from typing import Any

from .base import NormalizedType


class Boolean(NormalizedType[bool]):
    """Boolean normalization from various formats.

    Accepts:
    - True values: true, yes, y, 1, t, on
    - False values: false, no, n, 0, f, off
    - Case insensitive
    - Boolean and numeric types (bool, int, float)

    Raises ValueError for empty values (None, "", []) or unrecognized strings.
    """

    def _type_normalize(self, value: Any) -> bool:
        """Convert various boolean representations."""
        # Reject empty values
        if not value and not isinstance(value, (int, float, bool)):
            raise ValueError(f"Cannot normalize empty value to boolean: {value!r}")

        # Direct boolean
        if isinstance(value, bool):
            return value

        # Numeric types
        if isinstance(value, (int, float)):
            return bool(value)

        # String parsing
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "yes", "y", "1", "t", "on"):
                return True
            elif normalized in ("false", "no", "n", "0", "f", "off"):
                return False
            else:
                raise ValueError(f"Cannot normalize string to boolean: {value!r}")

        # Unrecognized type
        raise ValueError(f"Cannot normalize type {type(value).__name__} to boolean: {value!r}")
