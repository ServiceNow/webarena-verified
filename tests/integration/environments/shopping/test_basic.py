"""Basic HTTP health tests for Shopping Docker container.

Tests basic connectivity to the Magento storefront without requiring Playwright.

Usage:
    pytest tests/integration/environments/shopping/test_basic.py
"""

import urllib.request

import pytest

pytestmark = [pytest.mark.docker, pytest.mark.integration_docker_shopping]

# Known URLs in the shopping dataset (One Stop Market)
TEST_PRODUCT_URL = "toothbrush-head-cover-toothbrush-protective-case-toothbrush-head-cap-for-home-travel-camping-lightweight-safe-protecting-toothbrush-head-light-blue.html"
TEST_CATEGORY_URL = "beauty-personal-care.html"


@pytest.mark.flaky(reruns=2)
def test_shopping_homepage_responds(shopping_container, shopping_base_url):
    """Test that homepage responds with 200."""
    req = urllib.request.Request(shopping_base_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200


@pytest.mark.flaky(reruns=2)
def test_shopping_product_page_responds(shopping_container, shopping_base_url):
    """Test that a product page responds."""
    product_url = f"{shopping_base_url}/{TEST_PRODUCT_URL}"
    req = urllib.request.Request(product_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200


@pytest.mark.flaky(reruns=2)
def test_shopping_category_page_responds(shopping_container, shopping_base_url):
    """Test that a category page responds."""
    category_url = f"{shopping_base_url}/{TEST_CATEGORY_URL}"
    req = urllib.request.Request(category_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200
