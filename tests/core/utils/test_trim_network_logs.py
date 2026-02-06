"""Tests for network log trimming utility."""

import json

import pytest

from webarena_verified.core.utils.trim_network_logs import trim_har_file


@pytest.fixture
def sample_har_data():
    """Create sample HAR data for testing."""
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {"url": "http://example.com/page.html", "method": "GET", "headers": []},
                    "response": {"status": 200, "headers": []},
                },
                {
                    "request": {"url": "http://example.com/style.css", "method": "GET", "headers": []},
                    "response": {"status": 200, "headers": []},
                },
                {
                    "request": {"url": "http://example.com/script.js", "method": "GET", "headers": []},
                    "response": {"status": 200, "headers": []},
                },
                {
                    "request": {"url": "http://example.com/api/data", "method": "POST", "headers": []},
                    "response": {"status": 200, "headers": []},
                },
                {
                    "request": {"url": "http://example.com/logo.png", "method": "GET", "headers": []},
                    "response": {"status": 200, "headers": []},
                },
            ],
        }
    }


def test_trim_basic_har_file(tmp_path, sample_har_data):
    """Test basic HAR file trimming."""
    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(sample_har_data, indent=2))

    # Trim the file
    stats = trim_har_file(input_path, output_path)

    # Verify statistics
    assert stats["original_entries"] == 5
    assert stats["trimmed_entries"] == 2  # Only page.html and api/data
    assert stats["removed_entries"] == 3  # CSS, JS, PNG

    # Verify trimmed file content
    trimmed_data = json.loads(output_path.read_text())
    assert len(trimmed_data["log"]["entries"]) == 2

    # Check that only non-static resources remain
    urls = [entry["request"]["url"] for entry in trimmed_data["log"]["entries"]]
    assert "http://example.com/page.html" in urls
    assert "http://example.com/api/data" in urls
    assert "http://example.com/style.css" not in urls
    assert "http://example.com/script.js" not in urls
    assert "http://example.com/logo.png" not in urls


def test_trim_preserves_har_structure(tmp_path):
    """Test that trimming preserves HAR file structure."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Playwright", "version": "1.0"},
            "browser": {"name": "chromium", "version": "90.0"},
            "entries": [
                {
                    "request": {"url": "http://example.com/page.html", "method": "GET", "headers": []},
                    "response": {"status": 200, "headers": []},
                }
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    trim_har_file(input_path, output_path)

    # Verify structure is preserved
    trimmed_data = json.loads(output_path.read_text())
    assert "log" in trimmed_data
    assert trimmed_data["log"]["version"] == "1.2"
    assert trimmed_data["log"]["creator"]["name"] == "Playwright"
    assert trimmed_data["log"]["browser"]["name"] == "chromium"


def test_trim_file_not_found(tmp_path):
    """Test error when input file doesn't exist."""
    input_path = tmp_path / "nonexistent.har"
    output_path = tmp_path / "output.har"

    with pytest.raises(FileNotFoundError):
        trim_har_file(input_path, output_path)


@pytest.mark.parametrize(
    "invalid_data,error_message",
    [
        ({"entries": []}, "missing 'log' field"),
        ({"log": {"version": "1.2"}}, "missing 'log.entries' field"),
    ],
)
def test_trim_invalid_har_format(tmp_path, invalid_data, error_message):
    """Test error with invalid HAR format."""
    input_path = tmp_path / "invalid.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(invalid_data))

    with pytest.raises(ValueError, match=error_message):
        trim_har_file(input_path, output_path)


def test_trim_creates_output_directory(tmp_path):
    """Test that output directory is created if it doesn't exist."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {"url": "http://example.com/page.html", "method": "GET", "headers": []},
                    "response": {"status": 200, "headers": []},
                }
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "nested" / "dir" / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    trim_har_file(input_path, output_path)

    assert output_path.exists()
    assert output_path.parent.exists()


def test_trim_all_entries_skipped(tmp_path):
    """Test when all entries are skipped resources."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {"url": "http://example.com/style.css", "method": "GET", "headers": []},
                    "response": {"status": 200, "headers": []},
                },
                {
                    "request": {"url": "http://example.com/script.js", "method": "GET", "headers": []},
                    "response": {"status": 200, "headers": []},
                },
                {
                    "request": {"url": "http://example.com/logo.png", "method": "GET", "headers": []},
                    "response": {"status": 200, "headers": []},
                },
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    stats = trim_har_file(input_path, output_path)

    assert stats["original_entries"] == 3
    assert stats["trimmed_entries"] == 0
    assert stats["removed_entries"] == 3

    trimmed_data = json.loads(output_path.read_text())
    assert len(trimmed_data["log"]["entries"]) == 0


def test_trim_no_entries_skipped(tmp_path):
    """Test when no entries are skipped."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {"url": "http://example.com/page.html", "method": "GET", "headers": []},
                    "response": {"status": 200, "headers": []},
                },
                {
                    "request": {"url": "http://example.com/api/data", "method": "POST", "headers": []},
                    "response": {"status": 200, "headers": []},
                },
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    stats = trim_har_file(input_path, output_path)

    assert stats["original_entries"] == 2
    assert stats["trimmed_entries"] == 2
    assert stats["removed_entries"] == 0


def test_trim_file_size_reduction(tmp_path):
    """Test that file size is actually reduced."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "url": "http://example.com/page.html",
                        "method": "GET",
                        "headers": [],
                    },
                    "response": {"status": 200, "headers": []},
                },
                # Add multiple static resources to increase size
                *[
                    {
                        "request": {
                            "url": f"http://example.com/script{i}.js",
                            "method": "GET",
                            "headers": [],
                        },
                        "response": {"status": 200, "headers": []},
                    }
                    for i in range(10)
                ],
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    stats = trim_har_file(input_path, output_path)

    # Verify size was reduced
    assert stats["trimmed_size"] < stats["original_size"]
    assert stats["reduction_percent"] > 0
    # Should remove ~90% of entries (10 out of 11)
    assert stats["reduction_percent"] > 50


def test_sanitize_authorization_header(tmp_path):
    """Test that Authorization headers are sanitized."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "url": "http://example.com/api/data",
                        "method": "GET",
                        "headers": [
                            {"name": "Authorization", "value": "Bearer secret-token-12345"},
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                    },
                    "response": {
                        "status": 200,
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                    },
                }
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    stats = trim_har_file(input_path, output_path)

    # Verify sanitization statistics
    assert stats["request_headers_sanitized"] == 1
    assert stats["response_headers_sanitized"] == 0

    # Verify Authorization header was sanitized
    trimmed_data = json.loads(output_path.read_text())
    headers = trimmed_data["log"]["entries"][0]["request"]["headers"]
    auth_header = next(h for h in headers if h["name"] == "Authorization")
    assert auth_header["value"] == "[REDACTED]"

    # Verify other headers are unchanged
    content_type = next(h for h in headers if h["name"] == "Content-Type")
    assert content_type["value"] == "application/json"


def test_sanitize_api_key_headers(tmp_path):
    """Test that API key headers are sanitized."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "url": "http://example.com/api/data",
                        "method": "GET",
                        "headers": [
                            {"name": "X-API-Key", "value": "sk_live_1234567890"},
                            {"name": "X-Auth-Token", "value": "token_abc123"},
                            {"name": "X-API-Secret", "value": "secret_xyz789"},
                        ],
                    },
                    "response": {"status": 200, "headers": []},
                }
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    stats = trim_har_file(input_path, output_path)

    # Verify all API key headers were sanitized
    assert stats["request_headers_sanitized"] == 3

    # Verify all headers were redacted
    trimmed_data = json.loads(output_path.read_text())
    headers = trimmed_data["log"]["entries"][0]["request"]["headers"]
    for header in headers:
        assert header["value"] == "[REDACTED]"


def test_sanitize_pattern_matching_headers(tmp_path):
    """Test that headers with auth/token/key/secret patterns are sanitized."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "url": "http://example.com/api/data",
                        "method": "GET",
                        "headers": [
                            {"name": "X-Custom-Auth", "value": "custom-auth-value"},
                            {"name": "X-Access-Token", "value": "access-token-value"},
                            {"name": "X-Secret-Key", "value": "secret-key-value"},
                            {"name": "X-API-Key-ID", "value": "api-key-id-value"},
                            {"name": "User-Agent", "value": "Mozilla/5.0"},
                        ],
                    },
                    "response": {"status": 200, "headers": []},
                }
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    stats = trim_har_file(input_path, output_path)

    # Verify sensitive headers were sanitized (4 out of 5)
    assert stats["request_headers_sanitized"] == 4

    # Verify specific headers
    trimmed_data = json.loads(output_path.read_text())
    headers = {h["name"]: h["value"] for h in trimmed_data["log"]["entries"][0]["request"]["headers"]}

    # Sensitive headers should be redacted
    assert headers["X-Custom-Auth"] == "[REDACTED]"
    assert headers["X-Access-Token"] == "[REDACTED]"
    assert headers["X-Secret-Key"] == "[REDACTED]"
    assert headers["X-API-Key-ID"] == "[REDACTED]"

    # Non-sensitive header should be preserved
    assert headers["User-Agent"] == "Mozilla/5.0"


def test_preserve_cookie_headers(tmp_path):
    """Test that Cookie and Set-Cookie headers are NOT sanitized."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "url": "http://example.com/api/data",
                        "method": "GET",
                        "headers": [
                            {"name": "Cookie", "value": "session=abc123; user_id=456"},
                            {"name": "Authorization", "value": "Bearer secret-token"},
                        ],
                    },
                    "response": {
                        "status": 200,
                        "headers": [
                            {"name": "Set-Cookie", "value": "session=xyz789; HttpOnly; Secure"},
                            {"name": "X-Auth-Token", "value": "response-token"},
                        ],
                    },
                }
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    stats = trim_har_file(input_path, output_path)

    # Verify only Authorization and X-Auth-Token were sanitized
    assert stats["request_headers_sanitized"] == 1
    assert stats["response_headers_sanitized"] == 1

    # Verify Cookie and Set-Cookie are preserved
    trimmed_data = json.loads(output_path.read_text())
    request_headers = {h["name"]: h["value"] for h in trimmed_data["log"]["entries"][0]["request"]["headers"]}
    response_headers = {h["name"]: h["value"] for h in trimmed_data["log"]["entries"][0]["response"]["headers"]}

    # Cookies should NOT be redacted
    assert request_headers["Cookie"] == "session=abc123; user_id=456"
    assert response_headers["Set-Cookie"] == "session=xyz789; HttpOnly; Secure"

    # Auth headers should be redacted
    assert request_headers["Authorization"] == "[REDACTED]"
    assert response_headers["X-Auth-Token"] == "[REDACTED]"


def test_sanitize_case_insensitive(tmp_path):
    """Test that header sanitization is case-insensitive."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "url": "http://example.com/api/data",
                        "method": "GET",
                        "headers": [
                            {"name": "authorization", "value": "Bearer token1"},
                            {"name": "AUTHORIZATION", "value": "Bearer token2"},
                            {"name": "cookie", "value": "session=abc"},
                            {"name": "COOKIE", "value": "session=xyz"},
                        ],
                    },
                    "response": {"status": 200, "headers": []},
                }
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    stats = trim_har_file(input_path, output_path)

    # Verify both authorization headers were sanitized (2)
    # But cookies were NOT sanitized
    assert stats["request_headers_sanitized"] == 2

    # Verify specific headers
    trimmed_data = json.loads(output_path.read_text())
    headers = {h["name"]: h["value"] for h in trimmed_data["log"]["entries"][0]["request"]["headers"]}

    # Authorization headers (any case) should be redacted
    assert headers["authorization"] == "[REDACTED]"
    assert headers["AUTHORIZATION"] == "[REDACTED]"

    # Cookie headers (any case) should be preserved
    assert headers["cookie"] == "session=abc"
    assert headers["COOKIE"] == "session=xyz"


def test_sanitize_both_request_and_response_headers(tmp_path):
    """Test that both request and response headers are sanitized."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "url": "http://example.com/api/data",
                        "method": "POST",
                        "headers": [
                            {"name": "Authorization", "value": "Bearer request-token"},
                            {"name": "X-API-Key", "value": "request-key"},
                        ],
                    },
                    "response": {
                        "status": 200,
                        "headers": [
                            {"name": "X-Auth-Token", "value": "response-token"},
                            {"name": "X-API-Secret", "value": "response-secret"},
                        ],
                    },
                }
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    stats = trim_har_file(input_path, output_path)

    # Verify both request and response headers were sanitized
    assert stats["request_headers_sanitized"] == 2
    assert stats["response_headers_sanitized"] == 2

    # Verify all headers were redacted
    trimmed_data = json.loads(output_path.read_text())
    entry = trimmed_data["log"]["entries"][0]

    for header in entry["request"]["headers"]:
        assert header["value"] == "[REDACTED]"

    for header in entry["response"]["headers"]:
        assert header["value"] == "[REDACTED]"


def test_sanitize_with_no_sensitive_headers(tmp_path):
    """Test sanitization when no sensitive headers are present."""
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Test", "version": "1.0"},
            "entries": [
                {
                    "request": {
                        "url": "http://example.com/api/data",
                        "method": "GET",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                            {"name": "Accept", "value": "application/json"},
                            {"name": "User-Agent", "value": "Mozilla/5.0"},
                        ],
                    },
                    "response": {
                        "status": 200,
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                    },
                }
            ],
        }
    }

    input_path = tmp_path / "input.har"
    output_path = tmp_path / "output.har"
    input_path.write_text(json.dumps(har_data, indent=2))

    stats = trim_har_file(input_path, output_path)

    # Verify no headers were sanitized
    assert stats["request_headers_sanitized"] == 0
    assert stats["response_headers_sanitized"] == 0

    # Verify all headers remain unchanged
    trimmed_data = json.loads(output_path.read_text())
    entry = trimmed_data["log"]["entries"][0]

    assert entry["request"]["headers"][0]["value"] == "application/json"
    assert entry["request"]["headers"][1]["value"] == "application/json"
    assert entry["request"]["headers"][2]["value"] == "Mozilla/5.0"
    assert entry["response"]["headers"][0]["value"] == "application/json"
