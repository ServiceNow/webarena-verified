"""Month normalization to full month name."""

import calendar
from decimal import Decimal
from typing import Any

from dateutil import parser

from .base import NormalizedType


class Month(NormalizedType[str]):
    """Month normalization to full month name.

    Normalization logic:
    - Parse various month formats (numeric, abbreviated, full name)
    - Convert to full month name (e.g., "January", "February")
    - Handle case-insensitive input
    - Support numeric formats: "01", "1", "12"
    - Support abbreviations: "Jan", "Feb", "Sep"
    - Support full names: "January", "February"

    Examples:
        Month("01") → "January"
        Month("Jan") → "January"
        Month("JANUARY") → "January"
    """

    def _type_normalize(self, value: Any) -> str:
        """Normalize month to full month name.

        Args:
            value: The month value to normalize (string or number)

        Returns:
            Full month name (e.g., "January", "February")

        Raises:
            ValueError: If month parsing fails or value is invalid
        """
        # Handle empty values
        if not value and not isinstance(value, (int, float, Decimal)):
            raise ValueError("Empty month value")

        # Handle numeric types with validation for floats/decimals
        if isinstance(value, (int, float, Decimal)):
            # Check if it's a whole number
            if (isinstance(value, (float, Decimal))) and value != int(value):
                raise ValueError(f"Month must be a whole number, got: {value}")
            month_num = int(value)
            if 1 <= month_num <= 12:
                return calendar.month_name[month_num]
            else:
                raise ValueError(f"Month number out of range (1-12): {month_num}")

        # Convert to string for processing
        value_str = str(value).strip()

        # Handle empty string after strip
        if not value_str:
            raise ValueError("Empty month value")

        # Try to parse as pure numeric string month first (1-12 or 01-12)
        try:
            month_num = int(value_str)
            if 1 <= month_num <= 12:
                # It's a valid month number
                return calendar.month_name[month_num]
            else:
                # Out of range numeric value - don't try dateutil, just fail
                raise ValueError(f"Month number out of range (1-12): {month_num}")
        except ValueError as e:
            # If it's a range error, re-raise it
            if "out of range" in str(e):
                raise
            # Not a pure number, continue with dateutil parsing
            pass

        try:
            # Try to parse as month name or abbreviation using dateutil
            # Use a fixed date with day=1 to avoid ambiguity
            dt = parser.parse(value_str, default=parser.parse("2000-01-01"))
            month_num = dt.month

            # Validate month number
            if not 1 <= month_num <= 12:
                raise ValueError(f"Invalid month number: {month_num}")

            # Return full month name
            return calendar.month_name[month_num]

        except (ValueError, parser.ParserError) as e:
            raise ValueError(f"Unable to parse month: {value!r}") from e
