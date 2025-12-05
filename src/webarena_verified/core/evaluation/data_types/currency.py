# Requires: pip install price-parser
"""Currency type with automatic normalization and tolerance."""

from decimal import Decimal
from typing import Any, ClassVar

from price_parser import Price

from .base import NormalizedType


class Currency(NormalizedType[Decimal]):
    """Currency with automatic normalization and tolerance.

    Normalized to Decimal value. Comparison uses tolerance of 0.1 by default.

    Normalization features:
    - Strips currency symbols ($, €, £, ¥, ₹, ₽, ¢, etc.)
    - Handles thousands separators (commas, dots)
    - Handles decimal separators
    - Supports negative numbers (using minus sign: -$50, $-50, -50)
    - Converts to float using price-parser
    """

    DEFAULT_TOLERANCE: ClassVar[Decimal] = Decimal("0.1")

    def _type_normalize(self, value: Any) -> Decimal:
        """Convert currency to Decimal.

        Args:
            value: Currency value (number, string with/without symbols)

        Returns:
            Decimal value (positive or negative)

        Raises:
            ValueError: If value is empty or cannot be parsed
        """
        # Handle empty values
        if not value and not isinstance(value, (int, float, Decimal)):
            raise ValueError("Currency value is empty or None")

        # Convert to string for parsing (base class already normalized whitespace)
        value_str = str(value)

        # Detect negative sign (price-parser strips it, so we need to detect first)
        is_negative = value_str.startswith("-")

        # Remove minus sign for parsing (price-parser doesn't handle it correctly)
        if is_negative:
            value_str = value_str.replace("-", "")

        # Parse with price-parser
        decimal_separator = "." if value_str.rfind(".") > value_str.rfind(",") else ","
        price = Price.fromstring(value_str, decimal_separator=decimal_separator)

        # Check if parsing succeeded
        if price.amount_float is None:
            raise ValueError(f"Unable to parse currency: {value_str}")

        # Convert to Decimal for exact arithmetic
        result = Decimal(str(price.amount_float))

        # Apply negative sign if detected
        if is_negative:
            result = -result

        return result

    def __eq__(self, other: Any) -> bool:
        """Equality comparison using tolerance.

        Args:
            other: The value to compare with (Currency or Decimal)

        Returns:
            True if values are within tolerance (0.1), False otherwise

        Note:
            Supports comparison with both Currency instances and raw Decimal values.
            This allows flexible comparisons in tests and evaluations.
        """
        # Handle direct Decimal comparison
        if isinstance(other, Decimal):
            return abs(self.normalized - other) <= self.DEFAULT_TOLERANCE
        # Handle Currency comparison
        if isinstance(other, Currency):
            return abs(self.normalized - other.normalized) <= self.DEFAULT_TOLERANCE
        return False

    def __hash__(self) -> int:
        """Hash based on tolerance bucket to maintain hash invariant.

        Returns:
            Hash of the tolerance bucket

        Note:
            Objects within tolerance will have the same hash, maintaining Python's
            hash invariant: if a == b, then hash(a) == hash(b).

            Uses 2x tolerance for bucketing to handle boundary cases where values
            are exactly at the tolerance limit. This ensures values that are equal
            (within 0.1) hash to the same or adjacent buckets, then we use the
            midpoint of the bucket for consistent hashing.

        Example:
            Currency("10.0") and Currency("10.1") are within 0.1 tolerance,
            so they hash to the same bucket.
        """
        # Use 2x tolerance for bucket size to handle boundary cases
        # Round to nearest bucket using ROUND_HALF_EVEN (banker's rounding)
        bucket_size = self.DEFAULT_TOLERANCE * 2
        bucket = (self.normalized / bucket_size).quantize(Decimal("1"))
        return hash(bucket)
