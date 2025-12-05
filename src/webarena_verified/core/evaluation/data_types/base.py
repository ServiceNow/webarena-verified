"""Base class for normalized data types."""

import contextlib
import re
import unicodedata as ud
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Generic, TypeVar

from pydantic_core import core_schema
from unidecode import unidecode

from webarena_verified.core.utils import is_regexp

T = TypeVar("T")

# Regex pattern matching various hyphen-like Unicode characters when adjacent to letters.
# This normalizes "Buffalo-Niagara" → "Buffalo Niagara" but preserves "123-4567".
# Hyphen characters: - (U+002D), ‐ (U+2010), ‑ (U+2011), ‒ (U+2012), – (U+2013),
# — (U+2014), ― (U+2015), − (U+2212), ­ (U+00AD)
_HYPHEN_CHARS = r"[\u002D\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u00AD]"
_HYPHEN_PATTERN = re.compile(rf"(?<=[a-zA-Z]){_HYPHEN_CHARS}|{_HYPHEN_CHARS}(?=[a-zA-Z])")


class NormalizedType(Generic[T], ABC):
    """Base class for all normalized data types.

    Each subclass represents a specific data type (currency, date, state, etc.)
    and handles both normalization and comparison logic.

    The `normalized` attribute contains the normalized value after processing.
    Normalization failures raise exceptions - instances only exist when valid.

    Supports alternatives: when initialized with a list or tuple of 2+ items, each item is
    treated as a valid alternative value. Equality checks if the other value matches ANY
    alternative. Single-item lists are rejected to avoid ambiguity.
    """

    def __init__(self, raw: Any | list[Any], *, derender_url_fct=None, **kwargs):
        """Initialize with raw value(s) and normalize them.

        Args:
            raw: Single value or list/tuple of alternative values (requires 2+ items)

        Raises:
            ValueError: If normalization fails or if single-item list is provided

        Examples:
            NormalizedString('success')           # Single value
            NormalizedString(['success', 'ok'])   # Multiple alternatives (list, 2+ items)
            NormalizedString(('success', 'ok'))   # Multiple alternatives (tuple, 2+ items)
            NormalizedNumber(10)                  # Single value
            NormalizedNumber([10, 17])            # Multiple alternatives (2+ items)
        """
        self._raw_value = deepcopy(raw)

        # Store derender_url_fct for URL derendering in strings (best effort)
        # Default to no-op function (returns input unchanged)
        self.derender_url_fct = derender_url_fct

        # Detect alternatives: list/tuple with 2+ items means multiple valid values
        # Single-item lists are rejected to avoid ambiguity
        self.alternatives: tuple[T, ...]
        if isinstance(raw, (list, tuple)):
            if len(raw) < 2:
                raise ValueError(
                    f"Alternatives require 2+ items. Got {raw!r} with {len(raw)} item(s). "
                    f"Pass the value directly (not in a list)."
                )
            # Normalize each alternative
            self.alternatives = tuple(self._normalize_pipeline(v) for v in raw)
        else:
            # Single value - wrap in tuple for consistency
            self.alternatives = (self._normalize_pipeline(raw),)

        # For backwards compatibility - first alternative is the "primary" normalized value
        self.normalized: T = self.alternatives[0]

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> core_schema.CoreSchema:
        """Tell Pydantic how to serialize NormalizedType instances.

        This allows Pydantic to properly serialize all NormalizedType subclasses
        when they appear in Pydantic model fields. The serializer extracts the
        `.normalized` value for JSON output.

        Returns:
            CoreSchema that handles serialization for this type and all subclasses
        """
        return core_schema.is_instance_schema(
            cls,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: instance.normalized,
                return_schema=core_schema.any_schema(),
            ),
        )

    @property
    def raw(self) -> Any:
        """Get the original raw value before normalization."""
        return self._raw_value

    @property
    def is_regexp(self) -> bool:
        """Check if this normalized value is a regex pattern.

        Returns True if ANY alternative is a regex pattern (starts with ^ and ends with $).

        Returns:
            True if any alternative is a regex pattern, False otherwise

        Examples:
            >>> NormalizedString("^hello$").is_regexp
            True
            >>> NormalizedString("hello").is_regexp
            False
            >>> NormalizedString(["^hello$", "world"]).is_regexp
            True
        """
        # Check if any alternative is a pattern
        # For most types, alternatives are the normalized values (not raw strings)
        # So we need to convert back to string for pattern checking
        return any(is_regexp(str(alt)) for alt in self.alternatives)

    def _normalize_pipeline(self, value: Any) -> T:
        """Apply normalization pipeline.

        Pipeline steps:
        1. Unicode to ASCII conversion (for strings)
        2. Type-specific normalization

        Raises:
            Exception: If normalization fails
        """
        if isinstance(value, str):
            value = self._normalize_string(value)

        # Type-specific normalization (handles empty values internally)
        return self._type_normalize(value)

    @abstractmethod
    def _type_normalize(self, value: Any) -> T:
        """Type-specific normalization logic.

        Subclasses must implement this method and handle empty values (None, "", []).
        Should raise an exception if normalization cannot be performed.
        """
        pass

    def __eq__(self, other: Any) -> bool:
        """Equality comparison with alternatives support.

        Checks if there is ANY overlap between alternatives of both values.
        This ensures symmetric equality: A == B if and only if B == A.

        Args:
            other: The value to compare with (must be a valid NormalizedType)

        Returns:
            True if there is any overlap between alternatives, False otherwise

        Examples:
            # Expected with alternatives
            expected = NormalizedString(['success', 'ok'])
            # Actual without alternatives
            actual = NormalizedString('success')

            # Comparison is symmetric
            expected == actual  # True (because 'success' in both alternatives)
            actual == expected  # True (because 'success' in both alternatives)
        """
        # Other value must be valid and same type
        if not isinstance(other, self.__class__):
            return False

        # Check if there's any overlap between alternatives
        # Convert to sets for efficient intersection check
        return bool(set(self.alternatives) & set(other.alternatives))

    def __hash__(self) -> int:
        """Hash based on normalized value(s) for set operations.

        Returns:
            Hash of the normalized value (single) or alternatives (multiple)

        Note:
            For single values: hash of the normalized value
            For alternatives: hash of sorted tuple of alternatives
        """
        return hash(self.get_str_for_hashing())

    def get_str_for_hashing(self) -> str:
        if len(self.alternatives) == 1:
            return str(self.alternatives[0])
        else:
            # For alternatives, use tuple hash
            # Sort for consistency (if values are comparable)
            try:
                return str(tuple(sorted(self.alternatives)))  # type: ignore[type-var]
            except TypeError:
                # If alternatives are not sortable, use unsorted tuple
                return str(tuple(self.alternatives))

    def __repr__(self) -> str:
        """String representation for debugging."""
        if len(self.alternatives) > 1:
            alt_strs = ", or ".join(str(alt) for alt in self.alternatives)
            return f"{self.__class__.__name__}({self._raw_value!r} -> {alt_strs!r})"
        else:
            if self._raw_value == self.normalized:
                return f"{self.__class__.__name__}({self.normalized!r})"
        return f"{self.__class__.__name__}({self._raw_value!r} -> {self.normalized!r})"

    def __str__(self) -> str:
        return str(self.normalized)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary with raw and normalized values.

        Returns:
            dict with:
            - type: The class name
            - raw: The original raw value
            - normalized: The normalized value
        """
        return {
            "type": self.__class__.__name__,
            "raw": self._raw_value,
            "normalized": self.normalized,
        }

    def _normalize_string(self, s: str) -> str:
        """
        0. Try to derender URLs (best effort)
        1. Strip non-semantic marks (™, ®, ℠, ©)
        2. NFKC normalization (handles ligatures, full-width, etc.)
        3. Unidecode (ASCII transliteration)
        4. Clean up whitespace
        5. Casefold for comparison
        """
        if not s or is_regexp(s):
            return s

        # Step 0: Try to derender URLs (best effort, no exceptions)
        # Let the derender_url_fct decide whether to process the string
        if self.derender_url_fct is not None and "http" in s:
            with contextlib.suppress(Exception):
                s = self.derender_url_fct(s, strict=False)
                # If derendering fails for any reason, continue with original string

        # Step 1: Remove common non-semantic marks BEFORE NFKC normalization
        # U+2122 ™, U+00AE ®, U+2120 ℠, U+00A9 ©
        # Must happen before NFKC since NFKC converts ™→TM, ℠→SM
        s = s.translate({0x2122: None, 0x00AE: None, 0x2120: None, 0x00A9: None})

        # Step 2: NFKC - handles many edge cases
        # ﬁ → fi, ① → 1, ｆｕｌｌ → full, ² → 2
        s = ud.normalize("NFKC", s)

        # Step 2.5: Normalize hyphen-like characters to spaces BEFORE unidecode
        # (unidecode converts em-dash to '--' which would become double spaces later)
        # Only replace hyphens adjacent to letters to preserve "123-4567" patterns
        s = _HYPHEN_PATTERN.sub(" ", s)

        # Step 3a: Remove control/format chars except basic whitespace
        cleaned = []
        for ch in s:
            cat = ud.category(ch)
            if cat.startswith("C"):  # Control characters
                if ch in ("\t", "\n", "\r"):
                    cleaned.append(" ")  # Convert to space
                # else drop
            else:
                cleaned.append(ch)
        s = "".join(cleaned)

        # Step 3b: Convert to ASCII via transliteration
        s = unidecode(s)
        # Enforce ASCII-only (drops any remaining non-ASCII after transliteration)
        s = s.encode("ascii", "ignore").decode("ascii")

        # Step 4: Normalize whitespace
        s = s.strip()
        s = re.sub(r"\s+", " ", s)

        # Step 5: Casefold for robust case-insensitive comparison
        s = s.casefold()

        return s
