"""Playwright UI tests for Wikipedia Docker container.

Tests the kiwix-serve Wikipedia functionality using browser automation.

Test categories:
- Wikipedia Content: Verify Wikipedia articles are accessible
- Search: Search functionality via the kiwix-serve interface

Usage:
    pytest tests/integration/environments/wikipedia/test_playwright.py
    pytest tests/integration/environments/wikipedia/test_playwright.py --playwright-timeout-sec=60
"""

import pytest

pytestmark = [pytest.mark.docker, pytest.mark.integration_docker_wikipedia]

# Wikipedia Content Tests


@pytest.mark.flaky(reruns=2)
def test_wikipedia_landing_loads(wikipedia_container, wikipedia_base_url, page, pw_timeout):
    """Test that Wikipedia landing page loads with expected content (auto-redirects)."""
    page.goto(wikipedia_base_url, timeout=pw_timeout)

    # Verify we're on the Wikipedia landing page
    assert "Wikipedia" in page.content()
    assert "free encyclopedia" in page.content().lower()

    # Verify article count is displayed (6+ million articles)
    content = page.content()
    assert "articles" in content.lower()


@pytest.mark.flaky(reruns=2)
def test_wikipedia_article_navigation(wikipedia_container, wikipedia_base_url, page, pw_timeout):
    """Test that we can navigate to a Wikipedia article."""
    # Navigate to a well-known article (Python programming language)
    article_url = f"{wikipedia_base_url}/wikipedia_en_all_maxi_2022-05/A/Python_(programming_language)"
    page.goto(article_url, timeout=pw_timeout)

    # Verify article content loaded
    content = page.content().lower()
    assert "python" in content
    assert "programming" in content or "language" in content


# Search Tests


@pytest.mark.flaky(reruns=2)
def test_wikipedia_search_interface(wikipedia_container, wikipedia_base_url, page, pw_timeout):
    """Test that the search interface exists on Wikipedia pages."""
    page.goto(wikipedia_base_url, timeout=pw_timeout)

    # Look for search input - kiwix reader has a search box with placeholder containing "Search"
    search_input = page.get_by_role("textbox", name="Search")

    # Verify search input exists
    assert search_input.is_visible(timeout=5000), "Search input should be visible"


@pytest.mark.flaky(reruns=2)
def test_wikipedia_search_returns_results(wikipedia_container, wikipedia_base_url, page, pw_timeout):
    """Test that searching for a term returns results."""
    page.goto(wikipedia_base_url, timeout=pw_timeout)

    # Find and use search input
    search_input = page.get_by_role("textbox", name="Search")

    if search_input.is_visible(timeout=5000):
        search_input.fill("Einstein")
        search_input.press("Enter")

        # Wait for results
        page.wait_for_load_state("networkidle", timeout=pw_timeout)

        # Should navigate to search results or article
        content = page.content().lower()
        assert "einstein" in content, "Search should show Einstein-related content"
