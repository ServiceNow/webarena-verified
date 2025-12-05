"""Empty/null value normalization.

Handles various representations of missing or null data:
- Empty values: None, "", []
- Text representations: "n/a", "na", "nan", "null", "none"
- Case-insensitive matching

All normalize to a sentinel value for consistent comparison.
"""

import re
from decimal import Decimal
from typing import Any, ClassVar

from .base import NormalizedType


class Empty(NormalizedType[type[None]]):
    """Empty/null value normalization.

    Normalizes various representations of missing/empty data to None.

    Accepts:
    - Empty values: None, "", [], {}
    - Text representations (case-insensitive):
      - "n/a", "na", "N/A"
      - "nan", "NaN"
      - "null", "NULL"
      - "none", "None"
      - Any whitespace-only string

    All normalize to None for consistent comparison.

    Examples:
        >>> Empty(None).normalized
        None
        >>> Empty("").normalized
        None
        >>> Empty("N/A").normalized
        None
        >>> Empty("na").normalized
        None

        >>> Empty("N/A") == Empty("")
        True
        >>> Empty(None) == Empty("na")
        True
    """

    # Text patterns that represent empty/null values (after normalization)
    EMPTY_PATTERNS: ClassVar[set[str]] = {
        "n/a",
        "na",
        "nan",
        "null",
        "none",
    }

    def _type_normalize(self, value: Any) -> None:
        """Normalize various empty representations to None.

        Args:
            value: Any value to check for emptiness

        Returns:
            Always returns None (sentinel for empty)

        Raises:
            ValueError: If value is not an empty representation
        """
        # Check for direct empty values
        if not value:
            if isinstance(value, (int, float, Decimal)):
                raise ValueError("Numeric zero is not considered empty")
            return None

        # Check for string representations
        if isinstance(value, str) and value in self.EMPTY_PATTERNS:
            return None

        # Value is not an empty representation
        raise ValueError(
            f"Value is not an empty representation: {value!r}. "
            f"Expected one of: None, '', [], {{}}, or text like 'N/A', 'na', 'nan', 'null', 'none'"
        )

    def _normalize_string(self, s: str) -> str:
        """Override string normalization to preserve slashes.

        We want "N/A" to remain "n/a" after normalization, not "na".
        But we still want case-folding and whitespace normalization.
        Also handle "N / A" (with spaces) -> "n/a".
        """
        if not s:
            return s

        # Simple normalization: lowercase, strip, normalize whitespace
        # Don't use base class normalization which removes special chars
        s = s.strip().lower()
        # Normalize whitespace (including around slashes)
        s = re.sub(r"\s+", " ", s)
        # Remove spaces around slashes: "n / a" -> "n/a"
        s = re.sub(r"\s*/\s*", "/", s)

        return s
