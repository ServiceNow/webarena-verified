"""Playwright UI tests for Wikipedia Docker container.

Tests the kiwix-serve Wikipedia functionality using browser automation.
Works with both the full Wikipedia ZIM and the small Ray Charles CI ZIM.

Usage:
    pytest tests/integration/environments/wikipedia/test_playwright.py
    pytest tests/integration/environments/wikipedia/test_playwright.py --playwright-timeout-sec=60
"""

import pytest

pytestmark = [pytest.mark.docker, pytest.mark.integration_docker_wikipedia]


@pytest.mark.flaky(reruns=2)
def test_wikipedia_landing_loads(wikipedia_container, wikipedia_base_url, page, pw_timeout):
    """Test that Wikipedia/Kiwix landing page loads."""
    page.goto(wikipedia_base_url, timeout=pw_timeout)

    # Verify we're on the kiwix landing page (works with any ZIM)
    content = page.content().lower()
    assert "kiwix" in content or "wikipedia" in content or "ray charles" in content


@pytest.mark.flaky(reruns=2)
def test_wikipedia_article_accessible(wikipedia_container, wikipedia_base_url, page, pw_timeout):
    """Test that we can access article content."""
    page.goto(wikipedia_base_url, timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Should have some content loaded
    content = page.content()
    assert len(content) > 100, "Page should have content"


@pytest.mark.flaky(reruns=2)
def test_wikipedia_search_interface(wikipedia_container, wikipedia_base_url, page, pw_timeout):
    """Test that the search interface exists."""
    page.goto(wikipedia_base_url, timeout=pw_timeout)

    # Look for search input - kiwix reader has a search box
    search_input = page.get_by_role("textbox", name="Search")

    # Verify search input exists
    assert search_input.is_visible(timeout=5000), "Search input should be visible"


@pytest.mark.flaky(reruns=2)
def test_wikipedia_search_returns_results(wikipedia_container, wikipedia_base_url, page, pw_timeout):
    """Test that searching returns results (uses Ray Charles - exists in all ZIMs)."""
    page.goto(wikipedia_base_url, timeout=pw_timeout)

    # Find and use search input
    search_input = page.get_by_role("textbox", name="Search")
    assert search_input.is_visible(timeout=5000), "Search input should be visible"

    search_input.fill("Ray Charles")
    search_input.press("Enter")

    # Wait for results
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Should show Ray Charles content
    content = page.content().lower()
    assert "ray" in content or "charles" in content, "Search should show Ray Charles content"
