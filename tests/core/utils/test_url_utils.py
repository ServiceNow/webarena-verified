"""Unit tests for URL utility functions."""

import base64
from types import MappingProxyType

import pytest

from webarena_verified.core.utils.url_utils import extract_base64_query, normalize_query


@pytest.mark.parametrize(
    "path, expected_path, expected_queries",
    [
        # Happy path - valid base64 in middle
        (
            "/api/dXNlcj1hZG1pbiZwYXNzPTEyMw/data",
            "/api/data",
            ["user=admin&pass=123"],
        ),
        # Happy path - valid base64 at end
        (
            "/api/dXNlcj1hZG1pbiZwYXNzPTEyMw",
            "/api",
            ["user=admin&pass=123"],
        ),
        # Happy path - valid base64 at start
        (
            "/dXNlcj1hZG1pbg/api/data",
            "/api/data",
            ["user=admin"],
        ),
        # Happy path - multiple base64 segments
        (
            "/api/dXNlcj1hZG1pbg/data/cGFzcz0xMjM",
            "/api/data",
            ["user=admin", "pass=123"],
        ),
        # Happy path - base64 with URL-safe characters (- and _)
        (
            f"/api/{base64.urlsafe_b64encode(b'key=value-with_special').decode()}/data",
            "/api/data",
            ["key=value-with_special"],
        ),
        # Happy path - preserve leading slash
        (
            "/dXNlcj1hZG1pbg",
            "/",
            ["user=admin"],
        ),
        # Happy path - preserve trailing slash
        (
            "/api/dXNlcj1hZG1pbg/",
            "/api/",
            ["user=admin"],
        ),
        # Corner case - empty path
        ("", "", []),
        # Corner case - path with no base64
        ("/api/data", "/api/data", []),
        # Corner case - base64 segment too short (< 4 chars)
        ("/api/abc/data", "/api/abc/data", []),
        # Corner case - valid base64 but not a query string (no '=')
        (
            f"/api/{base64.urlsafe_b64encode(b'notaquery').decode()}/data",
            f"/api/{base64.urlsafe_b64encode(b'notaquery').decode()}/data",
            [],
        ),
        # Corner case - segment looks like base64 but isn't valid
        ("/api/notbase64segment/data", "/api/notbase64segment/data", []),
        # Corner case - segment with special chars (not base64)
        ("/api/segment@with#special$/data", "/api/segment@with#special$/data", []),
        # Corner case - all segments are base64
        (
            f"/{base64.urlsafe_b64encode(b'a=1').decode()}/{base64.urlsafe_b64encode(b'b=2').decode()}",
            "/",
            ["a=1", "b=2"],
        ),
        # Corner case - base64 with padding
        ("/api/dXNlcj1hZG1pbg==/data", "/api/data", ["user=admin"]),
        # Corner case - query string with leading ?
        (
            f"/api/{base64.urlsafe_b64encode(b'?key=value').decode()}/data",
            "/api/data",
            ["key=value"],
        ),
        # Corner case - query string with leading &
        (
            f"/api/{base64.urlsafe_b64encode(b'&key=value').decode()}/data",
            "/api/data",
            ["key=value"],
        ),
    ],
    ids=[
        "base64_in_middle",
        "base64_at_end",
        "base64_at_start",
        "multiple_base64",
        "url_safe_chars",
        "preserve_leading_slash",
        "preserve_trailing_slash",
        "empty_path",
        "no_base64",
        "segment_too_short",
        "not_query_string",
        "invalid_base64",
        "special_chars",
        "all_segments_base64",
        "with_padding",
        "query_leading_question",
        "query_leading_ampersand",
    ],
)
def test_extract_base64_query(path, expected_path, expected_queries):
    """Test base64 query extraction from URL paths."""
    cleaned_path, decoded_queries = extract_base64_query(path)
    assert cleaned_path == expected_path
    assert decoded_queries == expected_queries


@pytest.mark.parametrize(
    "query_string, expected",
    [
        # Happy path - simple single parameter
        ("key=value", MappingProxyType({"key": ("value",)})),
        # Happy path - multiple parameters
        (
            "key1=value1&key2=value2",
            MappingProxyType({"key1": ("value1",), "key2": ("value2",)}),
        ),
        # Happy path - duplicate keys (values should be sorted)
        (
            "tag=python&tag=code&tag=aws",
            MappingProxyType({"tag": ("aws", "code", "python")}),
        ),
        # Happy path - URL-encoded values
        (
            "name=John%20Doe&city=New%20York",
            MappingProxyType({"name": ("John Doe",), "city": ("New York",)}),
        ),
        # Happy path - URL-encoded keys
        (
            "search%5Bquery%5D=test",
            MappingProxyType({"search[query]": ("test",)}),
        ),
        # Happy path - mix of single and multiple values
        (
            "user=admin&tag=a&tag=b&role=editor",
            MappingProxyType({"user": ("admin",), "tag": ("a", "b"), "role": ("editor",)}),
        ),
        # Corner case - empty string
        ("", MappingProxyType({})),
        # Corner case - blank value (key with no value)
        ("key=", MappingProxyType({"key": ("",)})),
        # Corner case - multiple blank values
        ("key=&key=", MappingProxyType({"key": ("", "")})),
        # Corner case - parameter with only key (no =)
        ("key", MappingProxyType({"key": ("",)})),
        # Corner case - special characters in values
        (
            "special=hello%21%40%23",
            MappingProxyType({"special": ("hello!@#",)}),
        ),
        # Corner case - numeric values
        ("count=42&page=1", MappingProxyType({"count": ("42",), "page": ("1",)})),
        # Corner case - values with equals signs
        (
            "equation=a%3Db%2Bc",
            MappingProxyType({"equation": ("a=b+c",)}),
        ),
        # Corner case - multiple parameters with same value
        (
            "a=same&b=same&c=same",
            MappingProxyType({"a": ("same",), "b": ("same",), "c": ("same",)}),
        ),
        # Corner case - parameter names need sorting (duplicate with diff values)
        (
            "key=z&key=a&key=m",
            MappingProxyType({"key": ("a", "m", "z")}),
        ),
        # Corner case - whitespace in values (URL encoded)
        (
            "text=hello+world",
            MappingProxyType({"text": ("hello world",)}),
        ),
    ],
    ids=[
        "single_param",
        "multiple_params",
        "duplicate_keys_sorted",
        "url_encoded_values",
        "url_encoded_keys",
        "mixed_single_and_multi",
        "empty_string",
        "blank_value",
        "multiple_blank_values",
        "key_only",
        "special_chars",
        "numeric_values",
        "value_with_equals",
        "same_values_diff_keys",
        "duplicate_keys_diff_values",
        "whitespace_plus_encoding",
    ],
)
def test_normalize_query(query_string, expected):
    """Test query string normalization to QueryParams format."""
    result = normalize_query(query_string)
    assert result == expected
    assert isinstance(result, MappingProxyType)
    # Verify all values are tuples
    for _key, values in result.items():
        assert isinstance(values, tuple)
