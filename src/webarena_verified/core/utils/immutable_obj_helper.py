"""Utilities for deep serialization and deserialization of immutable objects (MappingProxyType).

This module provides functions to convert between mutable (dict/list) and immutable
(MappingProxyType/tuple) representations, with support for deeply nested structures.
"""

import json
from types import MappingProxyType
from typing import Any

from compact_json import EolStyle, Formatter


def serialize_to_json(obj: Any, indent: int | None = None, lists_to_tuples: bool = True) -> str:
    """Serialize object to JSON string, converting MappingProxyType to dict.

    This function is designed to work with the output of Pydantic's .model_dump(mode="json"),
    ensuring that any remaining MappingProxyType objects are converted to regular dicts
    before JSON serialization. Uses compact_json for consistent formatting.

    Args:
        obj: Object to serialize (typically output from .model_dump(mode="json"))
        indent: Number of spaces for JSON indentation (None for compact output, default: None)
        lists_to_tuples: If True, convert tuples to lists in output (default: True)

    Returns:
        JSON string with all MappingProxyType objects converted to dicts

    Examples:
        >>> from types import MappingProxyType
        >>> # With Pydantic model
        >>> result = some_model.model_dump(mode="json", exclude_none=True)
        >>> json_str = serialize_to_json(result, indent=2)

        >>> # With raw MappingProxyType
        >>> data = MappingProxyType({'a': MappingProxyType({'b': 1})})
        >>> serialize_to_json(data)
        '{"a":{"b":1}}'

        >>> # With indentation
        >>> serialize_to_json(data, indent=2)
        # Returns compact JSON with 2-space indentation
    """
    mutable_obj = serialize_to_mutable(obj, lists_to_tuples)

    if indent is None:
        # Use standard json.dumps for compact output
        return json.dumps(mutable_obj, separators=(",", ":"))

    # Use compact_json for formatted output
    formatter = Formatter()
    formatter.indent_spaces = indent
    formatter.max_inline_complexity = 10
    formatter.json_eol_style = EolStyle.LF
    formatter.omit_trailing_whitespace = True

    return formatter.serialize(mutable_obj)


def serialize_to_mutable(obj: Any, lists_to_tuples: bool = True) -> Any:
    """Recursively convert MappingProxyType (and optionally tuples) to mutable types.

    Converts MappingProxyType → dict for JSON serialization.
    Optionally converts tuples → lists when lists_to_tuples=True.

    Args:
        obj: Any object that may contain MappingProxyType instances
        lists_to_tuples: If True, convert tuples to lists (default: False)

    Returns:
        Object with all immutable types converted to mutable equivalents

    Examples:
        >>> from types import MappingProxyType
        >>> nested = MappingProxyType({'a': MappingProxyType({'b': 1})})
        >>> serialize_to_mutable(nested)
        {'a': {'b': 1}}

        >>> with_list = [MappingProxyType({'x': 1}), MappingProxyType({'y': 2})]
        >>> serialize_to_mutable(with_list)
        [{'x': 1}, {'y': 2}]

        >>> with_tuple = (1, 2, 3)
        >>> serialize_to_mutable(with_tuple, lists_to_tuples=True)
        [1, 2, 3]
    """
    if isinstance(obj, (MappingProxyType, dict)):
        return {k: serialize_to_mutable(v, lists_to_tuples) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        converted = [serialize_to_mutable(item, lists_to_tuples) for item in obj]
        # Convert tuple → list if flag is set, otherwise preserve original type
        if lists_to_tuples and isinstance(obj, tuple):
            return converted
        return type(obj)(converted)
    else:
        return obj


def deserialize_to_immutable(obj: Any, lists_to_tuples: bool = True) -> Any:
    """Recursively convert mutable types to immutable structures.

    Converts dict → MappingProxyType for immutable structures.
    Optionally converts lists → tuples when lists_to_tuples=True.

    Args:
        obj: Any object that may contain dict instances
        lists_to_tuples: If True, convert lists to tuples for full immutability (default: False)

    Returns:
        Object with all mutable types converted to immutable equivalents

    Examples:
        >>> nested = {'a': {'b': 1}}
        >>> result = deserialize_to_immutable(nested)
        >>> isinstance(result, MappingProxyType)
        True
        >>> isinstance(result['a'], MappingProxyType)
        True

        >>> with_list = [{'x': 1}, {'y': 2}]
        >>> result = deserialize_to_immutable(with_list)
        >>> all(isinstance(item, MappingProxyType) for item in result)
        True

        >>> with_list = [1, 2, 3]
        >>> result = deserialize_to_immutable(with_list, lists_to_tuples=True)
        >>> isinstance(result, tuple)
        True
    """
    if isinstance(obj, dict):
        return MappingProxyType({k: deserialize_to_immutable(v, lists_to_tuples) for k, v in obj.items()})
    elif isinstance(obj, (list, tuple)):
        converted = [deserialize_to_immutable(item, lists_to_tuples) for item in obj]
        # Convert list → tuple if flag is set
        if lists_to_tuples and isinstance(obj, list):
            return tuple(converted)
        return type(obj)(converted)
    else:
        return obj


class ImmutableObjJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles MappingProxyType and optionally tuple objects.

    Usage:
        >>> from types import MappingProxyType
        >>> data = MappingProxyType({'a': MappingProxyType({'b': 1})})
        >>> json.dumps(data, cls=ImmutableObjJSONEncoder)
        '{"a": {"b": 1}}'

        >>> encoder = ImmutableObjJSONEncoder(lists_to_tuples=True)
        >>> data = {'items': (1, 2, 3)}
        >>> encoder.encode(data)
        '{"items": [1, 2, 3]}'
    """

    def __init__(self, *args, lists_to_tuples: bool = False, **kwargs):
        """Initialize encoder.

        Args:
            lists_to_tuples: If True, convert tuples to lists during serialization
            *args: Positional arguments passed to json.JSONEncoder
            **kwargs: Keyword arguments passed to json.JSONEncoder
        """
        self.lists_to_tuples = lists_to_tuples
        super().__init__(*args, **kwargs)

    def default(self, obj: Any) -> Any:
        """Override default to handle MappingProxyType."""
        if isinstance(obj, MappingProxyType):
            return serialize_to_mutable(obj, self.lists_to_tuples)
        return super().default(obj)

    def encode(self, obj: Any) -> str:
        """Override encode to recursively handle nested immutable types."""
        return super().encode(serialize_to_mutable(obj, self.lists_to_tuples))


class ImmutableObjJSONDecoder(json.JSONDecoder):
    """Custom JSON decoder that converts dicts to MappingProxyType and optionally lists to tuples.

    Usage:
        >>> data = '{"a": {"b": 1}}'
        >>> result = json.loads(data, cls=ImmutableObjJSONDecoder)
        >>> isinstance(result, MappingProxyType)
        True
        >>> isinstance(result['a'], MappingProxyType)
        True

        >>> decoder = ImmutableObjJSONDecoder(lists_to_tuples=True)
        >>> data = '{"items": [1, 2, 3]}'
        >>> result = decoder.decode(data)
        >>> isinstance(result['items'], tuple)
        True
    """

    def __init__(self, *args, lists_to_tuples: bool = False, **kwargs):
        """Initialize decoder with custom object_hook.

        Args:
            lists_to_tuples: If True, convert lists to tuples for full immutability
            *args: Positional arguments passed to json.JSONDecoder
            **kwargs: Keyword arguments passed to json.JSONDecoder
        """
        self.lists_to_tuples = lists_to_tuples
        kwargs["object_hook"] = self._convert_to_immutable
        super().__init__(*args, **kwargs)

    def _convert_to_immutable(self, obj: dict) -> MappingProxyType:
        """Convert dict to MappingProxyType recursively."""
        return deserialize_to_immutable(obj, self.lists_to_tuples)
