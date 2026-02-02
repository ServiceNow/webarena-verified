"""Basic HTTP health tests for Wikipedia Docker container.

Tests basic connectivity to the kiwix-serve Wikipedia without requiring Playwright.

Usage:
    pytest tests/integration/environments/wikipedia/test_basic.py
"""

import urllib.request

import pytest


@pytest.mark.integration_docker_wikipedia
@pytest.mark.flaky(reruns=2)
def test_wikipedia_homepage_responds(wikipedia_container, wikipedia_base_url):
    """Test that Wikipedia homepage responds with 200 (auto-redirects to landing)."""
    req = urllib.request.Request(wikipedia_base_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200
