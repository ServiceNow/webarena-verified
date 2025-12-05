# Requires: pip install pint
"""Distance normalization to meters."""

import re
from decimal import ROUND_FLOOR, Decimal
from typing import Any, ClassVar

import pint

from .base import NormalizedType

# Create a unit registry for distance conversions
_ureg = pint.UnitRegistry()


class Distance(NormalizedType[Decimal]):
    """Distance normalization to meters.

    Normalized to Decimal value. Comparison uses tolerance-based equality with
    max(absolute, relative) threshold, suitable for map/routing distances.

    Supports various distance units:
    - Meters (m, meter, meters, metre, metres)
    - Kilometers (km, kilometer, kilometers, kilometre, kilometres)
    - Miles (mi, mile, miles)
    - Feet (ft, foot, feet)
    - Yards (yd, yard, yards)
    - Centimeters (cm, centimeter, centimeters, centimetre, centimetres)
    - Inches (in, inch, inches)
    """

    DEFAULT_TOLERANCE_METERS: ClassVar[Decimal] = Decimal("10")  # 10 meters absolute
    DEFAULT_TOLERANCE_PERCENT: ClassVar[Decimal] = Decimal("0.02")  # 2% relative

    def _type_normalize(self, value: Any) -> Decimal:
        """Convert distance to meters.

        Args:
            value: Distance value with required unit (e.g., "5 km", "100 m", "3.5 miles")

        Returns:
            Distance in meters as Decimal

        Raises:
            ValueError: If distance parsing or conversion fails, or if no unit is provided
        """
        # Handle empty values
        if not value and not isinstance(value, (int, float, Decimal)):
            raise ValueError("Distance value is empty or None")

        # Convert to string for parsing (base class already normalized whitespace)
        value_str = str(value)

        # Preprocess common abbreviations: "k" -> "km"
        # Matches patterns like "110k", "5.5k" and converts to "110 km", "5.5 km"
        value_str = re.sub(r"(\d+(?:\.\d+)?)\s*k(?=\s|$)", r"\1 km", value_str, flags=re.IGNORECASE)

        # Check if it's just a number without unit - reject it
        try:
            float(value_str)
            # If we get here, it's a plain number without unit
            raise ValueError("Distance must include a unit (e.g., 'm', 'km', 'mi', 'ft')")
        except ValueError as e:
            # If the ValueError is our custom message, re-raise it
            if "must include a unit" in str(e):
                raise
            # Otherwise, it's not a plain number, continue with pint parsing
            pass

        # Parse with pint (whitespace already normalized by base class)
        try:
            quantity = _ureg.parse_expression(value_str)
            # Convert to meters
            result = quantity.to(_ureg.meter)
            # Convert to Decimal for exact arithmetic
            return Decimal(str(result.magnitude))
        except pint.UndefinedUnitError as e:
            raise ValueError(f"Invalid or unsupported unit in distance: {value_str}") from e
        except pint.DimensionalityError as e:
            raise ValueError(f"Cannot convert to distance (meters): {value_str}") from e

    def _to_meters(self) -> Decimal:
        """Get the first alternative value in meters.

        Returns:
            Distance value in meters as Decimal
        """
        return self.alternatives[0]

    def __eq__(self, other: Any) -> bool:
        """Equality comparison using tolerance-based comparison.

        Uses max(absolute, relative) tolerance where:
        - Absolute tolerance: 10 meters
        - Relative tolerance: 2% of the larger value

        Args:
            other: The value to compare with (Distance instance)

        Returns:
            True if any pair of alternatives is within tolerance, False otherwise

        Note:
            Supports comparison between Distance instances with multiple alternatives.
            Returns True if ANY alternative from self matches ANY alternative from other.
        """
        if not isinstance(other, Distance):
            return False

        # Check all pairs of alternatives for a match within tolerance
        for self_meters in self.alternatives:
            for other_meters in other.alternatives:
                max_meters = max(self_meters, other_meters)
                relative_tolerance = max_meters * self.DEFAULT_TOLERANCE_PERCENT
                tolerance = max(self.DEFAULT_TOLERANCE_METERS, relative_tolerance)
                if abs(self_meters - other_meters) <= tolerance:
                    return True
        return False

    def __hash__(self) -> int:
        """Hash based on tolerance bucket to maintain hash invariant.

        Returns:
            Hash of the tolerance bucket

        Note:
            Objects with equal values must have equal hashes. Uses bucket-based
            hashing with bucket size of 2x the absolute tolerance to ensure
            values within tolerance range can hash to the same or adjacent buckets.

        Example:
            Distance("100 m") and Distance("105 m") may hash to the same bucket.
        """
        meters = self._to_meters()
        bucket_size = self.DEFAULT_TOLERANCE_METERS * 2
        bucket = (meters / bucket_size).to_integral_value(rounding=ROUND_FLOOR)
        return hash(bucket)
