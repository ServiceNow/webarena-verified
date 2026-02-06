"""Comprehensive unit tests for ValueComparator class.

Tests cover:
- Single value comparisons with alternatives
- Simple arrays (ordered/unordered)
- Simple objects
- Nested structures (objects in objects, arrays in arrays)
- Mixed nesting (objects in arrays, arrays in objects)
- Deep nesting (3+ levels)
- Type mismatches at all levels (expected type guides comparison)
- Error message validation with regex patterns
- Edge cases (empty structures, large arrays, deep recursion)
"""

import re
from types import MappingProxyType

import pytest

from webarena_verified.core.evaluation.data_types import (
    URL,
    Boolean,
    Currency,
    Date,
    Distance,
    Duration,
    NormalizedString,
    Number,
)
from webarena_verified.core.evaluation.value_comparator import ValueComparator
from webarena_verified.types.eval import EvalStatus

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def comparator():
    """Create ValueComparator instance."""
    return ValueComparator()


# ============================================================================
# Helper Functions
# ============================================================================


def assert_comparison_success(result):
    """Assert that comparison succeeded (empty result list)."""
    assert result == [], f"Expected no assertions (success), but got {len(result)} assertion(s): {result}"


def assert_comparison_failure(result, expected_count=None):
    """Assert that comparison failed (non-empty result list)."""
    assert len(result) > 0, "Expected comparison to fail, but got empty result (success)"
    if expected_count is not None:
        assert len(result) == expected_count, (
            f"Expected {expected_count} assertion(s), but got {len(result)}: {[a.assertion_name for a in result]}"
        )


def assert_assertion_name_matches(result, regex_pattern):
    """Assert that at least one assertion name matches the regex pattern."""
    pattern = re.compile(regex_pattern)
    assertion_names = [assertion.assertion_name for assertion in result]
    matches = [name for name in assertion_names if pattern.search(name)]
    assert len(matches) > 0, (
        f"Expected at least one assertion name to match pattern '{regex_pattern}', "
        f"but found none. Assertion names: {assertion_names}"
    )


def assert_has_assertion_with_status(result, status: EvalStatus):
    """Assert that result contains at least one assertion with given status."""
    statuses = [assertion.status for assertion in result]
    assert status in statuses, f"Expected status {status} in assertions, but got statuses: {statuses}"


# ============================================================================
# Category 1: Basic Single Value Tests
# ============================================================================


@pytest.mark.parametrize(
    ("data_type", "value1", "value2", "should_match", "error_pattern"),
    [
        # Exact matches
        (NormalizedString, "success", "success", True, None),
        (Number, 42, 42, True, None),
        (Number, 3.14, 3.14, True, None),
        (Boolean, True, True, True, None),
        (Boolean, False, False, True, None),
        # Mismatches
        (NormalizedString, "success", "failure", False, r"value_mismatch"),
        (Number, 42, 99, False, r"value_mismatch"),
        (Boolean, True, False, False, r"value_mismatch"),
        # None comparisons
        (None, None, None, True, None),  # None == None
        (NormalizedString, "success", None, False, r"none_mismatch"),  # value != None
        (None, None, "success", False, r"none_mismatch"),  # None != value (use None as data_type to skip wrapping)
    ],
    ids=[
        "string_match",
        "number_match",
        "float_match",
        "boolean_true_match",
        "boolean_false_match",
        "string_mismatch",
        "number_mismatch",
        "boolean_mismatch",
        "none_vs_none",
        "value_vs_none",
        "none_vs_value",
    ],
)
def test_single_value_comparison(comparator, data_type, value1, value2, should_match, error_pattern):
    """Test single value comparisons with different NormalizedType classes and None."""
    # Handle None cases specially
    if data_type is None:
        expected = value1
        actual = value2
    else:
        expected = data_type(value1) if value1 is not None else None
        actual = data_type(value2) if value2 is not None else None

    result = comparator.compare(actual, expected)

    if should_match:
        assert_comparison_success(result)
    else:
        assert_comparison_failure(result)
        if error_pattern:
            assert_assertion_name_matches(result, error_pattern)


# ============================================================================
# Type Mismatch Tests - Expected Type Guides Comparison
# ============================================================================


def test_type_mismatch_expected_dict_actual_list(comparator):
    """Test type mismatch where expected is dict but actual is list.

    Expected type (dict) guides the comparison path, so the comparison follows the object path.
    """
    expected = {"key": NormalizedString("value")}
    actual = [NormalizedString("value")]

    result = comparator.compare(actual, expected)

    assert_comparison_failure(result)
    assert_assertion_name_matches(result, r"invalid_format")


def test_type_mismatch_expected_list_actual_dict(comparator):
    """Test type mismatch where expected is list but actual is dict.

    Expected type (list) guides the comparison path, so the comparison follows the array path.
    """
    expected = [NormalizedString("value")]
    actual = {"key": NormalizedString("value")}

    result = comparator.compare(actual, expected)

    assert_comparison_failure(result)
    assert_assertion_name_matches(result, r"invalid_format")


def test_type_mismatch_expected_list_actual_normalized_type(comparator):
    """Test type mismatch where expected is list but actual is single NormalizedType."""
    expected = [NormalizedString("a"), NormalizedString("b")]
    actual = NormalizedString("a")

    result = comparator.compare(actual, expected)

    assert_comparison_failure(result)
    assert_assertion_name_matches(result, r"invalid_format")


def test_type_mismatch_expected_dict_actual_normalized_type(comparator):
    """Test type mismatch where expected is dict but actual is single NormalizedType."""
    expected = {"status": NormalizedString("ok")}
    actual = NormalizedString("ok")

    result = comparator.compare(actual, expected)

    assert_comparison_failure(result)
    assert_assertion_name_matches(result, r"invalid_format")


def test_type_mismatch_expected_normalized_actual_dict(comparator):
    """Test type mismatch where expected is NormalizedType but actual is dict."""
    expected = NormalizedString("ok")
    actual = {"status": NormalizedString("ok")}

    result = comparator.compare(actual, expected)

    assert_comparison_failure(result)
    assert_assertion_name_matches(result, r"mismatch")


def test_type_mismatch_expected_normalized_actual_list(comparator):
    """Test type mismatch where expected is NormalizedType but actual is list."""
    expected = NormalizedString("ok")
    actual = [NormalizedString("ok")]

    result = comparator.compare(actual, expected)

    assert_comparison_failure(result)
    assert_assertion_name_matches(result, r"mismatch")


# ============================================================================
# Category 2: Simple Array Tests - Unordered
# ============================================================================


@pytest.mark.parametrize(
    ("expected", "actual", "should_match", "error_pattern"),
    [
        # Same order match
        (
            [Number(42), Boolean(True), Currency(10.50)],
            [Number(42), Boolean(True), Currency(10.50)],
            True,
            None,
        ),
        # Different order match
        (
            [Date("2024-01-01"), Duration("2min"), URL("https://example.com")],
            [URL("https://example.com"), Date("2024-01-01"), Duration("2min")],
            True,
            None,
        ),
        # Missing element
        ([Number(10), Boolean(False), Currency(99.99)], [Number(10), Boolean(False)], False, r"array_values_mismatch"),
        # Extra element
        (
            [Distance("5km"), Date("2024-06-15")],
            [Distance("5km"), Date("2024-06-15"), Duration("30min")],
            False,
            r"array_values_mismatch",
        ),
        # Duplicates match
        ([Number(10), Number(10), Boolean(True)], [Number(10), Boolean(True), Number(10)], True, None),
        # Duplicates missing
        (
            [Currency(10.50), Currency(10.50), Currency(20.00)],
            [Currency(10.50), Currency(20.00)],
            False,
            r"array_values_mismatch",
        ),
        # With alternatives
        ([Number([100, 200]), Duration("5min")], [Number(200), Duration("5min")], True, None),
        # Empty arrays
        ([], [], True, None),
        # Empty vs non-empty
        ([URL("https://example.com")], [], False, None),
        # One mismatch
        (
            [Date("2024-01-01"), Date("2024-02-01"), Date("2024-03-01")],
            [Date("2024-01-01"), Date("2024-02-01"), Date("2024-04-01")],
            False,
            r"array_values_mismatch",
        ),
    ],
    ids=[
        "same_order",
        "different_order",
        "missing_element",
        "extra_element",
        "duplicates_match",
        "duplicates_missing",
        "with_alternatives",
        "empty_arrays",
        "empty_vs_non_empty",
        "one_mismatch",
    ],
)
def test_unordered_array_scenarios(comparator, expected, actual, should_match, error_pattern):
    """Test various unordered array comparison scenarios."""
    result = comparator.compare(actual, expected, ordered=False)

    if should_match:
        assert_comparison_success(result)
    else:
        assert_comparison_failure(result)
        if error_pattern:
            assert_assertion_name_matches(result, error_pattern)


# ============================================================================
# Category 3: Simple Array Tests - Ordered
# ============================================================================


@pytest.mark.parametrize(
    ("expected", "actual", "should_match", "error_pattern"),
    [
        # Exact match
        (
            [Duration("10min"), Currency(25.50), Boolean(True)],
            [Duration("10min"), Currency(25.50), Boolean(True)],
            True,
            None,
        ),
        # Wrong order
        ([Number(1), Number(2), Number(3)], [Number(3), Number(2), Number(1)], False, r"value\[0\]_mismatch"),
        # Partial reorder
        (
            [URL("https://a.com"), URL("https://b.com"), URL("https://c.com")],
            [URL("https://a.com"), URL("https://c.com"), URL("https://b.com")],
            False,
            None,
        ),
        # Missing at end
        (
            [Distance("5km"), Distance("10km"), Distance("15km")],
            [Distance("5km"), Distance("10km")],
            False,
            r"array_values_mismatch",
        ),
        # Extra at end
        ([Boolean(True), Boolean(False)], [Boolean(True), Boolean(False), Boolean(True)], False, None),
        # With alternatives
        (
            [NormalizedString(["success", "ok"]), Duration("30min")],
            [NormalizedString("ok"), Duration("30min")],
            True,
            None,
        ),
        # Alternatives wrong position
        ([Number(1), Number([2, 3])], [Number(3), Number(1)], False, None),
    ],
    ids=[
        "exact_match",
        "wrong_order",
        "partial_reorder",
        "missing_at_end",
        "extra_at_end",
        "with_alternatives",
        "alternatives_wrong_position",
    ],
)
def test_ordered_array_scenarios(comparator, expected, actual, should_match, error_pattern):
    """Test various ordered array comparison scenarios."""
    result = comparator.compare(actual, expected, ordered=True)

    if should_match:
        assert_comparison_success(result)
    else:
        assert_comparison_failure(result)
        if error_pattern:
            assert_assertion_name_matches(result, error_pattern)


# ============================================================================
# Category 4: Simple Object Tests
# ============================================================================


@pytest.mark.parametrize(
    ("expected", "actual", "should_match", "error_pattern"),
    [
        # Exact match
        (
            {"status": NormalizedString("success"), "code": Number(200), "enabled": Boolean(True)},
            {"status": NormalizedString("success"), "code": Number(200), "enabled": Boolean(True)},
            True,
            None,
        ),
        # Missing key
        (
            {"name": NormalizedString("Item"), "price": Currency(99.99), "url": URL("https://shop.com")},
            {"name": NormalizedString("Item"), "price": Currency(99.99)},
            False,
            r"keys_mismatch",
        ),
        # Extra key
        (
            {"city": NormalizedString("NYC"), "distance": Distance("10km")},
            {"city": NormalizedString("NYC"), "distance": Distance("10km"), "duration": Duration("15min")},
            False,
            r"keys_mismatch",
        ),
        # Value mismatch
        (
            {"price": Currency(100.00), "distance": Distance("5km")},
            {"price": Currency(150.00), "distance": Distance("5km")},
            False,
            r"price.*mismatch",
        ),
        # With alternatives
        (
            {"duration": Duration(["5min", "10min", "15min"]), "distance": Distance("2km")},
            {"duration": Duration("10min"), "distance": Distance("2km")},
            True,
            None,
        ),
    ],
    ids=[
        "exact_match",
        "missing_key",
        "extra_key",
        "value_mismatch",
        "with_alternatives",
    ],
)
def test_object_scenarios(comparator, expected, actual, should_match, error_pattern):
    """Test various object comparison scenarios."""
    result = comparator.compare(actual, expected)

    if should_match:
        assert_comparison_success(result)
    else:
        assert_comparison_failure(result)
        if error_pattern:
            assert_assertion_name_matches(result, error_pattern)


def test_object_extra_key_ignored(comparator):
    """Test object with extra key ignored when flag is set."""
    expected = {"verified": Boolean(True)}
    actual = {"verified": Boolean(True), "timestamp": Date("2024-01-01")}

    result = comparator.compare(
        expected=expected,
        actual=actual,
        value_name="test",
        ignore_extra_keys=True,
        ordered=False,  # Need to pass ordered parameter
    )

    assert_comparison_success(result)


def test_object_ignored_keys(comparator):
    """Test object with ignored_values_keys parameter."""
    expected = {"verified": Boolean(True), "created_date": Date("2024-01-01")}
    actual = {"verified": Boolean(True), "created_date": Date("2024-12-31")}

    result = comparator.compare(
        expected=expected, actual=actual, value_name="test", ignored_values_keys={"created_date"}
    )

    assert_comparison_success(result)


def test_object_mapping_proxy_type(comparator):
    """Test that MappingProxyType works as expected object."""
    expected = MappingProxyType({"count": Number(42), "url": URL("https://api.example.com")})
    actual = {"count": Number(42), "url": URL("https://api.example.com")}

    result = comparator.compare(actual, expected)

    assert_comparison_success(result)


# ============================================================================
# Category 5: Nested Objects (Objects in Objects)
# ============================================================================


@pytest.mark.parametrize(
    ("expected", "actual", "should_match", "error_pattern"),
    [
        # 2-level nested objects match
        (
            {"user": {"name": NormalizedString("John"), "age": Number(30), "verified": Boolean(True)}},
            {"user": {"name": NormalizedString("John"), "age": Number(30), "verified": Boolean(True)}},
            True,
            None,
        ),
        # 2-level nested object value mismatch
        (
            {"location": {"city": NormalizedString("NYC"), "distance": Distance("10km")}},
            {"location": {"city": NormalizedString("LA"), "distance": Distance("10km")}},
            False,
            r"value\.location\.city.*mismatch",
        ),
        # 3-level nested objects match
        (
            {"data": {"product": {"details": {"price": Currency(99.99), "url": URL("https://shop.com")}}}},
            {"data": {"product": {"details": {"price": Currency(99.99), "url": URL("https://shop.com")}}}},
            True,
            None,
        ),
        # Missing nested key
        (
            {"booking": {"date": Date("2024-06-15"), "duration": Duration("2h")}},
            {"booking": {"date": Date("2024-06-15")}},
            False,
            r"value\.booking.*keys_mismatch",
        ),
        # With alternatives
        (
            {"shipping": {"method": NormalizedString(["express", "priority", "overnight"])}},
            {"shipping": {"method": NormalizedString("priority")}},
            True,
            None,
        ),
        # Mixed types
        (
            {"trip": {"distance": Distance("25km"), "duration": Duration("30min"), "cost": Currency(45.00)}},
            {"trip": {"distance": Distance("25km"), "duration": Duration("30min"), "cost": Currency(45.00)}},
            True,
            None,
        ),
        # Type mismatch at nested level
        (
            {"event": {"dates": [Date("2024-01-01"), Date("2024-01-02")]}},
            {"event": {"dates": Date("2024-01-01")}},
            False,
            r"value\.event\.dates.*invalid_format",
        ),
    ],
    ids=[
        "2_levels_match",
        "2_levels_value_mismatch",
        "3_levels_match",
        "missing_nested_key",
        "with_alternatives",
        "mixed_types",
        "type_mismatch_at_nested_level",
    ],
)
def test_nested_object_scenarios(comparator, expected, actual, should_match, error_pattern):
    """Test various nested object comparison scenarios."""
    result = comparator.compare(actual, expected)

    if should_match:
        assert_comparison_success(result)
    else:
        assert_comparison_failure(result)
        if error_pattern:
            assert_assertion_name_matches(result, error_pattern)


# ============================================================================
# Category 6: Nested Arrays (Arrays in Arrays)
# ============================================================================


@pytest.mark.parametrize(
    ("expected", "actual", "ordered", "should_match", "error_pattern"),
    [
        # 2-level ordered match
        (
            [[Number(1), Number(2)], [Number(3), Number(4)]],
            [[Number(1), Number(2)], [Number(3), Number(4)]],
            True,
            True,
            None,
        ),
        # 2-level wrong nested order
        (
            [[Currency(10.00), Currency(20.00)], [Currency(30.00), Currency(40.00)]],
            [[Currency(10.00), Currency(20.00)], [Currency(40.00), Currency(30.00)]],
            True,
            False,
            r"value\[1\].*mismatch",
        ),
        # 2-level unordered match
        (
            [[Boolean(True), Boolean(False)], [Boolean(False), Boolean(True)]],
            [[Boolean(False), Boolean(True)], [Boolean(True), Boolean(False)]],
            False,
            True,
            None,
        ),
        # 3-level nested arrays
        (
            [[[Duration("5min"), Duration("10min")], [Duration("15min")]], [[Duration("20min"), Duration("25min")]]],
            [[[Duration("5min"), Duration("10min")], [Duration("15min")]], [[Duration("20min"), Duration("25min")]]],
            True,
            True,
            None,
        ),
        # Different nested lengths
        (
            [[Distance("5km"), Distance("10km")], [Distance("15km"), Distance("20km")]],
            [[Distance("5km"), Distance("10km")], [Distance("15km")]],
            True,
            False,
            None,
        ),
        # Empty nested arrays
        ([[URL("https://example.com")], []], [[URL("https://example.com")], []], True, True, None),
        # Empty vs non-empty nested
        (
            [[Date("2024-01-01")], []],
            [[Date("2024-01-01")], [Date("2024-02-01")]],
            True,
            False,
            None,
        ),
    ],
    ids=[
        "2_level_ordered_match",
        "2_level_wrong_nested_order",
        "2_level_unordered_match",
        "3_level_nested",
        "different_nested_lengths",
        "empty_nested",
        "empty_vs_non_empty",
    ],
)
def test_nested_array_scenarios(comparator, expected, actual, ordered, should_match, error_pattern):
    """Test various nested array comparison scenarios."""
    result = comparator.compare(actual, expected, ordered=ordered)

    if should_match:
        assert_comparison_success(result)
    else:
        assert_comparison_failure(result)
        if error_pattern:
            assert_assertion_name_matches(result, error_pattern)


# ============================================================================
# Category 7: Mixed Nesting - Objects in Arrays
# ============================================================================


@pytest.mark.parametrize(
    ("expected", "actual", "ordered", "should_match", "error_pattern"),
    [
        # Ordered match
        (
            [
                {"city": NormalizedString("NYC"), "distance": Distance("10km"), "cost": Currency(50.00)},
                {"city": NormalizedString("LA"), "distance": Distance("20km"), "cost": Currency(75.00)},
            ],
            [
                {"city": NormalizedString("NYC"), "distance": Distance("10km"), "cost": Currency(50.00)},
                {"city": NormalizedString("LA"), "distance": Distance("20km"), "cost": Currency(75.00)},
            ],
            True,
            True,
            None,
        ),
        # Ordered wrong order
        (
            [
                {"date": Date("2024-01-01"), "duration": Duration("2h")},
                {"date": Date("2024-02-01"), "duration": Duration("3h")},
            ],
            [
                {"date": Date("2024-02-01"), "duration": Duration("3h")},
                {"date": Date("2024-01-01"), "duration": Duration("2h")},
            ],
            True,
            False,
            None,
        ),
        # Unordered match
        (
            [
                {"url": URL("https://api.example.com"), "enabled": Boolean(True)},
                {"url": URL("https://api.test.com"), "enabled": Boolean(False)},
            ],
            [
                {"url": URL("https://api.test.com"), "enabled": Boolean(False)},
                {"url": URL("https://api.example.com"), "enabled": Boolean(True)},
            ],
            False,
            True,
            None,
        ),
        # Missing key in nested object
        (
            [{"product": NormalizedString("Laptop"), "price": Currency(999.99)}],
            [{"product": NormalizedString("Laptop")}],
            True,
            False,
            r"value\[0\].*keys_mismatch",
        ),
        # With alternatives
        (
            [{"mode": NormalizedString(["express", "priority"]), "duration": Duration("30min")}],
            [{"mode": NormalizedString("priority"), "duration": Duration("30min")}],
            True,
            True,
            None,
        ),
        # Type mismatch - expects objects but gets primitives
        ([{"count": Number(42)}], [Number(42)], True, False, r"value\[0\].*invalid_format"),
    ],
    ids=[
        "ordered_match",
        "ordered_wrong_order",
        "unordered_match",
        "missing_key",
        "with_alternatives",
        "type_mismatch",
    ],
)
def test_array_of_objects_scenarios(comparator, expected, actual, ordered, should_match, error_pattern):
    """Test various array of objects comparison scenarios."""
    result = comparator.compare(actual, expected, ordered=ordered)

    if should_match:
        assert_comparison_success(result)
    else:
        assert_comparison_failure(result)
        if error_pattern:
            assert_assertion_name_matches(result, error_pattern)


# ============================================================================
# Category 8: Mixed Nesting - Arrays in Objects
# ============================================================================


@pytest.mark.parametrize(
    ("expected", "actual", "ordered", "should_match", "error_pattern"),
    [
        # Object containing array
        (
            {"prices": [Currency(10.00), Currency(20.00), Currency(30.00)], "count": Number(3)},
            {"prices": [Currency(10.00), Currency(20.00), Currency(30.00)], "count": Number(3)},
            False,
            True,
            None,
        ),
        # Object with ordered array
        (
            {"dates": [Date("2024-01-01"), Date("2024-02-01"), Date("2024-03-01")]},
            {"dates": [Date("2024-01-01"), Date("2024-02-01"), Date("2024-03-01")]},
            True,
            True,
            None,
        ),
        # Object with unordered array different order
        (
            {"urls": [URL("https://a.com"), URL("https://b.com"), URL("https://c.com")]},
            {"urls": [URL("https://c.com"), URL("https://a.com"), URL("https://b.com")]},
            False,
            True,
            None,
        ),
        # Nested object with arrays
        (
            {"schedule": {"times": [Duration("1h"), Duration("2h")], "total": Duration("3h")}},
            {"schedule": {"times": [Duration("1h"), Duration("2h")], "total": Duration("3h")}},
            False,
            True,
            None,
        ),
        # Object array value mismatch
        (
            {"distances": [Distance("5km"), Distance("10km")]},
            {"distances": [Distance("5km"), Distance("15km")]},
            False,
            False,
            r"value\.distances.*mismatch",
        ),
        # Object array type mismatch
        (
            {"tags": [NormalizedString("python"), NormalizedString("javascript")]},
            {"tags": NormalizedString("python")},
            False,
            False,
            r"value\.tags.*invalid_format",
        ),
    ],
    ids=[
        "containing_array",
        "ordered_array",
        "unordered_different_order",
        "nested_with_arrays",
        "array_mismatch",
        "array_type_mismatch",
    ],
)
def test_object_with_array_scenarios(comparator, expected, actual, ordered, should_match, error_pattern):
    """Test various object with array comparison scenarios."""
    result = comparator.compare(actual, expected, ordered=ordered)

    if should_match:
        assert_comparison_success(result)
    else:
        assert_comparison_failure(result)
        if error_pattern:
            assert_assertion_name_matches(result, error_pattern)


# ============================================================================
# Category 9: Deep Nesting (3+ Levels)
# ============================================================================


@pytest.mark.parametrize(
    ("expected", "actual", "ordered", "should_match", "custom_check"),
    [
        # 3-level: Array -> Object -> Array
        (
            [{"prices": [Currency(10.00), Currency(20.00)]}, {"prices": [Currency(30.00), Currency(40.00)]}],
            [{"prices": [Currency(10.00), Currency(20.00)]}, {"prices": [Currency(30.00), Currency(40.00)]}],
            True,
            True,
            None,
        ),
        # 3-level: Object -> Array -> Object
        (
            {
                "trips": [
                    {"destination": NormalizedString("NYC"), "distance": Distance("500km"), "cost": Currency(150.00)},
                    {"destination": NormalizedString("LA"), "distance": Distance("800km"), "cost": Currency(250.00)},
                ]
            },
            {
                "trips": [
                    {"destination": NormalizedString("NYC"), "distance": Distance("500km"), "cost": Currency(150.00)},
                    {"destination": NormalizedString("LA"), "distance": Distance("800km"), "cost": Currency(250.00)},
                ]
            },
            False,
            True,
            None,
        ),
        # 4-level: Object -> Object -> Array -> Object -> Array
        (
            {"data": {"bookings": [{"dates": [Date("2024-01-01"), Date("2024-01-02")]}]}},
            {"data": {"bookings": [{"dates": [Date("2024-01-01"), Date("2024-01-02")]}]}},
            False,
            True,
            None,
        ),
        # 5-level deep nesting
        (
            {"level1": {"level2": [{"level3": {"level4": [NormalizedString("a"), NormalizedString("b")]}}]}},
            {"level1": {"level2": [{"level3": {"level4": [NormalizedString("a"), NormalizedString("b")]}}]}},
            False,
            True,
            None,
        ),
        # Ordered flag propagation through nesting
        (
            {"data": [{"items": [NormalizedString("a"), NormalizedString("b")]}]},
            {"data": [{"items": [NormalizedString("b"), NormalizedString("a")]}]},
            True,
            False,
            None,
        ),
        # Mismatch at level 3
        (
            {"data": {"results": [{"name": NormalizedString("Alice")}]}},
            {"data": {"results": [{"name": NormalizedString("Bob")}]}},
            False,
            False,
            lambda result: "results" in "|".join([a.assertion_name for a in result])
            and "mismatch" in "|".join([a.assertion_name for a in result]),
        ),
        # Type mismatch at level 3
        (
            {"data": {"results": [{"tags": [NormalizedString("a")]}]}},
            {"data": {"results": [{"tags": NormalizedString("a")}]}},
            False,
            False,
            lambda result: "results" in "|".join([a.assertion_name for a in result])
            and (
                "mismatch" in "|".join([a.assertion_name for a in result])
                or "invalid" in "|".join([a.assertion_name for a in result])
            ),
        ),
    ],
    ids=[
        "3_level_array_object_array",
        "3_level_object_array_object",
        "4_level_nesting",
        "5_level_nesting",
        "ordered_flag_propagation",
        "mismatch_at_level_3",
        "type_mismatch_at_level_3",
    ],
)
def test_deep_nesting_scenarios(comparator, expected, actual, ordered, should_match, custom_check):
    """Test various deep nesting comparison scenarios (3+ levels)."""
    result = comparator.compare(actual, expected, ordered=ordered)

    if should_match:
        assert_comparison_success(result)
    else:
        assert_comparison_failure(result)
        if custom_check:
            assert custom_check(result), f"Custom check failed for result: {[a.assertion_name for a in result]}"


# ============================================================================
# Category 10: Real Dataset Nesting Patterns - Error Cases
# ============================================================================


def test_operating_hours_missing_field(comparator):
    """Test operating hours with missing field in one object."""
    expected = [
        {
            "day": NormalizedString("Wednesday"),
            "open_time": NormalizedString("10:00"),
            "close_time": NormalizedString("17:00"),
        },
        {
            "day": NormalizedString("Thursday"),
            "open_time": NormalizedString("10:00"),
            "close_time": NormalizedString("17:00"),
        },
    ]
    actual = [
        {
            "day": NormalizedString("Wednesday"),
            "open_time": NormalizedString("10:00"),
            "close_time": NormalizedString("17:00"),
        },
        {"day": NormalizedString("Thursday"), "open_time": NormalizedString("10:00")},  # Missing close_time
    ]

    result = comparator.compare(actual, expected, ordered=True)
    assert_comparison_failure(result)
    assert_assertion_name_matches(result, r"value\[1\].*keys_mismatch")


def test_price_range_wrong_values(comparator):
    """Test price range with wrong min/max values."""
    expected = [{"min": Currency(5.49), "max": Currency(375.19)}]
    actual = [{"min": Currency(1.00), "max": Currency(375.19)}]  # Wrong min

    result = comparator.compare(actual, expected)
    assert_comparison_failure(result)
    # When comparing arrays of objects, either individual field or array mismatch is reported
    assert_assertion_name_matches(result, r"(value\[0\]\.min.*mismatch|value_array_values_mismatch)")


def test_transportation_modes_wrong_order_ordered(comparator):
    """Test transportation modes in wrong order with ordered comparison."""
    expected = [
        {"mode": NormalizedString("driving"), "duration": NormalizedString("2min")},
        {"mode": NormalizedString("walking"), "duration": NormalizedString("16min")},
    ]
    actual = [
        {"mode": NormalizedString("walking"), "duration": NormalizedString("16min")},
        {"mode": NormalizedString("driving"), "duration": NormalizedString("2min")},
    ]

    result = comparator.compare(actual, expected, ordered=True)
    assert_comparison_failure(result)


# ============================================================================
# Category 11: Edge Cases
# ============================================================================


def test_deeply_nested_empty_arrays(comparator):
    """Test empty arrays at various nesting levels."""
    expected = [[], [NormalizedString("a")], [], [NormalizedString("b"), NormalizedString("c")]]
    actual = [[], [NormalizedString("a")], [], [NormalizedString("b"), NormalizedString("c")]]

    result = comparator.compare(actual, expected, ordered=True)

    assert_comparison_success(result)


def test_all_elements_are_alternatives(comparator):
    """Test array where all elements have alternatives."""
    expected = [
        NormalizedString(["a", "b"]),
        NormalizedString(["c", "d"]),
        NormalizedString(["e", "f"]),
    ]
    actual = [NormalizedString("b"), NormalizedString("d"), NormalizedString("f")]

    result = comparator.compare(actual, expected, ordered=True)

    assert_comparison_success(result)


def test_unicode_in_nested_structures(comparator):
    """Test unicode characters in nested structures."""
    expected = {"user": {"name": NormalizedString("Café"), "city": NormalizedString("Zürich")}}
    actual = {"user": {"name": NormalizedString("Café"), "city": NormalizedString("Zürich")}}

    result = comparator.compare(actual, expected)

    assert_comparison_success(result)


def test_large_array_performance(comparator):
    """Test performance with large array (1000 elements)."""
    size = 1000
    expected = [NormalizedString(f"item_{i}") for i in range(size)]
    actual = [NormalizedString(f"item_{i}") for i in range(size)]

    result = comparator.compare(actual, expected, ordered=True)

    assert_comparison_success(result)


def test_very_deep_nesting_recursion(comparator):
    """Test very deep nesting (10 levels) for recursion handling."""
    # Build 10-level nested structure: object -> array -> object -> array -> ...
    expected = {"level0": [{"level1": [{"level2": [{"level3": [{"level4": [NormalizedString("deep")]}]}]}]}]}
    actual = {"level0": [{"level1": [{"level2": [{"level3": [{"level4": [NormalizedString("deep")]}]}]}]}]}

    result = comparator.compare(actual, expected)

    assert_comparison_success(result)


# ============================================================================
# Category 12: Error Message Quality Tests with Regex
# ============================================================================


@pytest.mark.parametrize(
    ("expected", "actual", "ordered", "custom_check", "description"),
    [
        # Full path in nested object
        (
            {"data": {"user": {"profile": {"name": NormalizedString("John")}}}},
            {"data": {"user": {"profile": {"name": NormalizedString("Jane")}}}},
            False,
            lambda result: any(
                re.search(r"value\.data\.user\.profile\.name.*mismatch", a.assertion_name) for a in result
            ),
            "full_path_nested_object",
        ),
        # Full path in array of objects
        (
            [{"name": NormalizedString("Alice")}, {"name": NormalizedString("Bob")}],
            [{"name": NormalizedString("Alice")}, {"name": NormalizedString("Charlie")}],
            True,
            lambda result: any(re.search(r"value\[1\]\.name.*mismatch", a.assertion_name) for a in result),
            "full_path_array_of_objects",
        ),
        # Matched count in arrays - check individual element errors
        (
            [NormalizedString("a"), NormalizedString("b"), NormalizedString("c"), NormalizedString("d")],
            [NormalizedString("a"), NormalizedString("b"), NormalizedString("x"), NormalizedString("y")],
            True,
            lambda result: len(result) >= 2
            and any(re.search(r"value\[2\]_mismatch", a.assertion_name) for a in result)
            and any(re.search(r"value\[3\]_mismatch", a.assertion_name) for a in result),
            "matched_count_arrays",
        ),
        # Type mismatch clear message
        (
            [NormalizedString("a")],
            {"key": NormalizedString("a")},
            False,
            lambda result: any(re.search(r"invalid_format", a.assertion_name) for a in result),
            "type_mismatch_clear",
        ),
        # Multiple errors at different levels
        (
            {"user": {"name": NormalizedString("John"), "age": Number(30)}, "status": NormalizedString("active")},
            {"user": {"name": NormalizedString("Jane"), "age": Number(25)}, "status": NormalizedString("inactive")},
            False,
            lambda result: len(result) >= 2
            and any("name" in a.assertion_name for a in result)
            and any("age" in a.assertion_name for a in result)
            and any("status" in a.assertion_name for a in result),
            "multiple_errors_different_levels",
        ),
        # Assertion name pattern
        (
            {"items": [NormalizedString("a")]},
            {"items": [NormalizedString("b")]},
            False,
            lambda result: "items" in "|".join([a.assertion_name for a in result])
            and "mismatch" in "|".join([a.assertion_name for a in result]),
            "assertion_name_pattern",
        ),
    ],
    ids=[
        "full_path_nested_object",
        "full_path_array_of_objects",
        "matched_count_arrays",
        "type_mismatch_clear",
        "multiple_errors_different_levels",
        "assertion_name_pattern",
    ],
)
def test_error_message_quality(comparator, expected, actual, ordered, custom_check, description):
    """Test error message quality and formatting."""
    result = comparator.compare(actual, expected, ordered=ordered)

    assert_comparison_failure(result)
    assert custom_check(result), f"Error message check failed for {description}: {[a.assertion_name for a in result]}"


# ============================================================================
# Category 13: Contextual Array Error Messages
# ============================================================================


def test_array_error_message_all_expected_found_with_extras(comparator):
    """Test contextual error message when all expected elements are found but extras exist."""
    expected = [Number(10), Number(20), Number(30)]
    actual = [Number(10), Number(20), Number(30), Number(40), Number(50)]

    result = comparator.compare(actual, expected, ordered=False)

    assert_comparison_failure(result)
    assert len(result) == 1
    # Check that the message clearly indicates all expected were found but extras exist
    assertion_msg = result[0].assertion_msgs[0]
    assert "contains all expected elements (3/3)" in assertion_msg
    assert "2 extra element(s)" in assertion_msg


def test_array_error_message_missing_elements_no_extras(comparator):
    """Test contextual error message when some expected elements are missing with no extras."""
    expected = [Number(10), Number(20), Number(30), Number(40), Number(50)]
    actual = [Number(10), Number(20), Number(30)]

    result = comparator.compare(actual, expected, ordered=False)

    assert_comparison_failure(result)
    assert len(result) == 1
    # Check that the message clearly indicates missing elements
    assertion_msg = result[0].assertion_msgs[0]
    assert "missing 2 expected element(s)" in assertion_msg
    assert "Matched (3/5)" in assertion_msg


def test_array_error_message_both_missing_and_extras(comparator):
    """Test contextual error message when both missing expected and extra actual elements."""
    expected = [Number(10), Number(20), Number(30)]
    actual = [Number(10), Number(40), Number(50)]

    result = comparator.compare(actual, expected, ordered=False)

    assert_comparison_failure(result)
    assert len(result) == 1
    # Check that the message shows both missing and extra counts
    assertion_msg = result[0].assertion_msgs[0]
    assert "Matched (1/3)" in assertion_msg
    assert "Missing: 2" in assertion_msg
    assert "Extra: 2" in assertion_msg


# ============================================================================
# Category 14: Circular Reference Protection
# ============================================================================


def test_circular_reference_simple_dict(comparator):
    """Test detection of simple circular reference in dict."""
    actual: dict = {"key": "value"}
    actual["self"] = actual  # Circular reference
    expected = {"key": NormalizedString("value"), "self": {}}

    with pytest.raises(ValueError, match=r"Circular reference detected"):
        comparator.compare(actual, expected)


def test_circular_reference_nested_objects(comparator):
    """Test detection of circular reference A → B → A."""
    obj_a: dict = {"name": "A"}
    obj_b: dict = {"name": "B", "ref": obj_a}
    obj_a["ref"] = obj_b  # Circular: A → B → A

    expected = {"name": NormalizedString("A"), "ref": {"name": NormalizedString("B"), "ref": {}}}

    with pytest.raises(ValueError, match=r"Circular reference detected"):
        comparator.compare(obj_a, expected)


def test_circular_reference_in_array(comparator):
    """Test detection of circular reference in array."""
    arr: list = [NormalizedString("item1")]
    arr.append(arr)  # Circular reference

    expected = [NormalizedString("item1"), []]

    with pytest.raises(ValueError, match=r"Circular reference detected"):
        comparator.compare(arr, expected)


def test_no_false_positive_deep_nesting(comparator):
    """Ensure deep nesting without circular refs still works."""
    # 10 levels deep but no circular references
    expected = {"level0": [{"level1": [{"level2": [{"level3": [{"level4": [NormalizedString("deep")]}]}]}]}]}
    actual = {"level0": [{"level1": [{"level2": [{"level3": [{"level4": [NormalizedString("deep")]}]}]}]}]}

    result = comparator.compare(actual, expected)
    assert_comparison_success(result)


def test_circular_reference_error_message_includes_path(comparator):
    """Verify error message includes the path where circular ref was detected."""
    actual: dict = {"data": {"nested": {}}}
    actual["data"]["nested"]["circular"] = actual  # Circular ref
    expected = {"data": {"nested": {"circular": {}}}}

    with pytest.raises(ValueError, match=r"path 'value\.data\.nested\.circular'"):
        comparator.compare(actual, expected)


def test_circular_reference_in_mixed_structure(comparator):
    """Test circular reference in mixed array-object structure."""
    obj: dict = {"items": []}
    obj["items"].append(obj)  # Circular reference via array

    expected = {"items": [{}]}

    with pytest.raises(ValueError, match=r"Circular reference detected"):
        comparator.compare(obj, expected)
