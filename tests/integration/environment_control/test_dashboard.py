"""Integration tests for the environment_control dashboard.

Tests the dashboard endpoint and interactive behavior using Playwright.

Usage:
    pytest tests/integration/environment_control/test_dashboard.py -v

Requirements for interactive tests:
    pip install pytest-playwright
    playwright install chromium
"""

import urllib.request

import pytest
from playwright.sync_api import Page, expect

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


# --- Playwright Interactive Tests ---


def test_dashboard_elements(env_control_container, page: Page):
    """Test dashboard has correct title, header, and buttons."""
    page.goto(f"{env_control_container.base_url}/")

    expect(page).to_have_title("WebArena Verified - Environment Control")
    expect(page.locator("h1")).to_have_text("WebArena Verified")
    expect(page.locator("h2")).to_have_text("Environment Control")

    # Check environment name and status badge
    expect(page.locator(".info-bar")).to_contain_text("dummy")
    expect(page.locator(".status-badge")).to_be_visible()

    # Check all buttons exist
    expect(page.locator("button.btn-init")).to_have_text("Initialize")
    expect(page.locator("button.btn-start")).to_have_text("Start")
    expect(page.locator("button.btn-stop")).to_have_text("Stop")
    expect(page.locator("button.btn-restart")).to_have_text("Restart")
    expect(page.locator("button.btn-refresh")).to_have_text("Refresh Status")


def test_dashboard_button_actions(env_control_container, page: Page):
    """Test clicking buttons updates console output."""
    page.goto(f"{env_control_container.base_url}/")
    console = page.locator("#console")

    # Initial state
    expect(console).to_contain_text("Waiting for commands")

    # Test init button
    page.click("button.btn-init")
    page.wait_for_timeout(1000)
    expect(console).to_contain_text("INIT")
    expect(console).to_contain_text("success")

    # Test start button
    page.click("button.btn-start")
    page.wait_for_timeout(1000)
    expect(console).to_contain_text("START")

    # Test stop button
    page.click("button.btn-stop")
    page.wait_for_timeout(1000)
    expect(console).to_contain_text("STOP")


def test_dashboard_refresh_status(env_control_container, page: Page):
    """Test refresh button updates status badge."""
    page.goto(f"{env_control_container.base_url}/")

    page.click("button.btn-refresh")
    page.wait_for_timeout(1000)

    console = page.locator("#console")
    expect(console).to_contain_text("REFRESH STATUS")

    status_badge = page.locator(".status-badge")
    expect(status_badge).to_be_visible()
    text = status_badge.text_content()
    assert text in ("Ready", "Not Ready")
