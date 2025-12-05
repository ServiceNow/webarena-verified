"""US address normalization and comparison.

Composite type that normalizes complete US addresses using USPS standards:
- state: State name normalization (e.g., "California" -> "CA")
- postcode: ZIP code normalization (e.g., "12345-6789")
- street: USPS street type and directional abbreviations (e.g., "Main Street" -> "main st", "South" -> "s")
- Other fields: NormalizedString (city, house_number, name)
- scourgify: USPS Pub. 28 standard abbreviations for street types and directionals

Comparison is based on required fields only (city, state, street, house_number, postcode).
Optional fields like 'name' are normalized but ignored during comparison.
"""

from typing import Any, ClassVar

from scourgify import normalize_address_record

from .base import NormalizedType
from .location_name import LocationName
from .string import NormalizedString


class FullAddress(NormalizedType[dict]):
    """Full US address normalized to a structured dict.

    Expected normalized representation:
        {
            "city": str,
            "state": str,  # 2-letter postal abbreviation
            "street": str,
            "house_number": str,
            "postcode": str,  # 5-digit or ZIP+4 format
            "name": str | None  # optional, uses fuzzy matching for location names
        }

    Comparison uses only required fields: city, state, street, house_number, postcode.
    The optional 'name' field is normalized but ignored during comparison.

    Supports various input formats:
    - Dict: {"city": "San Francisco", "state": "CA", "street": "Main St",
             "house_number": "123", "postcode": "94102"}
    - Dict with full state name: {"city": "San Francisco", "state": "California", ...}
    - Dict with optional name: {"name": "Alice", "city": "San Francisco", ...}

    Examples:
        >>> addr = FullAddress({"city": "San Francisco", "state": "CA",
        ...                      "street": "Main St", "house_number": "123",
        ...                      "postcode": "94102"})
        >>> addr.city
        'san francisco'
        >>> addr.state
        'CA'

        >>> addr1 = FullAddress({"city": "SF", "state": "California",
        ...                       "street": "Main St", "house_number": "123",
        ...                       "postcode": "94102", "name": "Alice"})
        >>> addr2 = FullAddress({"city": "sf", "state": "CA",
        ...                       "street": "main st", "house_number": "123",
        ...                       "postcode": "94102", "name": "Bob"})
        >>> addr1 == addr2  # Names differ but addresses match
        True
    """

    REQUIRED_FIELDS: ClassVar[set[str]] = {"city", "state", "street", "house_number", "postcode"}
    OPTIONAL_FIELDS: ClassVar[set[str]] = {"name"}
    ALL_FIELDS: ClassVar[set[str]] = REQUIRED_FIELDS | OPTIONAL_FIELDS

    def _normalize_with_scourgify(
        self,
        house_number: str,
        street: str,
        city: str,
        state: str,
        postcode: str,
    ) -> dict:
        """Normalize address using scourgify (USPS Pub. 28 standards).

        Handles:
        - Street type abbreviations (Street -> ST, Drive -> DR, etc.)
        - Directional abbreviations (North -> N, South -> S, etc.)
        - Standardized formatting

        Args:
            house_number: House number
            street: Street name (may be full form or abbreviated)
            city: City name
            state: State (2-letter code or full name)
            postcode: ZIP code

        Returns:
            Dict with normalized fields using USPS abbreviations

        Example:
            >>> self._normalize_with_scourgify("123", "Main Street", "San Francisco", "CA", "94102")
            {'address_line_1': '123 MAIN ST', 'city': 'SAN FRANCISCO', 'state': 'CA', 'postal_code': '94102'}
        """
        # Build address line 1 (house number + street)
        address_line_1 = f"{house_number} {street}".strip()

        # Normalize using scourgify
        normalized = normalize_address_record(
            {
                "address_line_1": address_line_1,
                "city": city,
                "state": state,
                "postal_code": postcode,
            }
        )

        return dict(normalized)

    def _normalize_state(self, value: str) -> str:
        """Normalize state name or abbreviation to 2-letter postal code.

        Uses the `us` library to handle various state name formats.

        Args:
            value: State name or abbreviation (e.g., "California", "CA", "calif")

        Returns:
            2-letter uppercase postal abbreviation (e.g., "CA")

        Raises:
            ValueError: If state cannot be found or value is empty
        """
        import us

        if not value or not str(value).strip():
            raise ValueError("State value is empty")

        value_str = str(value).strip()

        # Lookup state using us library (supports name, abbreviation, FIPS, phonetic)
        state = us.states.lookup(value_str)

        if state is None:
            raise ValueError(f"Unable to find US state: {value_str}")

        return state.abbr

    def _normalize_postcode(self, value: str) -> str:
        """Normalize ZIP code format.

        Args:
            value: ZIP code (5 or 9 digits, with optional separators)

        Returns:
            Normalized ZIP code: "12345" or "12345-6789"

        Raises:
            ValueError: If value is empty or invalid format
        """
        import re

        if not value or not str(value).strip():
            raise ValueError("ZIP code value is empty")

        value_str = str(value).strip()

        # Extract only digits
        digits = re.sub(r"\D", "", value_str)

        # Validate length
        if len(digits) == 5:
            # 5-digit ZIP
            return digits
        elif len(digits) == 9:
            # ZIP+4: format as 12345-6789
            return f"{digits[:5]}-{digits[5:]}"
        else:
            raise ValueError(f"Invalid ZIP code length: expected 5 or 9 digits, got {len(digits)}")

    def _extract_and_normalize_from_parsed(
        self,
        parsed: dict,
        pre_normalized_state: str,
        pre_normalized_postcode: str,
    ) -> dict:
        """Extract components from usaddress parsed dict and apply final normalization.

        Args:
            parsed: Dict from usaddress.tag()
            pre_normalized_state: Already normalized state code
            pre_normalized_postcode: Already normalized postcode

        Returns:
            Dict with normalized address fields

        Raises:
            ValueError: If required fields are empty after normalization
        """
        # Extract house number
        house_number = parsed.get("AddressNumber", "")

        # Extract and combine street components
        street_parts = []
        for key in [
            "StreetNamePreDirectional",
            "StreetNamePreModifier",
            "StreetName",
            "StreetNamePostType",
            "StreetNamePostDirectional",
        ]:
            if key in parsed:
                street_parts.append(parsed[key])
        street = " ".join(street_parts)

        # Extract city
        city = parsed.get("PlaceName", "")

        # Extract name (optional)
        name = parsed.get("Recipient")

        # Apply NormalizedString for final normalization (case, whitespace, unicode)
        normalized = {
            "house_number": NormalizedString(house_number).normalized if house_number else "",
            "street": NormalizedString(street).normalized if street else "",
            "city": NormalizedString(city).normalized if city else "",
            "state": pre_normalized_state,  # Already normalized
            "postcode": pre_normalized_postcode,  # Already normalized
            "name": LocationName(name).normalized if name else None,
        }

        # Validate that required fields are not empty after normalization
        for field in ["house_number", "street", "city", "state", "postcode"]:
            if not normalized[field]:
                raise ValueError(f"Required field '{field}' is empty after normalization")

        return normalized

    def _type_normalize(self, value: Any) -> dict:
        """Parse and validate address dict using scourgify for USPS normalization.

        Flow:
        1. Validate dict structure and required fields
        2. Use scourgify to normalize with USPS Pub. 28 standards (abbreviations, etc.)
        3. Parse scourgify output to extract house_number and street
        4. Apply final lowercase normalization with NormalizedString
        5. Normalize state and postcode separately

        Args:
            value: Address dict with required and optional fields

        Returns:
            Dict with normalized address fields (all lowercase except state)

        Raises:
            ValueError: If value is empty, missing required fields, or invalid format
            TypeError: If value is not a dict
        """
        # Validate input
        if not value:
            raise ValueError("Address value is empty or None")

        if not isinstance(value, dict):
            raise TypeError(
                f"Address must be a dict, got {type(value).__name__}. Expected keys: {self.REQUIRED_FIELDS}"
            )

        # Validate required fields are present
        missing_fields = self.REQUIRED_FIELDS - set(value.keys())
        if missing_fields:
            raise ValueError(
                f"Missing required address fields: {missing_fields}. "
                f"Required: {self.REQUIRED_FIELDS}, Got: {set(value.keys())}"
            )

        try:
            # Normalize with scourgify (handles street abbreviations and directionals)
            scourgified = self._normalize_with_scourgify(
                house_number=value["house_number"],
                street=value["street"],
                city=value["city"],
                state=value["state"],
                postcode=value["postcode"],
            )

            # scourgify returns uppercase address_line_1 = "123 MAIN ST"
            # Split to get house_number and street separately
            address_line_1 = scourgified.get("address_line_1", "").strip()
            parts = address_line_1.split(maxsplit=1)  # Split on first space
            if len(parts) < 2:
                raise ValueError(f"Unable to parse address_line_1: {address_line_1}")

            scourgified_house_number = parts[0]
            scourgified_street = parts[1]

            # Normalize state and postcode separately (scourgify may not handle all formats)
            normalized_state = self._normalize_state(scourgified.get("state", value["state"]))
            normalized_postcode = self._normalize_postcode(scourgified.get("postal_code", value["postcode"]))

            # Apply final normalization with NormalizedString for lowercase/whitespace
            # (scourgify returns UPPERCASE, we want lowercase)
            normalized = {
                "house_number": NormalizedString(scourgified_house_number).normalized
                if scourgified_house_number
                else "",
                "street": NormalizedString(scourgified_street).normalized if scourgified_street else "",
                "city": NormalizedString(scourgified.get("city", value["city"])).normalized,
                "state": normalized_state,  # Keep uppercase state code
                "postcode": normalized_postcode,
                "name": LocationName(value.get("name")).normalized if value.get("name") else None,
            }

            # Validate that required fields are not empty after normalization
            for field in ["house_number", "street", "city", "state", "postcode"]:
                if not normalized[field]:
                    raise ValueError(f"Required field '{field}' is empty after normalization")

            return normalized

        except (ValueError, TypeError) as exc:
            raise ValueError(f"Unable to normalize address: {value!r}") from exc

    def __eq__(self, other: Any) -> bool:
        """Equality comparison using required fields only.

        Compares only: city, state, street, house_number, postcode.
        Ignores optional fields like 'name'.

        Args:
            other: The value to compare with (must be a FullAddress instance)

        Returns:
            True if required fields match, False otherwise
        """
        if not isinstance(other, FullAddress):
            return False
        if self.normalized is None or other.normalized is None:
            return False

        # Compare only required fields
        return all(self.normalized[field] == other.normalized[field] for field in self.REQUIRED_FIELDS)

    def __hash__(self) -> int:
        """Hash based on required fields only for set operations.

        Uses only: city, state, street, house_number, postcode.
        Ignores optional fields like 'name'.

        Returns:
            Hash of the required fields tuple

        Note:
            Consistent with __eq__ which compares required fields only.
        """
        if self.normalized is None:
            return hash(None)

        # Hash tuple of required fields only
        return hash(
            (
                self.normalized["city"],
                self.normalized["state"],
                self.normalized["street"],
                self.normalized["house_number"],
                self.normalized["postcode"],
            )
        )

    # Convenience properties for field access
    @property
    def city(self) -> str:
        """Get normalized city name.

        Returns:
            City name (normalized string)

        Raises:
            ValueError: If normalization failed
        """
        if self.normalized is None:
            raise ValueError("Cannot access city: normalization failed")
        return self.normalized["city"]

    @property
    def state(self) -> str:
        """Get normalized state abbreviation.

        Returns:
            2-letter state postal abbreviation (e.g., "CA")

        Raises:
            ValueError: If normalization failed
        """
        if self.normalized is None:
            raise ValueError("Cannot access state: normalization failed")
        return self.normalized["state"]

    @property
    def street(self) -> str:
        """Get normalized street name.

        Returns:
            Street name (normalized string)

        Raises:
            ValueError: If normalization failed
        """
        if self.normalized is None:
            raise ValueError("Cannot access street: normalization failed")
        return self.normalized["street"]

    @property
    def house_number(self) -> str:
        """Get normalized house number.

        Returns:
            House number (normalized string)

        Raises:
            ValueError: If normalization failed
        """
        if self.normalized is None:
            raise ValueError("Cannot access house_number: normalization failed")
        return self.normalized["house_number"]

    @property
    def postcode(self) -> str:
        """Get normalized postcode.

        Returns:
            Postcode in standard format (5-digit or ZIP+4)

        Raises:
            ValueError: If normalization failed
        """
        if self.normalized is None:
            raise ValueError("Cannot access postcode: normalization failed")
        return self.normalized["postcode"]

    @property
    def name(self) -> str | None:
        """Get normalized name (optional field).

        Returns:
            Name (normalized string) or None if not provided

        Raises:
            ValueError: If normalization failed
        """
        if self.normalized is None:
            raise ValueError("Cannot access name: normalization failed")
        return self.normalized.get("name")
