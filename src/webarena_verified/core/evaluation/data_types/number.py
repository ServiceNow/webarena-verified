"""Numeric type without special formatting."""

from decimal import Decimal
from typing import Any

from word2number import w2n

from .base import NormalizedType


class Number(NormalizedType[float]):
    """Numeric type without special formatting.

    Simple numeric type for numbers without currency, distance, or other semantics.
    """

    def _type_normalize(self, value: Any) -> float:
        """Convert to float.

        Args:
            value: Numeric value (int, float, or string with optional commas)

        Returns:
            Float value

        Raises:
            ValueError: If value is empty or cannot be parsed as a number
        """
        # Handle empty values
        if not value and not isinstance(value, (int, float, Decimal)):
            raise ValueError("Number value is empty or None")

        # Handle numeric types directly
        if isinstance(value, (int, float)):
            return float(value)

        # Handle string representations
        value_str = str(value)

        # Remove commas and spaces from numeric strings
        # (e.g., "1,234.56" -> "1234.56", "1 0000" -> "10000")
        value_str = value_str.replace(",", "").replace(" ", "")

        try:
            return float(value_str)
        except ValueError:
            # Try word2number as fallback for text numbers (e.g., "twenty-three" -> 23.0)
            try:
                return float(w2n.word_to_num(str(value)))
            except ValueError as e:
                raise ValueError(f"Unable to parse number: {value}") from e
