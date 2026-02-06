"""Unit tests for Base64String data type."""

import base64

import pytest

from webarena_verified.core.evaluation.data_types import Base64String

# ===== Basic Functionality Tests =====


@pytest.mark.parametrize(
    "base64_value,expected_decoded",
    [
        # Simple ASCII text
        ("SGVsbG8gV29ybGQ=", "Hello World"),
        ("dGVzdA==", "test"),
        # Text with spaces
        ("SGVsbG8gV29ybGQh", "Hello World!"),
        # Multiline text
        ("TGluZSAxCkxpbmUgMg==", "Line 1\nLine 2"),
        # Empty base64 decodes to empty (but we strip it)
        # License text examples
        (base64.b64encode(b"MIT License").decode(), "MIT License"),
        (base64.b64encode(b"Apache License 2.0").decode(), "Apache License 2.0"),
    ],
)
def test_base64_decoding_basic(base64_value, expected_decoded):
    """Test that base64 strings are decoded correctly."""
    b64 = Base64String(base64_value)
    assert b64.normalized == expected_decoded
    assert isinstance(b64.normalized, str)


# ===== Line Ending Normalization Tests =====


@pytest.mark.parametrize(
    "content,expected_normalized",
    [
        # Windows line endings
        ("Line 1\r\nLine 2", "Line 1\nLine 2"),
        # Mac line endings
        ("Line 1\rLine 2", "Line 1\nLine 2"),
        # Unix line endings (no change)
        ("Line 1\nLine 2", "Line 1\nLine 2"),
        # Mixed line endings
        ("Line 1\r\nLine 2\rLine 3\nLine 4", "Line 1\nLine 2\nLine 3\nLine 4"),
        # Leading/trailing whitespace is stripped
        ("  Content  ", "Content"),
        ("\n\nContent\n\n", "Content"),
    ],
)
def test_line_ending_normalization(content, expected_normalized):
    """Test that line endings are normalized correctly."""
    base64_value = base64.b64encode(content.encode()).decode()
    b64 = Base64String(base64_value)
    assert b64.normalized == expected_normalized


# ===== Regex Pattern Tests =====


@pytest.mark.parametrize(
    "pattern,base64_content,should_match",
    [
        # Pattern matches decoded content
        ("^.*MIT License.*$", base64.b64encode(b"MIT License").decode(), True),
        ("^.*MIT License.*$", base64.b64encode(b"Apache License").decode(), False),
        # Pattern with multiline content (DOTALL flag)
        ("^.*MIT License.*$", base64.b64encode(b"Line 1\nMIT License\nLine 3").decode(), True),
        # Pattern for specific text
        ("^Hello World$", base64.b64encode(b"Hello World").decode(), True),
        ("^Hello World$", base64.b64encode(b"Hello World!").decode(), False),
        # Pattern with special characters
        ("^.*Apache License 2\\.0.*$", base64.b64encode(b"Apache License 2.0").decode(), True),
    ],
)
def test_regex_pattern_matching(pattern, base64_content, should_match):
    """Test that regex patterns match decoded content, not base64 string."""
    pattern_b64 = Base64String(pattern)  # Pattern is preserved as-is
    content_b64 = Base64String(base64_content)  # Content is decoded

    if should_match:
        assert pattern_b64 == content_b64
        assert content_b64 == pattern_b64  # Symmetric
    else:
        assert pattern_b64 != content_b64
        assert content_b64 != pattern_b64  # Symmetric


def test_regex_pattern_preserved():
    """Test that regex patterns are preserved and not decoded."""
    pattern = "^.*MIT License.*$"
    b64 = Base64String(pattern)
    # Pattern should be preserved as-is (not decoded)
    assert b64.normalized == pattern.strip()


def test_regex_with_dotall_flag():
    """Test that regex patterns use DOTALL flag for multiline content."""
    # Create multiline content with MIT License in the middle
    content = """
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights

MIT License

to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software.
"""
    base64_content = base64.b64encode(content.encode()).decode()

    pattern_b64 = Base64String("^.*MIT License.*$")
    content_b64 = Base64String(base64_content)

    # Pattern should match multiline content (with DOTALL flag)
    assert pattern_b64 == content_b64


# ===== Equality Tests =====


@pytest.mark.parametrize(
    "value1,value2",
    [
        # Same decoded content
        (
            base64.b64encode(b"Hello").decode(),
            base64.b64encode(b"Hello").decode(),
        ),
        # Different line endings normalize to same
        (
            base64.b64encode(b"Line 1\r\nLine 2").decode(),
            base64.b64encode(b"Line 1\nLine 2").decode(),
        ),
    ],
)
def test_equality_same_content(value1, value2):
    """Test that same decoded content is equal."""
    b64_1 = Base64String(value1)
    b64_2 = Base64String(value2)
    assert b64_1 == b64_2
    assert b64_2 == b64_1  # Symmetric


@pytest.mark.parametrize(
    "value1,value2",
    [
        # Different content
        (
            base64.b64encode(b"Hello").decode(),
            base64.b64encode(b"World").decode(),
        ),
        (
            base64.b64encode(b"MIT License").decode(),
            base64.b64encode(b"Apache License").decode(),
        ),
    ],
)
def test_inequality(value1, value2):
    """Test that different decoded content is not equal."""
    b64_1 = Base64String(value1)
    b64_2 = Base64String(value2)
    assert b64_1 != b64_2
    assert b64_2 != b64_1  # Symmetric


# ===== Case Sensitivity Tests =====


def test_case_sensitivity_in_decoded_content():
    """Test that decoded content is case-sensitive (no lowercasing)."""
    b64_upper = Base64String(base64.b64encode(b"MIT LICENSE").decode())
    b64_lower = Base64String(base64.b64encode(b"mit license").decode())
    b64_mixed = Base64String(base64.b64encode(b"MIT License").decode())

    # All should be different (case-sensitive)
    assert b64_upper != b64_lower
    assert b64_upper != b64_mixed
    assert b64_lower != b64_mixed


# ===== Alternatives Support Tests =====


@pytest.mark.parametrize(
    "values,expected_count",
    [
        # 2 alternatives with different content
        (
            [base64.b64encode(b"MIT").decode(), base64.b64encode(b"Apache").decode()],
            2,
        ),
        # 3+ alternatives
        (
            [
                base64.b64encode(b"License 1").decode(),
                base64.b64encode(b"License 2").decode(),
                base64.b64encode(b"License 3").decode(),
            ],
            3,
        ),
    ],
)
def test_alternatives_support(values, expected_count):
    """Test that alternatives work correctly."""
    b64 = Base64String(values)
    assert len(b64.alternatives) == expected_count


def test_alternatives_equality_with_overlap():
    """Test that equality works when alternatives overlap."""
    # Expected with alternatives
    expected = Base64String(
        [
            base64.b64encode(b"MIT License").decode(),
            base64.b64encode(b"Apache License").decode(),
        ]
    )
    # Actual matches first alternative
    actual = Base64String(base64.b64encode(b"MIT License").decode())
    assert expected == actual
    assert actual == expected  # Symmetric


def test_alternatives_equality_with_second_alternative():
    """Test that equality works when matching second alternative."""
    expected = Base64String(
        [
            base64.b64encode(b"License A").decode(),
            base64.b64encode(b"License B").decode(),
        ]
    )
    actual = Base64String(base64.b64encode(b"License B").decode())
    assert expected == actual
    assert actual == expected  # Symmetric


def test_alternatives_no_overlap():
    """Test that values with no overlapping alternatives don't match."""
    expected = Base64String(
        [
            base64.b64encode(b"License A").decode(),
            base64.b64encode(b"License B").decode(),
        ]
    )
    actual = Base64String(base64.b64encode(b"License C").decode())
    assert expected != actual
    assert actual != expected  # Symmetric


# ===== Error Handling Tests =====


def test_empty_string_raises_error():
    """Test that empty strings raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        Base64String("")

    error_msg = str(exc_info.value).lower()
    assert "empty" in error_msg


def test_whitespace_only_raises_error():
    """Test that whitespace-only strings raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        Base64String("   ")

    # Whitespace is stripped, resulting in empty string
    error_msg = str(exc_info.value).lower()
    assert "empty" in error_msg or "invalid base64" in error_msg


def test_invalid_base64_raises_error():
    """Test that invalid base64 strings raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        Base64String("not-valid-base64!!!")

    error_msg = str(exc_info.value).lower()
    assert "invalid base64" in error_msg


def test_none_value_raises_error():
    """Test that None raises ValueError about type."""
    with pytest.raises(ValueError) as exc_info:
        Base64String(None)

    error_msg = str(exc_info.value).lower()
    assert "only accepts string input" in error_msg


def test_single_item_list_raises_error():
    """Test that single-item list raises ValueError (alternatives require 2+)."""
    with pytest.raises(ValueError) as exc_info:
        Base64String([base64.b64encode(b"Test").decode()])

    error_msg = str(exc_info.value)
    assert "Alternatives require 2+ items" in error_msg


def test_empty_list_raises_error():
    """Test that empty list raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        Base64String([])

    error_msg = str(exc_info.value).lower()
    assert "alternatives require 2+ items" in error_msg


@pytest.mark.parametrize(
    "invalid_type",
    [
        123,
        45.67,
        True,
        False,
        {"a": 1},
        [1, 2, 3],
    ],
)
def test_invalid_type_raises_error(invalid_type):
    """Test that non-string types raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        Base64String(invalid_type)

    error_msg = str(exc_info.value).lower()
    assert "only accepts string input" in error_msg


# ===== Hash and Set/Dict Usage Tests =====


def test_hash_single_value():
    """Test that single values hash correctly."""
    b64_1 = Base64String(base64.b64encode(b"Test").decode())
    b64_2 = Base64String(base64.b64encode(b"Test").decode())
    # Should have same hash since they're equal
    assert b64_1 == b64_2
    assert hash(b64_1) == hash(b64_2)


def test_hash_alternatives():
    """Test that alternatives hash consistently."""
    values = [
        base64.b64encode(b"License 1").decode(),
        base64.b64encode(b"License 2").decode(),
    ]
    b64_1 = Base64String(values)
    b64_2 = Base64String(values)
    assert hash(b64_1) == hash(b64_2)


def test_hash_usable_in_set():
    """Test that Base64String instances can be used in sets."""
    b64_1 = Base64String(base64.b64encode(b"Test").decode())
    b64_2 = Base64String(base64.b64encode(b"Test").decode())  # Same content
    b64_3 = Base64String(base64.b64encode(b"Different").decode())

    b64_set = {b64_1, b64_2, b64_3}
    assert len(b64_set) == 2  # b64_1 and b64_2 are equal, so only 2 unique


def test_hash_usable_in_dict():
    """Test that Base64String instances can be used as dict keys."""
    b64_1 = Base64String(base64.b64encode(b"Test").decode())
    b64_2 = Base64String(base64.b64encode(b"Test").decode())  # Same content
    b64_3 = Base64String(base64.b64encode(b"Different").decode())

    result_dict = {b64_1: "value1", b64_3: "value2"}
    assert len(result_dict) == 2

    # Same content should retrieve same value
    assert result_dict[b64_2] == "value1"


# ===== Unicode and Special Characters Tests =====


def test_unicode_characters():
    """Test handling of Unicode characters in base64 content."""
    content = "Hello 世界 🎉"
    base64_value = base64.b64encode(content.encode()).decode()
    b64 = Base64String(base64_value)
    # Should preserve Unicode
    assert "世界" in b64.normalized
    assert "🎉" in b64.normalized


def test_special_characters():
    """Test handling of special characters in base64 content."""
    content = "Special chars: !@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    base64_value = base64.b64encode(content.encode()).decode()
    b64 = Base64String(base64_value)
    # Should preserve all special characters
    assert b64.normalized == content.strip()


# ===== Real-World GitLab LICENSE Example =====


def test_gitlab_license_change_scenario():
    """Test real-world GitLab LICENSE change scenario from Template 355.

    GitLab sends file content as base64 in POST request body.
    Task uses regex pattern to validate the decoded license text.
    """
    # MIT License content (simplified)
    mit_license_text = """MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction."""

    # Encode as base64 (as GitLab would send it)
    base64_content = base64.b64encode(mit_license_text.encode()).decode()

    # Pattern to match MIT License (from task config)
    pattern = "^.*MIT License.*$"

    # Create Base64String instances
    pattern_b64 = Base64String(pattern)
    content_b64 = Base64String(base64_content)

    # Pattern should match decoded content (not base64 string)
    assert pattern_b64 == content_b64
    assert content_b64 == pattern_b64  # Symmetric


def test_apache_license_change_scenario():
    """Test Apache License change scenario."""
    # Apache License content (simplified)
    apache_license_text = """Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION"""

    # Encode as base64
    base64_content = base64.b64encode(apache_license_text.encode()).decode()

    # Pattern to match Apache License
    pattern = "^.*Apache License.*$"

    pattern_b64 = Base64String(pattern)
    content_b64 = Base64String(base64_content)

    assert pattern_b64 == content_b64


def test_copyleft_license_scenario():
    """Test copyleft license scenario."""
    # GPL License content (simplified)
    gpl_license_text = """GNU GENERAL PUBLIC LICENSE
Version 3, 29 June 2007

This is a copyleft license."""

    # Encode as base64
    base64_content = base64.b64encode(gpl_license_text.encode()).decode()

    # Pattern to match copyleft
    pattern = "^.*copyleft.*$"

    pattern_b64 = Base64String(pattern)
    content_b64 = Base64String(base64_content)

    assert pattern_b64 == content_b64


# ===== Equality Properties Tests =====


def test_equality_reflexivity():
    """Test that equality is reflexive: A == A."""
    b64 = Base64String(base64.b64encode(b"Test").decode())
    assert b64 == b64


@pytest.mark.parametrize(
    "value1,value2",
    [
        # Same base64 encoding
        (
            base64.b64encode(b"Test").decode(),
            base64.b64encode(b"Test").decode(),
        ),
        # Different line endings normalize to same
        (
            base64.b64encode(b"Line 1\r\nLine 2").decode(),
            base64.b64encode(b"Line 1\nLine 2").decode(),
        ),
    ],
)
def test_equality_symmetry(value1, value2):
    """Test that equality is symmetric: A == B implies B == A."""
    b64_1 = Base64String(value1)
    b64_2 = Base64String(value2)
    assert b64_1 == b64_2
    assert b64_2 == b64_1


def test_equality_transitivity():
    """Test that equality is transitive: if A == B and B == C, then A == C."""
    # All encode to same content (with different line endings)
    b64_1 = Base64String(base64.b64encode(b"Line 1\nLine 2").decode())
    b64_2 = Base64String(base64.b64encode(b"Line 1\rLine 2").decode())
    b64_3 = Base64String(base64.b64encode(b"Line 1\r\nLine 2").decode())

    assert b64_1 == b64_2
    assert b64_2 == b64_3
    assert b64_1 == b64_3


# ===== No Normalization Tests =====


def test_no_unicode_normalization():
    """Test that Unicode normalization is NOT applied (unlike NormalizedString)."""
    # Content with special Unicode characters
    content = "café"  # é is U+00E9
    base64_value = base64.b64encode(content.encode()).decode()
    b64 = Base64String(base64_value)

    # Should preserve exact Unicode (no NFKC normalization)
    assert b64.normalized == "café"


def test_no_lowercasing():
    """Test that lowercasing is NOT applied (unlike NormalizedString)."""
    content = "MIT LICENSE"
    base64_value = base64.b64encode(content.encode()).decode()
    b64 = Base64String(base64_value)

    # Should preserve case
    assert b64.normalized == "MIT LICENSE"
    assert b64.normalized != "mit license"


def test_no_aggressive_whitespace_normalization():
    """Test that aggressive whitespace normalization is NOT applied.

    Only line ending normalization and strip() are applied.
    """
    # Content with multiple spaces (should be preserved)
    content = "Text  with    multiple   spaces"
    base64_value = base64.b64encode(content.encode()).decode()
    b64 = Base64String(base64_value)

    # Should preserve internal whitespace
    assert b64.normalized == content.strip()


# ===== Comparison with NormalizedString =====


def test_different_from_normalized_string():
    """Test that Base64String behaves differently from NormalizedString.

    NormalizedString applies:
    - Unicode normalization (NFKC)
    - Lowercasing
    - Aggressive whitespace normalization

    Base64String does NOT apply these transformations.
    """
    from webarena_verified.core.evaluation.data_types import NormalizedString

    # Content with uppercase and special chars
    content = "MIT LICENSE"
    base64_value = base64.b64encode(content.encode()).decode()

    # Base64String preserves case
    b64 = Base64String(base64_value)
    assert b64.normalized == "MIT LICENSE"

    # NormalizedString lowercases
    norm_str = NormalizedString(content)
    assert norm_str.normalized == "mit license"

    # They should be different
    assert b64.normalized != norm_str.normalized
