"""Base64 string data type for normalized comparison."""

import base64
import re
from typing import Any

from webarena_verified.core.utils import is_regexp

from .base import NormalizedType


class Base64String(NormalizedType[str]):
    """Base64-encoded string normalization for comparison.

    This type handles base64-encoded content by:
    - Decoding base64 before comparison
    - Preserving exact content (no Unicode normalization, no lowercasing)
    - Supporting regex patterns on decoded content (not on base64 string)
    - Minimal normalization: only line ending normalization

    Use case: GitLab POST requests send file content as base64-encoded strings.
    When validating with regex patterns, the pattern should match the decoded
    content, not the base64 string itself.

    Input must be a string containing valid base64. Non-string inputs will raise ValueError.

    Alternatives: To specify alternative valid values, pass a list of 2+ base64 strings:
        Base64String(['dGVzdDE=', 'dGVzdDI='])  # Two alternative base64 values

    Examples:
        >>> Base64String('SGVsbG8gV29ybGQ=')  # "Hello World"
        Base64String('Hello World')

        >>> Base64String('^.*MIT License.*$')  # Regex pattern on decoded content
        Base64String('^.*MIT License.*$')

        >>> Base64String('TUlUIExpY2Vuc2U=')  # "MIT License" in base64
        Base64String('MIT License')
    """

    # Explicitly use parent's __hash__ since we override __eq__
    __hash__ = NormalizedType.__hash__  # type: ignore[assignment]

    def _normalize_string(self, s: str) -> str:
        """Override to skip Unicode/lowercase normalization for base64 content.

        Base64 strings are case-sensitive and contain only ASCII characters,
        so we:
        - Skip Unicode normalization (NFKC, unidecode)
        - Skip lowercasing
        - Skip aggressive whitespace normalization
        - Only strip leading/trailing whitespace

        Regex patterns (^...$) are preserved as-is.
        """
        return s.strip()

    def _type_normalize(self, value: Any) -> str:
        """Normalize base64 string for comparison.

        Steps:
        1. Validate input is a string
        2. Detect regex patterns (^...$) and preserve them as-is
        3. Decode base64 content
        4. Normalize line endings only (preserve exact content otherwise)

        Args:
            value: Must be a string containing base64 or regex pattern

        Returns:
            Decoded content (with normalized line endings) or regex pattern as-is

        Raises:
            ValueError: If value is not a string, is empty, or is invalid base64
        """
        # Only accept strings
        if not isinstance(value, str):
            raise ValueError(f"Base64String only accepts string input. Got {type(value).__name__}: {value!r}")

        # Handle empty strings
        if not value:
            raise ValueError("Base64 string is empty")

        # Regex patterns are preserved as-is (for matching decoded content later)
        if is_regexp(value):
            return value.strip()

        # Decode base64 content
        try:
            decoded_bytes = base64.b64decode(value, validate=True)
            decoded_str = decoded_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Invalid base64 string: {value!r}") from e

        # Normalize line endings to \n (Windows/Mac/Linux compatibility)
        content = decoded_str.replace("\r\n", "\n").replace("\r", "\n")

        # Strip leading/trailing whitespace from entire content
        content = content.strip()

        return content

    def __eq__(self, other: Any) -> bool:
        """Equality comparison with regex pattern matching on decoded content.

        Comparison order:
        1. Check for regex patterns (strings starting with ^ and ending with $)
        2. Try standard comparison via parent class __eq__()

        Regex patterns are matched against the decoded content, not the base64 string.

        Args:
            other: The value to compare with (must be a valid Base64String)

        Returns:
            True if values match (with or without regex), False otherwise
        """
        # Type check (same as base class)
        if not isinstance(other, self.__class__):
            return False

        # Check for regex pattern matching
        # If any alternative on either side is a pattern, try regex matching
        for self_alt in self.alternatives:
            if is_regexp(self_alt):
                # self has pattern - match against other's alternatives (decoded content)
                try:
                    pattern = re.compile(self_alt, re.DOTALL)  # re.DOTALL for multiline content
                    if any(pattern.fullmatch(other_alt) for other_alt in other.alternatives):
                        return True
                except re.error:
                    # Invalid regex - fall through to standard comparison
                    pass

        for other_alt in other.alternatives:
            if is_regexp(other_alt):
                # other has pattern - match against self's alternatives (decoded content)
                try:
                    pattern = re.compile(other_alt, re.DOTALL)  # re.DOTALL for multiline content
                    if any(pattern.fullmatch(self_alt) for self_alt in self.alternatives):
                        return True
                except re.error:
                    # Invalid regex - fall through to standard comparison
                    pass

        # Try standard set-based comparison (check for overlap in alternatives)
        # This is the base class logic: bool(set(self.alternatives) & set(other.alternatives))
        return bool(set(self.alternatives) & set(other.alternatives))
