"""Duration normalization to timedelta format."""

import re
from datetime import timedelta
from typing import Any, ClassVar, cast

from pytimeparse2 import parse

from .base import NormalizedType


class Duration(NormalizedType[timedelta]):
    """Duration normalization to timedelta format.

    Supports multiple formats via pytimeparse2:
    - Compact: 32m, 2h32m, 1w3d2h32m
    - Verbose: 5 hours, 34 minutes, 56 seconds
    - Clock-style: 4:13, 4:13:02.266
    - Decimal: 1.2 minutes, 1.24 days
    - Mixed units: 1y2mo3w4d5h6m7s8ms

    Comparison uses tolerance: max(3 minutes absolute, 10% relative).
    This accounts for variability in travel time estimates from mapping services.
    """

    DEFAULT_TOLERANCE_SECONDS: ClassVar[float] = 180.0  # 3 minutes
    DEFAULT_TOLERANCE_PERCENT: ClassVar[float] = 0.10  # 10%

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any):
        """Custom Pydantic schema to serialize timedelta as string for JSON."""
        from pydantic_core import core_schema

        return core_schema.is_instance_schema(
            cls,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: str(instance.normalized),
                return_schema=core_schema.str_schema(),
            ),
        )

    def _type_normalize(self, value: Any) -> timedelta:
        """Convert duration to timedelta format.

        Args:
            value: Duration value with required format (e.g., "5 hours", "2h30m", "4:13")

        Returns:
            Duration as timedelta object

        Raises:
            ValueError: If duration parsing fails or if no unit/format is provided
        """
        # Handle empty values
        if not value:
            raise ValueError("Duration value is empty or None")

        if isinstance(value, timedelta):
            return value

        # Convert to string for parsing (base class already normalized whitespace)
        value_str = str(value)

        # Check if it's just a number without unit - reject it
        try:
            float(value_str)
            # If we get here, it's a plain number without unit
            raise ValueError("Duration must include a unit or time format (e.g., '5m', '2 hours', '4:13')")
        except ValueError as e:
            # If the ValueError is our custom message, re-raise it
            if "must include a unit" in str(e):
                raise
            # Otherwise, it's not a plain number, continue with pytimeparse2 parsing
            pass

        # Parse with pytimeparse2 to get seconds
        seconds_value = cast(int | float | None, parse(value_str))

        if seconds_value is None:
            raise ValueError(f"Unable to parse duration: {value_str}")

        # Convert to timedelta
        return timedelta(seconds=float(seconds_value))

    def _normalize_string(self, s: str) -> str:
        """Additional handling for duration strings"""
        normalized = super()._normalize_string(s)
        # Handle "1:35 hours"
        normalized = re.sub(r"(\d+):(\d+)\s*hours?", r"\1h\2m", normalized)
        return normalized

    def _to_seconds(self) -> float:
        """Convert primary normalized duration to total seconds.

        Returns:
            Total duration in seconds for the primary (first) alternative
        """
        return self.normalized.total_seconds()

    def __eq__(self, other: Any) -> bool:
        """Equality comparison using tolerance with alternatives support.

        Uses max(3 minutes absolute, 10% relative) tolerance to account for
        variability in travel time estimates from mapping services.

        Checks if ANY pair of alternatives from both sides is within tolerance,
        maintaining symmetry: A == B if and only if B == A.

        Args:
            other: The value to compare with (must be a Duration)

        Returns:
            True if any pair of alternatives is within tolerance, False otherwise
        """
        if not isinstance(other, Duration):
            return False

        # Check all pairs of alternatives for a match within tolerance
        for self_alt in self.alternatives:
            for other_alt in other.alternatives:
                self_seconds = self_alt.total_seconds()
                other_seconds = other_alt.total_seconds()

                # Calculate tolerance as max(absolute, relative * max_value)
                max_seconds = max(self_seconds, other_seconds)
                relative_tolerance = max_seconds * self.DEFAULT_TOLERANCE_PERCENT
                tolerance = max(self.DEFAULT_TOLERANCE_SECONDS, relative_tolerance)

                if abs(self_seconds - other_seconds) <= tolerance:
                    return True

        return False

    def __hash__(self) -> int:
        """Hash based on tolerance bucket to maintain hash invariant.

        Returns:
            Hash of the tolerance bucket

        Note:
            Objects within tolerance will have the same hash, maintaining Python's
            hash invariant: if a == b, then hash(a) == hash(b).

            Uses 2x tolerance for bucketing to handle boundary cases.
        """
        seconds = self._to_seconds()
        # Use absolute tolerance for bucket size (simpler, works for most cases)
        bucket_size = self.DEFAULT_TOLERANCE_SECONDS * 2
        bucket = int(seconds // bucket_size)
        return hash(bucket)
