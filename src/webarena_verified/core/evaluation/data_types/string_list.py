"""String list data type for comma-separated values with order-independent comparison."""

from typing import Any

from .base import NormalizedType


class StringList(NormalizedType[tuple[str, ...]]):
    """Comma-separated string list normalized to a sorted tuple.

    Takes input like "632,64,86,96,340" and converts to sorted tuple
    for order-independent comparison. This is useful when comparing
    lists where the order of elements doesn't matter.

    The normalization process:
    1. Converts input to string
    2. Splits by comma
    3. Strips whitespace from each item
    4. Removes empty items
    5. Sorts items alphabetically
    6. Returns as immutable tuple

    Examples:
        >>> sl1 = StringList("632,64,86,96,340")
        >>> sl2 = StringList("632,64,86,340,96")
        >>> sl1 == sl2  # True (order doesn't matter)
        True

        >>> sl3 = StringList("apple, banana, cherry")
        >>> sl4 = StringList("cherry,banana,apple")
        >>> sl3 == sl4
        True

        >>> # Supports alternatives
        >>> sl5 = StringList(["1,2,3", "3,2,1"])  # Both are valid
        >>> sl5 == StringList("2,1,3")
        True

    Attributes:
        normalized: The first normalized value (sorted tuple)
        alternatives: Tuple of all alternative normalized values

    Raises:
        ValueError: If the input is empty or contains no valid items after parsing
    """

    def _type_normalize(self, value: Any) -> tuple[str, ...]:
        """Parse comma-separated string and return sorted tuple.

        Args:
            value: The value to normalize. Can be a string with comma-separated
                   items, or any value that can be converted to string.

        Returns:
            A sorted tuple of string items with whitespace stripped.

        Raises:
            ValueError: If value is empty/None or contains no valid items.
        """
        if not value:
            raise ValueError("StringList value is empty or None")

        # Convert to string and split by comma
        value_str = str(value)
        items = [item.strip() for item in value_str.split(",")]

        # Remove empty items (items that are only whitespace)
        items = [item for item in items if item]

        if not items:
            raise ValueError(f"No valid items in StringList: {value!r}")

        # Return sorted tuple for order-independent comparison
        return tuple(sorted(items))
