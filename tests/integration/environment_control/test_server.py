"""Integration tests for environment_control server.

Tests the HTTP server running in a Docker container with dummy ops.

Usage:
    pytest tests/integration/environment_control/test_server.py -v
"""

import json
import urllib.error
import urllib.request

import pytest

# --- Server Endpoint Tests ---


def test_status_endpoint(client):
    """Test GET /status returns health info."""
    result = client.status()

    assert "success" in result
    assert "details" in result
    assert "value" in result["details"]
    assert "exec_logs" in result["details"]
    assert result["success"] is True


def test_start_endpoint(client):
    """Test POST /start."""
    result = client.start()

    assert result["success"] is True


def test_start_endpoint_with_wait(client):
    """Test POST /start?wait=1."""
    result = client.start(wait=True)

    assert result["success"] is True


def test_stop_endpoint(client):
    """Test POST /stop."""
    result = client.stop()

    assert result["success"] is True


def test_init_endpoint(client):
    """Test POST /init."""
    result = client.init()

    assert result["success"] is True


# --- Client Utility Tests ---


def test_wait_until_ready(client):
    """Test wait_until_ready returns expected structure."""
    result = client.wait_until_ready(timeout=10, interval=0.5)

    # Result should have success key and message
    assert "success" in result
    assert "message" in result
    # If successful, details should contain value info
    if result["success"]:
        assert "details" in result


# --- Error Response Tests ---


def test_not_found_endpoint(env_control_container):
    """Test 404 response for unknown endpoints."""
    url = "http://localhost:8877/unknown"
    req = urllib.request.Request(url)

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)

    assert exc_info.value.code == 404
    error_data = json.loads(exc_info.value.read().decode("utf-8"))
    assert error_data["success"] is False
