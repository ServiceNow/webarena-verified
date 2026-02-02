"""Basic HTTP health tests for Shopping Admin Docker container.

Tests basic connectivity to the Magento admin panel without requiring Playwright.

Usage:
    pytest tests/integration/environments/shopping_admin/test_basic.py
"""

import urllib.request

import pytest


@pytest.mark.integration_docker_shopping_admin
@pytest.mark.flaky(reruns=2)
def test_homepage_responds(shopping_admin_container, shopping_admin_base_url):
    """Test that homepage responds with 200."""
    req = urllib.request.Request(shopping_admin_base_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200


@pytest.mark.integration_docker_shopping_admin
@pytest.mark.flaky(reruns=2)
def test_admin_panel_accessible(shopping_admin_container, shopping_admin_base_url):
    """Test that admin panel is accessible."""
    admin_url = f"{shopping_admin_base_url}/admin"
    req = urllib.request.Request(admin_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        # Admin panel may redirect to login, but should respond
        assert response.status == 200
