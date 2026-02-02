"""Integration tests for the environment_control dashboard HTML content.

Tests the static HTML content returned by the dashboard endpoint.

Usage:
    pytest tests/integration/environment_control/test_dashboard.py -v
"""

import urllib.request

DASHBOARD_URL = "http://localhost:8877/"


def test_dashboard_returns_html(env_control_container):
    """Test GET / returns HTML with correct content type."""
    with urllib.request.urlopen(DASHBOARD_URL, timeout=5) as response:
        content_type = response.headers.get("Content-Type", "")
        content = response.read().decode("utf-8")

    assert response.status == 200
    assert "text/html" in content_type
    assert "<!DOCTYPE html>" in content


def test_dashboard_shows_environment_name(env_control_container):
    """Test dashboard displays the environment name."""
    with urllib.request.urlopen(DASHBOARD_URL, timeout=5) as response:
        content = response.read().decode("utf-8")

    assert "dummy" in content
    assert "Environment:" in content


def test_dashboard_shows_status_badge(env_control_container):
    """Test dashboard displays status badge."""
    with urllib.request.urlopen(DASHBOARD_URL, timeout=5) as response:
        content = response.read().decode("utf-8")

    assert "status-badge" in content
    assert "Status:" in content


def test_dashboard_has_action_buttons(env_control_container):
    """Test dashboard has all action buttons."""
    with urllib.request.urlopen(DASHBOARD_URL, timeout=5) as response:
        content = response.read().decode("utf-8")

    assert "Initialize" in content
    assert "Start" in content
    assert "Stop" in content
    assert "Restart" in content
    assert "Refresh Status" in content


def test_dashboard_has_console_area(env_control_container):
    """Test dashboard has console output area."""
    with urllib.request.urlopen(DASHBOARD_URL, timeout=5) as response:
        content = response.read().decode("utf-8")

    assert "Console Output" in content
    assert 'id="console"' in content


def test_dashboard_has_javascript(env_control_container):
    """Test dashboard includes required JavaScript functions."""
    with urllib.request.urlopen(DASHBOARD_URL, timeout=5) as response:
        content = response.read().decode("utf-8")

    assert "doAction" in content
    assert "refreshStatus" in content
    assert "<script>" in content


def test_dashboard_shows_ready_when_healthy(env_control_container):
    """Test dashboard shows ready status when services are healthy."""
    with urllib.request.urlopen(DASHBOARD_URL, timeout=5) as response:
        content = response.read().decode("utf-8")

    assert 'class="status-badge ready"' in content or "Ready" in content
