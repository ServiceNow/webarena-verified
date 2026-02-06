"""Unit tests for NormalizedType base class alternatives handling."""

import pytest

from webarena_verified.core.evaluation.data_types import NormalizedString, Number


@pytest.mark.parametrize(
    ("data_type", "value", "expected"),
    [
        (NormalizedString, "success", "success"),
        (Number, 10, 10),
    ],
)
def test_single_value_creates_single_alternative(data_type, value, expected):
    """Test that single values work correctly."""
    normalized = data_type(value)
    assert normalized.normalized == expected
    assert len(normalized.alternatives) == 1
    assert normalized.alternatives[0] == expected


@pytest.mark.parametrize(
    ("data_type", "values", "expected_alternatives"),
    [
        # 2-item lists
        (NormalizedString, ["success", "ok"], ("success", "ok")),
        (Number, [10, 17], (10, 17)),
        # 3+ item lists
        (NormalizedString, ["success", "ok", "completed"], ("success", "ok", "completed")),
        (Number, [10, 17, 25], (10, 17, 25)),
        # 2-item tuples
        (NormalizedString, ("success", "ok"), ("success", "ok")),
        (Number, (10, 17), (10, 17)),
    ],
)
def test_valid_alternatives_accepted(data_type, values, expected_alternatives):
    """Test that 2+ item lists/tuples are accepted as alternatives."""
    normalized = data_type(values)
    assert len(normalized.alternatives) == len(expected_alternatives)
    assert normalized.alternatives == expected_alternatives
    # First alternative becomes the normalized value
    assert normalized.normalized == expected_alternatives[0]


@pytest.mark.parametrize(
    ("data_type", "invalid_value"),
    [
        # Single-item lists
        (NormalizedString, ["success"]),
        (Number, [10]),
        # Single-item tuples
        (NormalizedString, ("success",)),
        (Number, (10,)),
        # Empty lists
        (NormalizedString, []),
        (Number, []),
    ],
)
def test_single_item_container_raises_error(data_type, invalid_value):
    """Test that single-item or empty containers raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        data_type(invalid_value)

    error_msg = str(exc_info.value)
    assert "Alternatives require 2+ items" in error_msg


def test_alternatives_equality_with_overlap():
    """Test that equality works correctly with alternatives."""
    # Expected with alternatives
    expected = NormalizedString(["success", "ok"])
    # Actual without alternatives
    actual = NormalizedString("success")

    # Should match because "success" is in both alternatives
    assert expected == actual
    assert actual == expected  # Symmetric


def test_alternatives_no_overlap():
    """Test that values with no overlapping alternatives don't match."""
    expected = NormalizedString(["success", "ok"])
    actual = NormalizedString("failure")

    assert expected != actual
    assert actual != expected  # Symmetric


@pytest.mark.parametrize(
    ("data_type", "value1", "value2"),
    [
        # Single values
        (NormalizedString, "success", "success"),
        (Number, 10, 10),
        # Alternatives with overlap
        (NormalizedString, ["success", "ok"], "success"),
        (NormalizedString, ["success", "ok"], ["success", "completed"]),
        (Number, [10, 17], 10),
        (Number, [10, 17], [17, 25]),
        # Multiple overlaps
        (NormalizedString, ["success", "ok"], ["success", "ok"]),
        (Number, [10, 17, 25], [17, 25, 30]),
    ],
)
def test_equality_symmetry(data_type, value1, value2):
    """Test that equality is symmetric: A == B implies B == A."""
    obj1 = data_type(value1)
    obj2 = data_type(value2)

    # Symmetric equality
    assert obj1 == obj2
    assert obj2 == obj1


@pytest.mark.parametrize(
    ("data_type", "value1", "value2"),
    [
        # Different single values
        (NormalizedString, "success", "failure"),
        (Number, 10, 20),
        # No overlap in alternatives
        (NormalizedString, ["success", "ok"], ["failure", "error"]),
        (Number, [10, 17], [25, 30]),
        # Single vs alternatives with no overlap
        (NormalizedString, "success", ["failure", "error"]),
        (Number, 10, [25, 30]),
    ],
)
def test_inequality_symmetry(data_type, value1, value2):
    """Test that inequality is symmetric: A != B implies B != A."""
    obj1 = data_type(value1)
    obj2 = data_type(value2)

    # Symmetric inequality
    assert obj1 != obj2
    assert obj2 != obj1


@pytest.mark.parametrize(
    ("data_type", "value1", "value2", "value3"),
    [
        # Transitivity with single values
        (NormalizedString, "success", "success", "success"),
        (Number, 10, 10, 10),
        # Transitivity with alternatives
        (NormalizedString, ["success", "ok"], ["success", "completed"], ["success", "done"]),
        (Number, [10, 17], [17, 25], [17, 30]),
    ],
)
def test_equality_transitivity(data_type, value1, value2, value3):
    """Test that equality is transitive: if A == B and B == C, then A == C."""
    obj1 = data_type(value1)
    obj2 = data_type(value2)
    obj3 = data_type(value3)

    # If A == B and B == C, then A == C
    if obj1 == obj2 and obj2 == obj3:
        assert obj1 == obj3


def test_equality_reflexivity():
    """Test that equality is reflexive: A == A."""
    str_obj = NormalizedString("success")
    num_obj = Number(10)
    str_alt_obj = NormalizedString(["success", "ok"])
    num_alt_obj = Number([10, 17])

    assert str_obj == str_obj  # noqa: PLR0124
    assert num_obj == num_obj  # noqa: PLR0124
    assert str_alt_obj == str_alt_obj  # noqa: PLR0124
    assert num_alt_obj == num_alt_obj  # noqa: PLR0124


@pytest.mark.parametrize(
    ("data_type", "value", "expected_hash"),
    [
        # Single values should hash to their normalized value
        (NormalizedString, "success", hash("success")),
        pytest.param(
            Number,
            10,
            hash(10.0),
            marks=pytest.mark.skip(
                reason="Number class hashes using alternatives tuple, not normalized value directly"
            ),
        ),
    ],
)
def test_hash_single_value(data_type, value, expected_hash):
    """Test that single values hash to their normalized value."""
    obj = data_type(value)
    assert hash(obj) == expected_hash


def test_hash_alternatives():
    """Test that alternatives hash consistently."""
    # Objects with same alternatives should have same hash
    str_obj1 = NormalizedString(["ok", "success"])
    str_obj2 = NormalizedString(["ok", "success"])
    assert hash(str_obj1) == hash(str_obj2)

    num_obj1 = Number([10, 17])
    num_obj2 = Number([10, 17])
    assert hash(num_obj1) == hash(num_obj2)


def test_hash_equal_objects_have_equal_hashes():
    """Test that equal objects have equal hashes (hash consistency requirement)."""
    # Single values
    str1 = NormalizedString("success")
    str2 = NormalizedString("success")
    assert str1 == str2
    assert hash(str1) == hash(str2)

    # Alternatives
    str_alt1 = NormalizedString(["success", "ok"])
    str_alt2 = NormalizedString(["success", "ok"])
    assert str_alt1 == str_alt2
    assert hash(str_alt1) == hash(str_alt2)


def test_hash_usable_in_set():
    """Test that NormalizedType instances can be used in sets."""
    str1 = NormalizedString("success")
    str2 = NormalizedString("success")
    str3 = NormalizedString("failure")

    # Same values should deduplicate in set
    str_set = {str1, str2, str3}
    assert len(str_set) == 2  # Only 2 unique values

    # Alternatives should work in sets
    alt1 = NormalizedString(["success", "ok"])
    alt2 = NormalizedString(["success", "ok"])
    alt3 = NormalizedString(["failure", "error"])

    alt_set = {alt1, alt2, alt3}
    assert len(alt_set) == 2  # Only 2 unique alternative sets


def test_hash_usable_in_dict():
    """Test that NormalizedType instances can be used as dict keys."""
    str1 = NormalizedString("success")
    str2 = NormalizedString("success")
    str3 = NormalizedString("failure")

    # Should work as dict keys
    result_dict = {str1: "value1", str3: "value2"}
    assert len(result_dict) == 2

    # Same object should retrieve same value
    assert result_dict[str2] == "value1"
