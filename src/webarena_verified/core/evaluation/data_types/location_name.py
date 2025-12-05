"""Location name matching with fuzzy string comparison using thefuzz library."""

from typing import Any

from thefuzz import fuzz

from .base import NormalizedType


class LocationName(NormalizedType[str]):
    """Fuzzy string matching with 80% similarity threshold for location names.

    Uses thefuzz library's token_sort_ratio function for comparison.
    Token sort ratio handles word order variations better than simple ratio,
    making it ideal for place names where order may vary.

    Normalization applies standard string normalization (lowercase,
    whitespace, unicode) before fuzzy comparison.

    Examples:
        >>> ln1 = LocationName("Carnegie Mellon University")
        >>> ln2 = LocationName("Carnegie Mellon Univ")
        >>> ln1 == ln2  # True if similarity >= 80%
        True

        >>> ln1 = LocationName("Starbucks on Craig Street")
        >>> ln2 = LocationName("Starbucks Craig St")
        >>> ln1 == ln2
        True

        >>> ln1 = LocationName("Apple Store Shadyside")
        >>> ln2 = LocationName("Shadyside Apple Store")
        >>> ln1 == ln2  # Token sort handles word order
        True
    """

    # Minimum similarity score (0-100) for fuzzy string matching.
    # 80 was chosen as a balance between tolerance for minor typos/variations
    # (such as abbreviations or word order changes) and avoiding false positives.
    # Lowering this threshold increases the chance of matching dissimilar strings,
    # while raising it makes matching stricter and may miss legitimate variations.
    fuzzy_threshold: int = 80

    # Explicitly use parent's __hash__ since we override __eq__
    __hash__ = NormalizedType.__hash__  # type: ignore[assignment]

    def _type_normalize(self, value: Any) -> str:
        """Normalize string using standard string normalization.

        Args:
            value: The value to normalize

        Returns:
            Normalized string value

        Raises:
            ValueError: If value is None
        """
        if value is None:
            raise ValueError("Value cannot be None")

        if not value:
            return ""

        return str(value).lower().strip()

    def __eq__(self, other: Any) -> bool:
        """Compare using fuzzy matching with threshold.

        Uses token_sort_ratio which:
        - Tokenizes both strings
        - Sorts tokens alphabetically
        - Compares the sorted strings
        This handles word order variations like "Apple Store Shadyside"
        vs "Shadyside Apple Store".

        Args:
            other: The value to compare with

        Returns:
            True if fuzzy similarity >= fuzzy_threshold, False otherwise
        """
        if not isinstance(other, self.__class__):
            return False

        # Check all combinations of alternatives for any match
        for self_alt in self.alternatives:
            for other_alt in other.alternatives:
                # Skip empty comparisons
                if not self_alt or not other_alt:
                    if self_alt == other_alt:
                        return True
                    continue

                # Use token_sort_ratio for better word order handling
                similarity = fuzz.token_sort_ratio(self_alt, other_alt)
                if similarity >= self.fuzzy_threshold:
                    return True

        return False
