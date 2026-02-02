"""Playwright UI tests for OpenStreetMap Docker container.

Tests OpenStreetMap website functionality using browser automation.

Test categories:
- Page Navigation: Basic map viewing
- User Registration: Account creation flow
- Map Interaction: Pan, zoom operations

Usage:
    pytest tests/integration/environments/map/test_playwright.py
    pytest tests/integration/environments/map/test_playwright.py --headed
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.docker, pytest.mark.integration_docker_map]

# =============================================================================
# Page Navigation Tests
# =============================================================================


@pytest.mark.flaky(reruns=2)
def test_map_homepage_loads(map_container, map_base_url, page, pw_timeout):
    """Test that the map homepage loads correctly."""
    page.goto(map_base_url)

    # Wait for the map to be visible
    expect(page.locator("#map")).to_be_visible(timeout=pw_timeout)


@pytest.mark.flaky(reruns=2)
def test_map_login_page_loads(map_container, map_base_url, page, pw_timeout):
    """Test that the login page loads correctly."""
    page.goto(f"{map_base_url}/login")

    # Verify login form is present
    expect(page.get_by_role("heading", name="Log In")).to_be_visible(timeout=pw_timeout)


@pytest.mark.flaky(reruns=2)
def test_map_signup_page_loads(map_container, map_base_url, page, pw_timeout):
    """Test that the signup page loads correctly."""
    page.goto(f"{map_base_url}/user/new")

    # Verify signup form is present
    expect(page.get_by_role("heading", name="Sign Up")).to_be_visible(timeout=pw_timeout)


# =============================================================================
# Map Interaction Tests
# =============================================================================


@pytest.mark.flaky(reruns=2)
def test_map_zoom_controls_visible(map_container, map_base_url, page, pw_timeout):
    """Test that map zoom controls are visible."""
    page.goto(map_base_url)

    # Wait for map to load
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Check zoom controls are present
    expect(page.locator(".leaflet-control-zoom-in")).to_be_visible(timeout=pw_timeout)
    expect(page.locator(".leaflet-control-zoom-out")).to_be_visible(timeout=pw_timeout)


@pytest.mark.flaky(reruns=2)
def test_map_layers_control_visible(map_container, map_base_url, page, pw_timeout):
    """Test that map layers control is visible."""
    page.goto(map_base_url)

    # Wait for map to load
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Check layers control is present
    expect(page.locator(".leaflet-control-layers")).to_be_visible(timeout=pw_timeout)


# =============================================================================
# Search Tests
# =============================================================================


@pytest.mark.flaky(reruns=2)
def test_map_search_box_visible(map_container, map_base_url, page, pw_timeout):
    """Test that the search box is visible on the map page."""
    page.goto(map_base_url)

    # Wait for map to load
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Check search box is present
    search_box = page.locator("input[name='query']")
    expect(search_box).to_be_visible(timeout=pw_timeout)


# =============================================================================
# History/Changeset Tests
# =============================================================================


@pytest.mark.flaky(reruns=2)
def test_map_history_page_loads(map_container, map_base_url, page, pw_timeout):
    """Test that the history/changesets page loads."""
    page.goto(f"{map_base_url}/history")

    # Verify history page loaded
    expect(page.get_by_role("heading", name="Changesets")).to_be_visible(timeout=pw_timeout)
