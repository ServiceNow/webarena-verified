"""Integration tests for the environment_control dashboard.

Tests the dashboard endpoint returns valid HTML.

Usage:
    pytest tests/integration/environment_control/test_dashboard.py -v
"""

import urllib.request

DASHBOARD_URL = "http://localhost:8877/"


def test_dashboard_returns_html(env_control_container):
    """Test GET / returns HTML dashboard."""
    with urllib.request.urlopen(DASHBOARD_URL, timeout=5) as response:
        content_type = response.headers.get("Content-Type", "")
        content = response.read().decode("utf-8")

    assert response.status == 200
    assert "text/html" in content_type
    assert "<!DOCTYPE html>" in content
    assert "Environment Control" in content
