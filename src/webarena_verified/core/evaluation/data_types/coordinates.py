# Requires: pip install geopy
"""Geographic coordinates normalization using geopy.

Supports parsing various coordinate formats:
- Dict: {"latitude": 40.7, "longitude": -74.0} or {"lat": 40.7, "lon": -74.0}
- List/Tuple: [40.7, -74.0] or (40.7, -74.0)
- String: "40.7, -74.0" or "40.7N, 74.0W" or various other formats
- geopy Point object

Uses geopy.Point for robust coordinate parsing and validation.
"""

from typing import Any, ClassVar

from geopy import Point

from .base import NormalizedType


class Coordinates(NormalizedType[dict]):
    """Geographic coordinates normalized to a latitude/longitude dict.

    Expected normalized representation:
        {"latitude": float, "longitude": float}

    Comparison uses default tolerance of 1e-5 degrees (~1.1m at equator).
    This tolerance accounts for typical GPS accuracy and OpenStreetMap data precision.

    Supports various input formats:
    - Dict: {"latitude": 40.7, "longitude": -74.0}
    - Dict (short keys): {"lat": 40.7, "lon": -74.0}
    - List/Tuple: [40.7, -74.0] or (40.7, -74.0)
    - String: "40.7, -74.0", "40.7N 74.0W", "40° 42' N, 74° 0' W"
    - geopy Point object

    Examples:
        >>> c = Coordinates("40.7128, -74.0060")
        >>> c.latitude
        40.7128
        >>> c.longitude
        -74.006

        >>> c = Coordinates([40.7128, -74.0060])
        >>> c.normalized
        {'latitude': 40.7128, 'longitude': -74.006}

        >>> c1 = Coordinates("40.7128, -74.0060")
        >>> c2 = Coordinates([40.7128, -74.0060])
        >>> c1 == c2
        True
    """

    DEFAULT_TOLERANCE: ClassVar[float] = 1e-5  # ~1.1 meters at equator

    def __init__(self, raw: Any, **kwargs):
        """Initialize Coordinates with special handling for list/tuple inputs.

        For Coordinates, a 2-element list [lat, lon] represents a SINGLE coordinate value,
        not a list of alternatives. This overrides the base class behavior.

        Args:
            raw: Coordinate value in various formats
            **kwargs: Additional parameters (ignored, for compatibility)
        """
        # Special case: A 2-element list/tuple is a coordinate pair, not alternatives
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            # Check if this looks like a coordinate pair (both elements are numeric or string)
            try:
                # Try to determine if this is [lat, lon] vs [alt1, alt2]
                # If both elements are numbers or parseable as coordinates, treat as single value
                is_coord_pair = all(isinstance(v, (int, float, str)) for v in raw)
                if is_coord_pair:
                    # This is a coordinate pair [lat, lon], not alternatives
                    # Bypass base class alternative detection
                    from copy import deepcopy

                    self._raw_value = deepcopy(raw)
                    self.alternatives = (self._normalize_pipeline(raw),)
                    self.normalized = self.alternatives[0]
                    return
            except Exception:
                pass  # Fall through to base class handling

        # For all other cases (dicts, strings, Point objects, actual alternatives), use base class
        super().__init__(raw, **kwargs)

    def _type_normalize(self, value: Any) -> dict:
        """Parse and validate coordinate formats using geopy.

        Args:
            value: Coordinate value in various formats

        Returns:
            Dict with validated latitude and longitude

        Raises:
            ValueError: If coordinate parsing or validation fails
        """
        if not value:
            raise ValueError("Coordinate value is empty or None")

        try:
            # Parse the value into a geopy Point
            point = self._parse_to_point(value)

            # Extract and validate coordinates
            latitude = point.latitude
            longitude = point.longitude

            # Validate latitude (longitude is already normalized by geopy to [-180, 180])
            self._validate_latitude(latitude)

            return {
                "latitude": latitude,
                "longitude": longitude,
            }

        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f"Unable to parse coordinates: {value!r}") from exc

    def _find_key_by_prefix(self, data: dict, prefix: str) -> str | None:
        """Find a key in the dictionary that starts with the given prefix.

        Args:
            data: Dictionary to search
            prefix: Prefix to match (e.g., "la" for latitude, "lo"/"lng" for longitude)

        Returns:
            The matching key, or None if no match found

        Note:
            If multiple keys match the prefix, returns the first match found.
            Keys are checked in dictionary iteration order.
            Special handling for "lng" variant which doesn't start with "lo".
            Keys must be valid prefixes of "latitude" or "longitude" words.
        """
        for key in data:
            if isinstance(key, str):
                key_lower = key.lower()
                # Handle latitude keys (must be a prefix of "latitude")
                if prefix == "la" and "latitude".startswith(key_lower) and len(key_lower) >= 2:
                    return key
                # Handle longitude keys (must be a prefix of "longitude" or exactly "lng")
                if prefix == "lo" and (
                    ("longitude".startswith(key_lower) and len(key_lower) >= 2) or key_lower == "lng"
                ):
                    return key
        return None

    def _parse_to_point(self, value: Any) -> Point:
        """Parse various input formats to a geopy Point.

        Args:
            value: Input value in various formats

        Returns:
            geopy.Point object

        Raises:
            ValueError: If parsing fails
        """
        # If already a Point, return it
        if isinstance(value, Point):
            return value

        # Dict format
        if isinstance(value, dict):
            # Use flexible key matching: any key starting with "la" for latitude, "lo" for longitude
            # This supports: lat, lati, latit, latitude, lon, long, longi, longitude, lng, etc.
            lat_key = self._find_key_by_prefix(value, "la")
            lon_key = self._find_key_by_prefix(value, "lo")

            if lat_key and lon_key:
                return Point(latitude=value[lat_key], longitude=value[lon_key])
            else:
                missing = []
                if not lat_key:
                    missing.append("latitude (key starting with 'la')")
                if not lon_key:
                    missing.append("longitude (key starting with 'lo')")
                raise ValueError(f"Dictionary must contain {' and '.join(missing)}")

        # List or tuple format: [lat, lon] or (lat, lon)
        if isinstance(value, (list, tuple)) and len(value) == 2:
            # Pass floats directly to geopy.Point to avoid precision loss
            return Point(latitude=value[0], longitude=value[1])

        # String format - let geopy parse it
        if isinstance(value, str):
            # geopy.Point can parse many formats:
            # - "40.7128, -74.0060"
            # - "40.7128 N, 74.0060 W"
            # - "40° 42' 46\" N, 74° 0' 21\" W"
            # - etc.
            try:
                return Point(value)
            except (ValueError, AttributeError) as exc:
                raise ValueError(f"Unable to parse coordinate string: {value!r}") from exc

        # Unsupported type
        raise ValueError(
            f"Unsupported coordinate input type: {type(value).__name__}. "
            f"Expected dict, list, tuple, string, or geopy.Point"
        )

    def _validate_latitude(self, latitude: float) -> None:
        """Validate latitude is within valid range.

        Args:
            latitude: Latitude value to validate

        Raises:
            ValueError: If latitude is out of range

        Note:
            Longitude validation is not needed because geopy.Point automatically
            normalizes longitude values to [-180, 180] range during construction.
            Latitude values outside [-90, 90] cause errors in geopy, so we validate them.
        """
        if not -90.0 <= latitude <= 90.0:
            raise ValueError(f"Latitude must be between -90 and 90 degrees, got {latitude}")

    def __eq__(self, other: Any) -> bool:
        """Equality comparison using tolerance-based comparison.

        Args:
            other: The value to compare with (must be a Coordinates instance)

        Returns:
            True if coordinates match within default tolerance

        Note:
            Uses DEFAULT_TOLERANCE for comparison. For custom tolerance,
            use _equals_with_tolerance() method directly.
        """
        if not isinstance(other, Coordinates):
            return False
        if self.normalized is None or other.normalized is None:
            return False
        return self._equals_with_tolerance(other, None)

    def _equals_with_tolerance(self, expected: "Coordinates", tolerance: float | None) -> bool:
        """Compare coordinates with component-wise tolerance.

        Note: This should only be called when both normalizations succeeded.

        Args:
            expected: Expected coordinate value
            tolerance: Optional tolerance override (default: 1e-6)

        Returns:
            True if coordinates match within tolerance
        """
        # Defensive assertions - these should never fail if called correctly from compare()
        assert isinstance(expected, Coordinates), (
            f"Type mismatch: cannot compare Coordinates with {expected.__class__.__name__}"
        )
        assert expected.normalized is not None, "Expected value must have valid normalization"
        assert self.normalized is not None, "Actual value must have valid normalization"

        actual_tolerance = tolerance if tolerance is not None else self.DEFAULT_TOLERANCE
        return (
            abs(self.normalized["latitude"] - expected.normalized["latitude"]) <= actual_tolerance
            and abs(self.normalized["longitude"] - expected.normalized["longitude"]) <= actual_tolerance
        )

    def __hash__(self) -> int:
        """Hash based on coordinate values for set operations.

        Returns:
            Hash of the coordinate tuple

        Note:
            Converts dict to tuple for hashing since dicts are unhashable.
            Consistent with __eq__ which compares normalized values.
        """
        if self.normalized is None:
            return hash(None)
        # Hash tuple of (latitude, longitude) for consistent hashing
        return hash((self.normalized["latitude"], self.normalized["longitude"]))

    @property
    def latitude(self) -> float:
        """Get latitude component.

        Returns:
            Latitude value

        Raises:
            ValueError: If normalization failed
        """
        if self.normalized is None:
            raise ValueError("Cannot access latitude: normalization failed")
        return self.normalized["latitude"]

    @property
    def longitude(self) -> float:
        """Get longitude component.

        Returns:
            Longitude value

        Raises:
            ValueError: If normalization failed
        """
        if self.normalized is None:
            raise ValueError("Cannot access longitude: normalization failed")
        return self.normalized["longitude"]

    def to_point(self) -> Point:
        """Convert to geopy Point object.

        Returns:
            geopy.Point object

        Raises:
            ValueError: If normalization failed
        """
        if self.normalized is None:
            raise ValueError("Cannot convert to Point: normalization failed")
        return Point(latitude=self.normalized["latitude"], longitude=self.normalized["longitude"])
