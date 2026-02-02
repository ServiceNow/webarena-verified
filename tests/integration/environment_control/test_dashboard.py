"""Integration tests for the environment_control dashboard.

Tests the dashboard endpoint returns valid HTML.

Usage:
    pytest tests/integration/environment_control/test_dashboard.py -v
"""

import urllib.request

import pytest

pytestmark = pytest.mark.docker


def test_dashboard_returns_html(env_control_container):
    """Test GET / returns HTML dashboard."""
    url = f"{env_control_container.base_url}/"

    with urllib.request.urlopen(url, timeout=5) as response:
        content_type = response.headers.get("Content-Type", "")
        content = response.read().decode("utf-8")

    assert response.status == 200
    assert "text/html" in content_type
    assert "<!DOCTYPE html>" in content
    assert "Environment Control" in content
