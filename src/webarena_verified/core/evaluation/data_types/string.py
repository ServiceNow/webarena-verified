# Requires: pip install unidecode
"""Basic normalized string (lowercase, stripped)."""

import re
from typing import Any

from webarena_verified.core.utils import is_regexp

from .base import NormalizedType


class NormalizedString(NormalizedType[str]):
    """Basic normalized string.

    Future normalization will:
    - Convert unicode to ASCII using unidecode
    - Convert to lowercase
    - Strip whitespace
    """

    # Explicitly use parent's __hash__ since we override __eq__
    __hash__ = NormalizedType.__hash__  # type: ignore[assignment]

    def _type_normalize(self, value: Any) -> str:
        """Basic string normalization.

        Currently: simple string conversion with lowercase and strip
        Future: will apply unicode -> ASCII as well
        """
        # Handle empty values
        if not value:
            return ""

        if is_regexp(value):
            # For regex patterns, return as-is (after basic str conversion)
            return str(value).strip()

        # Hyphen normalization is handled in base class's _normalize_string
        return str(value).lower().strip()

    def __eq__(self, other: Any) -> bool:
        """Equality comparison with prefix/suffix tolerance and regex pattern matching.

        Comparison order:
        1. Check for regex patterns (strings starting with ^ and ending with $)
        2. Try standard comparison via super().__eq__()
        3. Retry after stripping common quote/punctuation prefixes and suffixes

        Args:
            other: The value to compare with (must be a valid NormalizedString)

        Returns:
            True if values match (with or without prefixes/suffixes or via regex), False otherwise
        """
        # Type check (same as base class)
        if not isinstance(other, self.__class__):
            # Allow comparison with raw strings to handle DeepDiff's hashing mechanism.
            # DeepDiff may pass raw strings when comparing nested structures with custom operators,
            # so we need to normalize them on-the-fly for accurate comparison.
            if isinstance(other, str):
                _other = NormalizedString(other)
            else:
                return False
        else:
            _other = other

        # Check for regex pattern matching
        # If any alternative on either side is a pattern, try regex matching
        for self_alt in self.alternatives:
            if is_regexp(self_alt):
                # self has pattern - match against other's alternatives
                try:
                    pattern = re.compile(self_alt, re.IGNORECASE)
                    if any(pattern.fullmatch(other_alt) for other_alt in _other.alternatives):
                        return True
                except re.error:
                    # Invalid regex - fall through to standard comparison
                    pass

        for other_alt in _other.alternatives:
            if is_regexp(other_alt):
                # other has pattern - match against self's alternatives
                try:
                    pattern = re.compile(other_alt, re.IGNORECASE)
                    if any(pattern.fullmatch(self_alt) for self_alt in self.alternatives):
                        return True
                except re.error:
                    # Invalid regex - fall through to standard comparison
                    pass

        # Try standard set-based comparison (check for overlap in alternatives)
        # This is the base class logic: bool(set(self.alternatives) & set(other.alternatives))
        if bool(set(self.alternatives) & set(_other.alternatives)):
            return True

        # If standard comparison failed, retry with prefix/suffix stripping
        # Strip prefixes and suffixes from both sets of alternatives
        self_stripped = {self._strip_prefix_suffix(alt) for alt in self.alternatives}
        other_stripped = {self._strip_prefix_suffix(alt) for alt in _other.alternatives}

        # Check for intersection
        return bool(self_stripped & other_stripped)

    @staticmethod
    def _strip_prefix_suffix(s: str) -> str:
        """Remove common leading and trailing quote/punctuation characters.

        Handles: ' " ` . , ; : ! ?

        Args:
            s: String to strip

        Returns:
            String with leading/trailing quote/punctuation removed
        """
        if not s:
            return s

        # Common quote and punctuation characters
        chars = ("'", '"', "`", ".", ",", ";", ":", "!", "?")

        # Strip all leading prefix characters
        while s and s[0] in chars:
            s = s[1:]

        # Strip all trailing suffix characters
        while s and s[-1] in chars:
            s = s[:-1]

        return s
