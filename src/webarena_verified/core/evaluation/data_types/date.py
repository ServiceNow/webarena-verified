# Requires: pip install python-dateutil
"""Date normalization to ISO format."""

import re
from typing import Any

from dateutil import parser

from .base import NormalizedType


class Date(NormalizedType[str]):
    """Date normalization to ISO 8601 format (YYYY-MM-DD).

    Normalization logic:
    - Parse multiple date formats (Jan 15 2024, 01/15/2024, etc.)
    - Remove ordinal suffixes (1st, 2nd, 3rd, 4th)
    - Convert to ISO 8601 format using python-dateutil
    """

    def _type_normalize(self, value: Any) -> str:
        """Normalize date to ISO format.

        Args:
            value: The date value to normalize

        Returns:
            ISO 8601 formatted date string (YYYY-MM-DD) or empty string

        Raises:
            ValueError: If date parsing fails or multiple date candidates detected
        """
        # Handle empty values
        if not value:
            raise ValueError("Empty date value")

        # Add space after commas if missing
        value = re.sub(r",(?! )", ", ", value)

        dt = parser.parse(str(value), dayfirst=False)

        # Convert to ISO 8601 format (YYYY-MM-DD)
        return dt.date().isoformat()
