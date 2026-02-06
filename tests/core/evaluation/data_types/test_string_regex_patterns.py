"""Unit tests for NormalizedString regex pattern matching."""

import pytest

from webarena_verified.core.evaluation.data_types import NormalizedString
from webarena_verified.core.utils import is_regexp


# Pattern detection tests
@pytest.mark.parametrize(
    "value,is_pattern",
    [
        ("^success$", True),
        ("^test.*$", True),
        ("^$", True),  # Empty pattern
        ("success", False),  # No anchors
        ("^success", False),  # Only start anchor
        ("success$", False),  # Only end anchor
        ("", False),  # Empty string
        ("^", False),  # Only ^
        ("$", False),  # Only $
    ],
)
def test_is_pattern_detection(value, is_pattern):
    """Test that is_regexp correctly identifies regex patterns."""
    assert is_regexp(value) == is_pattern


# Basic pattern matching tests
@pytest.mark.parametrize(
    "pattern,test_string,should_match",
    [
        # Exact matches
        ("^success$", "success", True),
        ("^success$", "failure", False),
        # Case sensitivity (patterns are normalized to lowercase)
        ("^success$", "SUCCESS", True),  # NormalizedString lowercases both
        # Wildcards
        ("^success.*$", "success", True),
        ("^success.*$", "success: done", True),
        ("^success.*$", "failure", False),
        # Character classes
        ("^[0-9]+$", "123", True),
        ("^[0-9]+$", "abc", False),
        # Word boundaries
        ("^test$", "test", True),
        ("^test$", "testing", False),
        # Optional characters
        ("^colou?r$", "color", True),
        ("^colou?r$", "colour", True),
    ],
)
def test_pattern_matches_string(pattern, test_string, should_match):
    """Test that patterns match strings correctly."""
    pattern_obj = NormalizedString(pattern)
    string_obj = NormalizedString(test_string)

    if should_match:
        assert pattern_obj == string_obj
        assert string_obj == pattern_obj  # Symmetric
    else:
        assert pattern_obj != string_obj
        assert string_obj != pattern_obj  # Symmetric


# Pattern with alternatives tests
def test_pattern_matches_any_alternative():
    """Test that pattern matches if ANY alternative matches."""
    pattern = NormalizedString("^success$")
    alternatives = NormalizedString(["success", "failure", "error"])

    # Should match because "success" is in alternatives
    assert pattern == alternatives
    assert alternatives == pattern


def test_pattern_no_match_with_alternatives():
    """Test that pattern doesn't match if NO alternative matches."""
    pattern = NormalizedString("^success$")
    alternatives = NormalizedString(["failure", "error"])

    assert pattern != alternatives
    assert alternatives != pattern


def test_wildcard_pattern_matches_multiple_alternatives():
    """Test wildcard patterns against multiple alternatives."""
    pattern = NormalizedString("^success.*$")
    alternatives = NormalizedString(["success: done", "failure", "success: ok"])

    # Should match because "success: done" and "success: ok" match
    assert pattern == alternatives
    assert alternatives == pattern


# Complex pattern tests
@pytest.mark.parametrize(
    "pattern,test_string,should_match",
    [
        # Phone number patterns
        ("^\\d{3}-\\d{4}$", "123-4567", True),
        ("^\\d{3}-\\d{4}$", "123-456", False),
        # Email-like patterns
        ("^\\w+@\\w+\\.com$", "user@example.com", True),
        ("^\\w+@\\w+\\.com$", "user@example", False),
        # Version patterns
        ("^v\\d+\\.\\d+\\.\\d+$", "v1.2.3", True),
        ("^v\\d+\\.\\d+\\.\\d+$", "v1.2", False),
        # URL paths
        ("^/api/v\\d+/.*$", "/api/v1/users", True),
        ("^/api/v\\d+/.*$", "/api/users", False),
    ],
)
def test_complex_patterns(pattern, test_string, should_match):
    """Test complex real-world regex patterns."""
    pattern_obj = NormalizedString(pattern)
    string_obj = NormalizedString(test_string)

    if should_match:
        assert pattern_obj == string_obj
    else:
        assert pattern_obj != string_obj


# Invalid pattern tests
def test_invalid_regex_pattern_falls_back_to_standard_comparison():
    """Test that invalid regex patterns fall back to standard string comparison."""
    # Invalid regex (unmatched bracket)
    invalid_pattern = NormalizedString("^[invalid(")
    test_string = NormalizedString("^[invalid(")

    # Should match via standard comparison (both are same string)
    assert invalid_pattern == test_string


# Non-pattern string tests (ensure backward compatibility)
def test_non_pattern_strings_work_as_before():
    """Test that strings without pattern markers work normally."""
    str1 = NormalizedString("success")
    str2 = NormalizedString("success")
    str3 = NormalizedString("failure")

    assert str1 == str2
    assert str1 != str3


def test_prefix_suffix_stripping_still_works():
    """Test that existing prefix/suffix stripping logic still works."""
    str1 = NormalizedString("'success'")
    str2 = NormalizedString("success")

    # Should match after prefix/suffix stripping
    assert str1 == str2


# Edge cases
def test_pattern_with_only_anchors():
    """Test pattern that is just anchors (matches empty string)."""
    pattern = NormalizedString("^$")
    empty = NormalizedString("")

    assert pattern == empty


def test_pattern_does_not_match_partial_string():
    """Test that patterns require full match (fullmatch behavior)."""
    pattern = NormalizedString("^success$")
    partial = NormalizedString("success!")

    assert pattern != partial


def test_multiple_patterns_not_supported():
    """Test that having multiple patterns as alternatives is not the intended use case.

    This test documents current behavior - patterns are OR'd together.
    """
    # This creates a NormalizedString with two patterns as alternatives
    # Both will be checked independently
    patterns = NormalizedString(["^success$", "^ok$"])
    test_success = NormalizedString("success")
    test_ok = NormalizedString("ok")
    test_failure = NormalizedString("failure")

    # Should match "success" because first pattern matches
    assert patterns == test_success
    # Should match "ok" because second pattern matches
    assert patterns == test_ok
    # Should not match "failure"
    assert patterns != test_failure


# Integration with existing functionality
def test_pattern_matching_with_standard_comparison():
    """Test that pattern matching doesn't break standard comparison."""
    # First pattern, then standard match
    pattern = NormalizedString("^test$")
    exact = NormalizedString("test")
    different = NormalizedString("testing")

    assert pattern == exact
    assert pattern != different


def test_case_insensitive_pattern_matching():
    """Test case-insensitive pattern matching (via normalization)."""
    # Patterns are normalized (lowercased) before compilation
    pattern = NormalizedString("^SUCCESS$")  # Will be normalized to "^success$"
    test_upper = NormalizedString("SUCCESS")  # Will be normalized to "success"
    test_lower = NormalizedString("success")  # Already lowercase

    # Both should match because normalization lowercases everything
    assert pattern == test_upper
    assert pattern == test_lower


def test_pattern_matching_preserves_normalization():
    """Test that string normalization (lowercase, strip) is applied before pattern matching."""
    pattern = NormalizedString("^success$")
    with_whitespace = NormalizedString("  SUCCESS  ")  # Will be normalized to "success"

    # Should match because normalization strips and lowercases
    assert pattern == with_whitespace
