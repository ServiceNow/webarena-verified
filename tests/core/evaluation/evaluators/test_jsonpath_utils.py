"""Unit tests for JSONPath utility functions."""

import pytest

from webarena_verified.core.utils.jsonpath_utils import (
    deserialize_nested_json,
    extract_jsonpath_value,
    is_jsonpath_key,
)

# ============================================================================
# is_jsonpath_key tests
# ============================================================================


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("$.note.note", True),
        ("$.items[0].price", True),
        ("$", True),
        ("$.root", True),
        ("$not_at_start", True),  # Still a JSONPath key (starts with $)
        ("^reply_to_submission_\\d+\\[comment\\]$", True),  # Regex pattern
        ("^.*$", True),  # Regex pattern
        ("user_id", False),
        ("note", False),
        ("", False),
        ("regular_key", False),
        ("field$with$dollars", False),  # $ not at start
        ("^incomplete", False),  # Starts with ^ but doesn't end with $
        ("incomplete$", False),  # Ends with $ but doesn't start with ^
    ],
)
def test_is_jsonpath_key(key, expected):
    """Test detection of JSONPath keys and regex patterns."""
    assert is_jsonpath_key(key) == expected


def test_is_jsonpath_key_non_string():
    """Test that non-string keys return False."""
    assert is_jsonpath_key(123) is False  # type: ignore
    assert is_jsonpath_key(None) is False  # type: ignore


# ============================================================================
# extract_jsonpath_value tests - Single match (success cases)
# ============================================================================


def test_extract_simple_nested_field():
    """Test extracting a simple nested field."""
    data = {"note": {"noteable_type": "MergeRequest", "note": "lgtm"}}
    result = extract_jsonpath_value(data, "$.note.note", strict=True)
    assert result == "lgtm"


def test_extract_top_level_field():
    """Test extracting a top-level field."""
    data = {"user_id": "123", "status": "active"}
    result = extract_jsonpath_value(data, "$.user_id", strict=True)
    assert result == "123"


def test_extract_deeply_nested_field():
    """Test extracting a deeply nested field."""
    data = {"metadata": {"user": {"profile": {"name": "John"}}}}
    result = extract_jsonpath_value(data, "$.metadata.user.profile.name", strict=True)
    assert result == "John"


def test_extract_array_element():
    """Test extracting a specific array element."""
    data = {"items": [{"id": 1, "price": "10.00"}, {"id": 2, "price": "20.00"}]}
    result = extract_jsonpath_value(data, "$.items[0].price", strict=True)
    assert result == "10.00"


def test_extract_from_list_root():
    """Test extracting from data that's a list at root."""
    data = [{"name": "Alice"}, {"name": "Bob"}]
    result = extract_jsonpath_value(data, "$[0].name", strict=True)
    assert result == "Alice"


# ============================================================================
# extract_jsonpath_value tests - No match (strict vs non-strict)
# ============================================================================


def test_extract_missing_field_strict():
    """Test that missing field raises error in strict mode."""
    data = {"user_id": "123"}
    with pytest.raises(ValueError, match="matched 0 values"):
        extract_jsonpath_value(data, "$.note.note", strict=True)


def test_extract_missing_field_non_strict():
    """Test that missing field returns None in non-strict mode."""
    data = {"user_id": "123"}
    result = extract_jsonpath_value(data, "$.note.note", strict=False)
    assert result is None


def test_extract_missing_nested_path_non_strict():
    """Test that missing nested path returns None in non-strict mode."""
    data = {"note": {"noteable_type": "MergeRequest"}}
    result = extract_jsonpath_value(data, "$.note.comment.text", strict=False)
    assert result is None


# ============================================================================
# extract_jsonpath_value tests - Multiple matches (strict vs non-strict)
# ============================================================================


def test_extract_multiple_matches_strict():
    """Test that multiple matches return tuple even in strict mode."""
    data = {"items": [{"price": "10.00"}, {"price": "20.00"}]}
    result = extract_jsonpath_value(data, "$.items[*].price", strict=True)
    assert result == ("10.00", "20.00")


def test_extract_multiple_matches_non_strict():
    """Test that multiple matches return tuple in non-strict mode."""
    data = {"items": [{"price": "10.00"}, {"price": "20.00"}]}
    result = extract_jsonpath_value(data, "$.items[*].price", strict=False)
    assert result == ("10.00", "20.00")


# ============================================================================
# extract_jsonpath_value tests - Invalid JSONPath expressions
# ============================================================================


def test_extract_invalid_jsonpath_strict():
    """Test that invalid JSONPath raises error in strict mode."""
    data = {"user_id": "123"}
    with pytest.raises(ValueError, match="Invalid JSONPath expression"):
        extract_jsonpath_value(data, "$...[invalid", strict=True)


def test_extract_invalid_jsonpath_non_strict():
    """Test that invalid JSONPath returns None in non-strict mode."""
    data = {"user_id": "123"}
    result = extract_jsonpath_value(data, "$...[invalid", strict=False)
    assert result is None


# ============================================================================
# extract_jsonpath_value tests - Complex data types
# ============================================================================


def test_extract_dict_value():
    """Test extracting a dict value."""
    data = {"note": {"metadata": {"author": "John", "timestamp": "2024-01-01"}}}
    result = extract_jsonpath_value(data, "$.note.metadata", strict=True)
    assert result == {"author": "John", "timestamp": "2024-01-01"}


def test_extract_list_value():
    """Test extracting a list value."""
    data = {"tags": ["python", "testing", "jsonpath"]}
    result = extract_jsonpath_value(data, "$.tags", strict=True)
    assert result == ["python", "testing", "jsonpath"]


def test_extract_number_value():
    """Test extracting a numeric value."""
    data = {"price": 29.99, "quantity": 5}
    result = extract_jsonpath_value(data, "$.price", strict=True)
    assert result == 29.99


def test_extract_boolean_value():
    """Test extracting a boolean value."""
    data = {"is_active": True, "is_verified": False}
    result = extract_jsonpath_value(data, "$.is_active", strict=True)
    assert result is True


def test_extract_null_value():
    """Test extracting a null value."""
    data = {"optional_field": None}
    result = extract_jsonpath_value(data, "$.optional_field", strict=True)
    assert result is None


# ============================================================================
# extract_jsonpath_value tests - Edge cases
# ============================================================================


def test_extract_empty_dict():
    """Test extracting from empty dict."""
    data = {}
    result = extract_jsonpath_value(data, "$.any_field", strict=False)
    assert result is None


def test_extract_empty_list():
    """Test extracting from empty list."""
    data = []
    result = extract_jsonpath_value(data, "$[0]", strict=False)
    assert result is None


def test_extract_with_special_characters_in_key():
    """Test extracting field with special characters."""
    data = {"user[website_url]": "https://example.com"}
    result = extract_jsonpath_value(data, "$['user[website_url]']", strict=True)
    assert result == "https://example.com"


def test_extract_with_spaces_in_key():
    """Test extracting field with spaces in key name."""
    data = {"user profile": {"name": "Alice"}}
    result = extract_jsonpath_value(data, "$['user profile'].name", strict=True)
    assert result == "Alice"


# ============================================================================
# deserialize_nested_json tests
# ============================================================================


def test_deserialize_nested_dict():
    """Test deserializing nested dict with JSON string value."""
    data = {"outer": '{"inner": "value"}'}
    result = deserialize_nested_json(data)
    assert result == {"outer": {"inner": "value"}}


def test_deserialize_deeply_nested_dict():
    """Test deserializing deeply nested dict with multiple JSON string layers."""
    data = {"level1": '{"level2": "{\\"level3\\": \\"deep_value\\"}"}'}
    result = deserialize_nested_json(data)
    # First pass deserializes level1
    assert result == {"level1": {"level2": '{"level3": "deep_value"}'}}


def test_deserialize_nested_list():
    """Test deserializing list containing JSON strings (strings in lists are NOT deserialized)."""
    # Note: The function only deserializes strings that are dict values, not list items
    data = {"items": ['{"name": "item1"}', '{"name": "item2"}']}
    result = deserialize_nested_json(data)
    assert result == {"items": ['{"name": "item1"}', '{"name": "item2"}']}


def test_deserialize_list_at_root():
    """Test that list at root level is processed but string items are unchanged."""
    # Note: The function only deserializes strings that are dict values, not list items
    data = ['{"key": "value1"}', '{"key": "value2"}']
    result = deserialize_nested_json(data)
    assert result == ['{"key": "value1"}', '{"key": "value2"}']


def test_deserialize_mixed_nesting():
    """Test deserializing mixed nesting (dict containing lists and JSON strings)."""
    data = {
        "users": [{"id": 1, "data": '{"name": "Alice"}'}, {"id": 2, "data": '{"name": "Bob"}'}],
        "metadata": '{"count": 2, "items": ["user1", "user2"]}',
    }
    result = deserialize_nested_json(data)
    assert result == {
        "users": [{"id": 1, "data": {"name": "Alice"}}, {"id": 2, "data": {"name": "Bob"}}],
        "metadata": {"count": 2, "items": ["user1", "user2"]},
    }


def test_deserialize_invalid_json():
    """Test that invalid JSON strings are kept as-is."""
    data = {"valid": '{"key": "value"}', "invalid": "not json", "partial": '{"incomplete":'}
    result = deserialize_nested_json(data)
    assert result == {
        "valid": {"key": "value"},
        "invalid": "not json",
        "partial": '{"incomplete":',
    }


def test_deserialize_non_string_values():
    """Test that non-string values pass through unchanged."""
    data = {
        "string": "plain text",
        "number": 42,
        "float": 3.14,
        "boolean": True,
        "null": None,
        "list": [1, 2, 3],
        "dict": {"nested": "value"},
    }
    result = deserialize_nested_json(data)
    assert result == data


def test_deserialize_empty_structures():
    """Test deserializing empty structures."""
    # Empty dict
    assert deserialize_nested_json({}) == {}

    # Empty list
    assert deserialize_nested_json([]) == []

    # Dict with empty string
    data = {"key": ""}
    result = deserialize_nested_json(data)
    assert result == {"key": ""}


def test_deserialize_primitive_types():
    """Test that primitive types are returned unchanged."""
    assert deserialize_nested_json("plain string") == "plain string"
    assert deserialize_nested_json(123) == 123
    assert deserialize_nested_json(45.67) == 45.67
    assert deserialize_nested_json(True) is True
    assert deserialize_nested_json(None) is None


def test_deserialize_json_array_string():
    """Test deserializing a JSON array string."""
    data = {"array": '["item1", "item2", "item3"]'}
    result = deserialize_nested_json(data)
    assert result == {"array": ["item1", "item2", "item3"]}


def test_deserialize_nested_objects_in_list():
    """Test deserializing nested objects within a list."""
    data = {"records": [{"data": '{"id": 1}'}, {"data": '{"id": 2}'}]}
    result = deserialize_nested_json(data)
    assert result == {"records": [{"data": {"id": 1}}, {"data": {"id": 2}}]}


def test_deserialize_complex_nested_structure():
    """Test deserializing a complex nested structure."""
    data = {
        "response": '{"status": "success", "data": {"users": [1, 2, 3]}}',
        "metadata": {"created": "2024-01-01", "config": '{"enabled": true}'},
    }
    result = deserialize_nested_json(data)
    assert result == {
        "response": {"status": "success", "data": {"users": [1, 2, 3]}},
        "metadata": {"created": "2024-01-01", "config": {"enabled": True}},
    }


def test_deserialize_special_json_values():
    """Test deserializing JSON strings with special values."""
    data = {
        "null_value": '{"key": null}',
        "boolean_values": '{"true": true, "false": false}',
        "numeric": '{"int": 42, "float": 3.14, "negative": -10}',
        "empty_array": '{"arr": []}',
        "empty_object": '{"obj": {}}',
    }
    result = deserialize_nested_json(data)
    assert result == {
        "null_value": {"key": None},
        "boolean_values": {"true": True, "false": False},
        "numeric": {"int": 42, "float": 3.14, "negative": -10},
        "empty_array": {"arr": []},
        "empty_object": {"obj": {}},
    }
