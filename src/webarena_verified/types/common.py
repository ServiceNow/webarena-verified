"""Common type aliases for WebArena Verified."""

from types import MappingProxyType
from typing import Annotated, Any

from pydantic import Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from webarena_verified.core.utils.immutable_obj_helper import deserialize_to_immutable, serialize_to_mutable


# ============================================================================
# Immutable Type Handling (MappingProxyType with deep nesting support)
# ============================================================================
def validate_mapping_proxy(v: Any) -> MappingProxyType:
    """Validate and convert to MappingProxyType with lists→tuples (handles deep nesting).

    Args:
        v: Value to validate (dict or MappingProxyType)

    Returns:
        MappingProxyType with all nested lists converted to tuples

    Raises:
        ValueError: If value is not dict or MappingProxyType
    """
    if isinstance(v, MappingProxyType):
        return v
    if isinstance(v, dict):
        return deserialize_to_immutable(v, lists_to_tuples=True)
    raise ValueError(f"Expected dict or MappingProxyType, got {type(v)}")


def serialize_mapping_proxy(v: MappingProxyType) -> dict:
    """Serialize MappingProxyType to dict with tuples→lists (handles deep nesting).

    Args:
        v: MappingProxyType to serialize

    Returns:
        dict with all nested tuples converted to lists for JSON compatibility
    """
    return serialize_to_mutable(v, lists_to_tuples=True)


class _MappingProxyTypeAnnotation:
    """Pydantic annotation for MappingProxyType with deep nesting support."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: GetCoreSchemaHandler) -> CoreSchema:
        """Define Pydantic core schema for MappingProxyType."""
        return core_schema.json_or_python_schema(
            json_schema=core_schema.dict_schema(),
            python_schema=core_schema.no_info_plain_validator_function(validate_mapping_proxy),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_mapping_proxy, return_schema=core_schema.dict_schema()
            ),
        )


# Reusable annotation for MappingProxyType fields in Pydantic models
SerializableMappingProxyType = Annotated[MappingProxyType, _MappingProxyTypeAnnotation]

# Query parameters with immutable tuple values
# - Keys are query parameter names (strings)
# - Values are tuples of strings (even for single values)
# - MappingProxyType ensures immutability of the entire dict
# - Tuples ensure immutability and hashability of values
# - Empty tuple represents a parameter with no value
# - Pydantic-compatible: works in both model fields and function signatures
QueryParams = Annotated[MappingProxyType[str, tuple[str, ...]], _MappingProxyTypeAnnotation]

# Non-empty string type for required string fields
NonEmptyStr = Annotated[str, Field(min_length=1)]
