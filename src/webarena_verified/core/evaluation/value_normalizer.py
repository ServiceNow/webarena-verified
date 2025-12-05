"""Value normalization with schema-driven type resolution and alternatives support."""

import json
import logging
from types import MappingProxyType
from typing import Any

from webarena_verified.core.evaluation.data_types import TYPE_REGISTRY, NormalizedString, NormalizedType

logger = logging.getLogger(__name__)


class ValueNormalizer:
    """Normalizes values using TYPE_REGISTRY and NormalizedType classes.

    Responsibilities:
    - Extract type from JSON schema
    - Look up NormalizedType class from TYPE_REGISTRY
    - Create NormalizedType instances (handles normalization internally)
    - Support single values, arrays, and objects
    - Detect and handle alternatives (when value is a list)

    Examples:
        normalizer = ValueNormalizer()

        # Single value with schema
        normalized = normalizer.normalize("success", {"type": "string"}, strict=True)
        # → NormalizedString("success")

        # Single value with alternatives
        normalized = normalizer.normalize(["success", "ok"], {"type": "string"}, strict=True)
        # → NormalizedString(["success", "ok"])

        # Array with element-level alternatives
        normalized = normalizer.normalize([[10, 17], 15], {"type": "array", "items": {"format": "number"}}, strict=True)
        # → [NormalizedNumber([10, 17]), NormalizedNumber(15)]

        # Object with property-level alternatives
        normalized = normalizer.normalize(
            {"status": ["success", "ok"], "code": 200},
            {"type": "object", "properties": {"status": {"type": "string"}, "code": {"format": "number"}}},
            strict=True
        )
        # → {"status": NormalizedString(["success", "ok"]), "code": NormalizedNumber(200)}
    """

    def _get_normalized_type_class(self, item_type: dict | None) -> type[NormalizedType]:
        if item_type is None:
            return NormalizedString  # Default to string type

        if format := item_type.get("format"):
            type_name = format
        else:
            type_name = item_type.get("type", "string")  # Default to string if not specified

        if type_name not in TYPE_REGISTRY:
            raise ValueError(f"Unknown type name: {type_name!r} during normalization")
        return TYPE_REGISTRY[type_name]

    def _normalize_simple_value(
        self, original_value: Any, item_type: dict | None, strict: bool = True, **kwargs
    ) -> NormalizedType | Any:
        type_class = self._get_normalized_type_class(item_type)

        try:
            return type_class(original_value, **kwargs)
        except Exception as e:
            if strict:
                raise ValueError(
                    f"Failed to normalize value {original_value!r} with type {type_class.__name__!r}"
                ) from e
            logger.debug(
                f"Normalization failed for value {original_value!r} with type {type_class.__name__!r}: {e}",
                exc_info=True,
            )
            return original_value

    def normalize_object(
        self, value: Any, schema: dict | MappingProxyType | None, strict: bool = True, **kwargs
    ) -> MappingProxyType | None:
        if schema:
            if not isinstance(schema, (dict, MappingProxyType)):
                raise TypeError(f"Schema must be dict or MappingProxyType, got {type(schema).__name__}")
        else:
            return None

        if not strict and isinstance(value, str):
            # Try json parsing for strings
            try:
                parsed = json.loads(value)
                if (
                    isinstance(parsed, dict)
                    or isinstance(parsed, (list, tuple))
                    and len(parsed) == 1
                    and isinstance(parsed[0], dict)
                ):
                    value = parsed
            except json.JSONDecodeError:
                pass

        if not isinstance(value, (dict, MappingProxyType)):
            if strict:
                raise ValueError(f"Property '{value}' schema expects array but got {type(value).__name__}")
            return None

        properties = schema.get("properties", {})
        normalized = {}
        for field_name, field_schema in properties.items():
            if field_name not in value:
                normalized[field_name] = None
                continue

            field_type = field_schema.get("type")
            if field_type == "array":
                normalized[field_name] = self.normalize_array(value[field_name], field_schema, strict, **kwargs)
            else:
                normalized[field_name] = self._normalize_simple_value(value[field_name], field_schema, strict, **kwargs)

        return MappingProxyType(normalized)

    def normalize_array(
        self, value: Any, schema: dict | MappingProxyType | None, strict: bool = True, **kwargs
    ) -> tuple | None:
        if schema and not isinstance(schema, (dict, MappingProxyType)):
            raise TypeError(f"Schema must be dict or MappingProxyType, got {type(schema).__name__}")

        if not strict:
            if isinstance(value, str):
                # Try json parsing for strings
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, (list, tuple)):
                        value = parsed
                except json.JSONDecodeError:
                    pass

            if not isinstance(value, (list, tuple)):
                value = (value,)

        if not isinstance(value, (list, tuple)):
            if strict:
                raise ValueError(f"Property '{value}' schema expects array but got {type(value).__name__}")
            return None

        # Handle schema=None by defaulting to string type for array elements
        if schema is None:
            items_schema = None  # Will default to NormalizedString in _normalize_simple_value
            items_type = "string"
        else:
            schema_type = schema.get("type", "array")
            if schema_type != "array":
                raise ValueError(f"Schema type must be 'array', got: {schema_type!r}")

            items_schema = schema.get("items", {})
            items_type = items_schema.get("type", "string")  # Default to string if not specified

        if items_type == "object":
            # Handle list of objects
            # Note: items_schema cannot be None here because items_type is only "object" when schema is provided
            if items_schema is None:
                raise ValueError("items_schema must be provided when items_type is 'object'")
            normalized_array = tuple(
                [self._normalize_object_or_array(item, items_schema, strict, **kwargs) for item in value]
            )
        else:
            # Handle list of simple types
            normalized_array = tuple(
                [self._normalize_simple_value(item, items_schema, strict, **kwargs) for item in value]
            )

        return tuple(normalized_array)

    def normalize(
        self, value: Any, schema: dict | MappingProxyType, strict: bool = True, **kwargs
    ) -> NormalizedType | tuple[NormalizedType, ...] | tuple[dict, ...] | dict | MappingProxyType | None:
        """Main entry point for normalization.

        Args:
            value: Raw value to normalize (single, array, or object)
            schema: JSON schema defining the type
            strict: If True, raise on normalization errors (for expected)
                   If False, return raw value on error (for actual)

        Returns:
            Normalized value (NormalizedType instances, tuple, or dict)
            Returns None for None/empty values
            Arrays are returned as tuple for immutability

        Examples:
            # With schema
            normalize("yes", {"type": "boolean"}, strict=True)
            # → Boolean(True)

            # Array with schema
            normalize([10, 15], {"type": "array", "items": {"format": "number"}}, strict=True)
            # → (NormalizedNumber(10), NormalizedNumber(15))
        """
        # Handle None/empty values
        if not value:
            return None

        if not schema:
            if isinstance(value, (dict, MappingProxyType)):
                schema = {"type": "object"}
            elif isinstance(value, (list, tuple)):
                schema = {"type": "array"}

        type_name_or_schema, is_array = self._extract_type_from_schema(schema)

        # Check if we got an object schema instead of a type name
        if isinstance(type_name_or_schema, (dict, MappingProxyType)):
            # Handle object schema with property-by-property normalization
            return self._normalize_object_or_array(value, type_name_or_schema, strict, **kwargs)

        # Handle array vs single value based on schema
        if is_array:
            # Schema indicates array - normalize as array
            if not isinstance(value, (list, tuple)):
                # Value should be an array but isn't - error or coerce?
                if strict:
                    raise ValueError(f"Schema expects array but got {type(value).__name__}: {value!r}")
                return value  # Return raw value in non-strict mode
            return self._normalize_array(value, type_name_or_schema, strict, **kwargs)
        else:
            # Schema indicates single value
            # If value is list at root level, treat as alternatives
            return self.normalize_single(value, type_name_or_schema, strict, **kwargs)

    def normalize_single(self, value: Any, type_name: str, strict: bool, **kwargs) -> NormalizedType:
        """Normalize single value with alternative detection.

        Args:
            value: Raw value (single value or list of alternatives)
            type_name: Type name from TYPE_REGISTRY
            strict: If True, raise on normalization errors

        Returns:
            NormalizedType instance (may contain alternatives internally)

        Examples:
            # Single value
            _normalize_single("success", "string", strict=True)
            # → NormalizedString("success")

            # Multiple alternatives
            _normalize_single(["success", "ok"], "string", strict=True)
            # → NormalizedString(["success", "ok"])
        """
        if type_name not in TYPE_REGISTRY:
            raise ValueError(f"Unknown type name: {type_name!r}")

        type_class = TYPE_REGISTRY[type_name]

        try:
            # NormalizedType handles both single values and lists (alternatives)
            return type_class(value, **kwargs)
        except Exception as e:
            logger.debug(f"Normalization failed for value {value!r} with type {type_name!r}: {e}", exc_info=True)
            if strict:
                raise
            # In non-strict mode, return raw value on normalization failure
            return value

    def _normalize_array(
        self,
        value: list | tuple | str,
        type_name: str | dict | MappingProxyType,
        strict: bool,
        **kwargs,
    ) -> tuple[NormalizedType, ...] | Any:
        """Normalize array, detecting element-level alternatives.

        Args:
            value: List or tuple of values (each can be single or list of alternatives)
            type_name: Type name from TYPE_REGISTRY for array elements
            strict: If True, raise on normalization errors

        Returns:
            Tuple of NormalizedType instances

        Examples:
            # Array without alternatives
            _normalize_array(("apple", "banana"), "string", strict=True)
            # → (NormalizedString("apple"), NormalizedString("banana"))

            # Array with element-level alternatives
            _normalize_array(([10, 17], 15), "number", strict=True)
            # → (NormalizedNumber([10, 17]), NormalizedNumber(15))
        """
        if isinstance(value, str):
            # Try json parsing for strings
            try:
                parsed = json.loads(value)
                if isinstance(parsed, (list, tuple)):
                    value = parsed
            except json.JSONDecodeError:
                pass
        elif not isinstance(value, (list, tuple)):
            if strict:
                raise ValueError(f"Property '{value}' schema expects array but got {type(value).__name__}")
            return value  # Return raw value in non-strict mode
        if isinstance(type_name, (dict, MappingProxyType)):
            return self._normalize_object_or_array(value, type_name, strict, **kwargs)
        elif type_name not in TYPE_REGISTRY:
            raise ValueError(f"Unknown type name: {type_name!r}")

        type_class = TYPE_REGISTRY[type_name]
        result = []

        for i, item in enumerate(value):
            try:
                # Each item can be:
                # 1. A single value → NormalizedType(item)
                # 2. A list of alternatives → NormalizedType([alt1, alt2, ...])
                # The NormalizedType constructor handles both cases
                result.append(type_class(item, **kwargs))
            except Exception as e:
                if strict:
                    raise ValueError(f"Failed to normalize array element at index {i}: {item!r}") from e
                # In non-strict mode, keep raw value
                result.append(item)

        return tuple(result)

    def _normalize_object_or_array(
        self,
        value: dict | MappingProxyType | list[dict] | tuple[dict, ...],
        object_schema: dict | MappingProxyType,
        strict: bool,
        **kwargs,
    ) -> dict | tuple[dict, ...]:
        """Normalize object or array of objects.

        Args:
            value: Object or array of objects
            object_schema: Object schema with properties
            strict: If True, raise on normalization errors

        Returns:
            Normalized object or tuple of objects
        """
        if isinstance(value, (list, tuple)):
            # Array of objects
            return tuple(self._normalize_object(obj, object_schema, strict, **kwargs) for obj in value)
        else:
            # Single object
            return self._normalize_object(value, object_schema, strict, **kwargs)

    def _normalize_object(
        self,
        obj: dict | MappingProxyType,
        object_schema: dict | MappingProxyType,
        strict: bool,
        **kwargs,
    ) -> dict:
        """Normalize object with property-level alternatives.

        Args:
            obj: Dictionary with properties
            object_schema: Object schema with property definitions
            strict: If True, raise on normalization errors

        Returns:
            Dictionary with normalized property values

        Examples:
            # Object without alternatives
            _normalize_object(
                {"status": "success", "code": 200},
                {"properties": {"status": {"type": "string"}, "code": {"format": "number"}}},
                strict=True
            )
            # → {"status": NormalizedString("success"), "code": NormalizedNumber(200)}

            # Object with property-level alternatives
            _normalize_object(
                {"status": ["success", "ok"], "code": 200},
                {"properties": {"status": {"type": "string"}, "code": {"format": "number"}}},
                strict=True
            )
            # → {"status": NormalizedString(["success", "ok"]), "code": NormalizedNumber(200)}
        """
        if isinstance(obj, MappingProxyType):
            obj = dict(obj)
        elif isinstance(obj, str):
            # Try json parsing for strings
            try:
                parsed = json.loads(obj)
                if isinstance(parsed, dict):
                    obj = parsed
            except json.JSONDecodeError:
                pass

        if not isinstance(obj, dict):
            if strict:
                raise ValueError(f"Expected dict for object normalization, got {type(obj).__name__}: {obj!r}")
            return obj

        # Get property schemas
        properties = object_schema.get("properties", {})
        normalized = {}

        for prop_name, prop_value in obj.items():
            # Handle None values - don't attempt normalization
            if prop_value is None:
                normalized[prop_name] = None
                continue

            # Get property schema
            prop_schema = properties.get(prop_name)

            if prop_schema is None:
                # No schema for this property - fall back to NormalizedString
                try:
                    normalized[prop_name] = NormalizedString(prop_value, **kwargs)
                except Exception:
                    if strict:
                        raise
                    normalized[prop_name] = prop_value
                continue

            # Extract type from property schema
            prop_type_name, is_array = self._extract_type_from_schema(prop_schema)

            # Normalize property value (handles alternatives automatically)
            try:
                if is_array:
                    normalized[prop_name] = self._normalize_array(prop_value, prop_type_name, strict, **kwargs)
                elif isinstance(prop_type_name, str) and prop_type_name in TYPE_REGISTRY:
                    type_class = TYPE_REGISTRY[prop_type_name]
                    normalized[prop_name] = type_class(prop_value, **kwargs)
                elif isinstance(prop_type_name, (dict, MappingProxyType)):
                    # Recursively normalize nested object
                    normalized[prop_name] = self._normalize_object(prop_value, prop_type_name, strict, **kwargs)
                else:
                    # Unknown type, fall back to NormalizedString or keep raw
                    normalized[prop_name] = NormalizedString(prop_value, **kwargs)
            except Exception as e:
                if strict:
                    raise ValueError(f"Failed to normalize property '{prop_name}': {prop_value!r}") from e
                # In non-strict mode, keep raw value
                normalized[prop_name] = prop_value

        return normalized

    def _extract_type_from_schema(
        self, schema: dict | MappingProxyType
    ) -> tuple[str | dict[str, Any] | MappingProxyType[str, Any], bool]:
        """Extract type information from JSON schema.

        Args:
            schema: JSON schema

        Returns:
            Tuple of (type_name_or_schema, is_array)
            - type_name_or_schema: Either a string (type name) or dict (object schema)
            - is_array: True if schema indicates an array

        Examples:
            # Simple type
            _extract_type_from_schema({"type": "string"})
            # → ("string", False)

            # Format-based type
            _extract_type_from_schema({"type": "string", "format": "currency"})
            # → ("currency", False)

            # Array type
            _extract_type_from_schema({"type": "array", "items": {"format": "number"}})
            # → ("number", True)

            # Object type
            _extract_type_from_schema({"type": "object", "properties": {...}})
            # → ({properties...}, False)
        """
        if not isinstance(schema, (dict, MappingProxyType)):
            raise ValueError(f"Schema must be dict or MappingProxyType, got {type(schema).__name__}")

        schema_type = schema.get("type")

        # Handle array type
        if schema_type == "array":
            items_schema = schema.get("items", {})
            # Extract type from items schema
            item_type, _ = self._extract_type_from_schema(items_schema)
            return (item_type, True)  # is_array=True

        # Handle object type
        if schema_type == "object":
            # Return the entire schema for object handling
            return (schema, False)  # is_array=False

        # Handle simple types with optional format
        # Format takes precedence (e.g., "format": "currency" overrides "type": "string")
        format_type = schema.get("format")
        if format_type:
            return (format_type, False)

        # Fall back to base type
        if schema_type:
            return (schema_type, False)

        # No type information - default to string
        return ("string", False)
