"""Integration tests for the environment_control dashboard.

Tests both HTML content and interactive functionality using Playwright.

Usage:
    pytest tests/integration/environment_control/test_dashboard.py -v

Requirements for Playwright tests:
    pip install pytest-playwright
    playwright install chromium
"""

import urllib.request

import pytest

# --- HTML Content Tests ---


def test_dashboard_returns_html(env_control_container):
    """Test GET / returns HTML with correct content type."""
    url = "http://localhost:8877/"
    with urllib.request.urlopen(url, timeout=5) as response:
        content_type = response.headers.get("Content-Type", "")
        content = response.read().decode("utf-8")

    assert response.status == 200
    assert "text/html" in content_type
    assert "<!DOCTYPE html>" in content


def test_dashboard_shows_environment_name(env_control_container):
    """Test dashboard displays the environment name."""
    url = "http://localhost:8877/"
    with urllib.request.urlopen(url, timeout=5) as response:
        content = response.read().decode("utf-8")

    # Should show "dummy" as the environment name
    assert "dummy" in content
    assert "Environment:" in content


def test_dashboard_shows_status_badge(env_control_container):
    """Test dashboard displays status badge."""
    url = "http://localhost:8877/"
    with urllib.request.urlopen(url, timeout=5) as response:
        content = response.read().decode("utf-8")

    # Should have status badge with ready/not-ready class
    assert "status-badge" in content
    assert "Status:" in content


def test_dashboard_has_action_buttons(env_control_container):
    """Test dashboard has all action buttons."""
    url = "http://localhost:8877/"
    with urllib.request.urlopen(url, timeout=5) as response:
        content = response.read().decode("utf-8")

    # Check for all action buttons
    assert "Initialize" in content
    assert "Start" in content
    assert "Stop" in content
    assert "Restart" in content
    assert "Refresh Status" in content


def test_dashboard_has_console_area(env_control_container):
    """Test dashboard has console output area."""
    url = "http://localhost:8877/"
    with urllib.request.urlopen(url, timeout=5) as response:
        content = response.read().decode("utf-8")

    assert "Console Output" in content
    assert 'id="console"' in content


def test_dashboard_has_javascript(env_control_container):
    """Test dashboard includes required JavaScript functions."""
    url = "http://localhost:8877/"
    with urllib.request.urlopen(url, timeout=5) as response:
        content = response.read().decode("utf-8")

    # Check for key JavaScript functions
    assert "doAction" in content
    assert "refreshStatus" in content
    assert "<script>" in content


def test_dashboard_shows_ready_when_healthy(env_control_container):
    """Test dashboard shows ready status when services are healthy."""
    url = "http://localhost:8877/"
    with urllib.request.urlopen(url, timeout=5) as response:
        content = response.read().decode("utf-8")

    # Default dummy ops returns healthy, so should show "ready" class
    assert 'class="status-badge ready"' in content or "Ready" in content


# --- Playwright Interactive Tests ---
# These tests require: pip install pytest-playwright && playwright install chromium


# Try to import playwright - mark tests to skip if not available
try:
    from playwright.sync_api import Page, expect

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None  # type: ignore[assignment,misc]
    expect = None  # type: ignore[assignment,misc]


DASHBOARD_URL = "http://localhost:8877/"


@pytest.fixture(scope="module")
def browser(env_control_container):
    """Create a browser instance for the test module."""
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("playwright not installed")

    from playwright.sync_api import sync_playwright  # noqa: PLC0415 (optional dependency)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    """Create a new page for each test."""
    page = browser.new_page()
    yield page
    page.close()


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="playwright not installed")
class TestDashboardLoads:
    """Tests for dashboard initial load."""

    def test_dashboard_title(self, page: Page):
        """Test dashboard has correct title."""
        page.goto(DASHBOARD_URL)
        expect(page).to_have_title("WebArena Verified - Environment Control")

    def test_dashboard_header(self, page: Page):
        """Test dashboard shows header text."""
        page.goto(DASHBOARD_URL)
        expect(page.locator("h1")).to_have_text("WebArena Verified")
        expect(page.locator("h2")).to_have_text("Environment Control")

    def test_dashboard_shows_environment(self, page: Page):
        """Test dashboard shows environment name."""
        page.goto(DASHBOARD_URL)
        info_bar = page.locator(".info-bar")
        expect(info_bar).to_contain_text("dummy")

    def test_dashboard_shows_status(self, page: Page):
        """Test dashboard shows status badge."""
        page.goto(DASHBOARD_URL)
        status_badge = page.locator(".status-badge")
        expect(status_badge).to_be_visible()


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="playwright not installed")
class TestActionButtons:
    """Tests for dashboard action buttons."""

    def test_init_button_exists(self, page: Page):
        """Test Initialize button exists."""
        page.goto(DASHBOARD_URL)
        button = page.locator("button.btn-init")
        expect(button).to_be_visible()
        expect(button).to_have_text("Initialize")

    def test_start_button_exists(self, page: Page):
        """Test Start button exists."""
        page.goto(DASHBOARD_URL)
        button = page.locator("button.btn-start")
        expect(button).to_be_visible()
        expect(button).to_have_text("Start")

    def test_stop_button_exists(self, page: Page):
        """Test Stop button exists."""
        page.goto(DASHBOARD_URL)
        button = page.locator("button.btn-stop")
        expect(button).to_be_visible()
        expect(button).to_have_text("Stop")

    def test_restart_button_exists(self, page: Page):
        """Test Restart button exists."""
        page.goto(DASHBOARD_URL)
        button = page.locator("button.btn-restart")
        expect(button).to_be_visible()
        expect(button).to_have_text("Restart")

    def test_refresh_button_exists(self, page: Page):
        """Test Refresh Status button exists."""
        page.goto(DASHBOARD_URL)
        button = page.locator("button.btn-refresh")
        expect(button).to_be_visible()
        expect(button).to_have_text("Refresh Status")


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="playwright not installed")
class TestButtonClicks:
    """Tests for button click interactions."""

    def test_init_button_updates_console(self, page: Page):
        """Test clicking Initialize updates console."""
        page.goto(DASHBOARD_URL)
        console = page.locator("#console")

        # Click init button
        page.click("button.btn-init")

        # Wait for response and check console
        page.wait_for_timeout(1000)
        expect(console).to_contain_text("INIT")
        expect(console).to_contain_text("success")

    def test_start_button_updates_console(self, page: Page):
        """Test clicking Start updates console."""
        page.goto(DASHBOARD_URL)
        console = page.locator("#console")

        # Click start button
        page.click("button.btn-start")

        # Wait for response and check console
        page.wait_for_timeout(1000)
        expect(console).to_contain_text("START")
        expect(console).to_contain_text("success")

    def test_stop_button_updates_console(self, page: Page):
        """Test clicking Stop updates console."""
        page.goto(DASHBOARD_URL)
        console = page.locator("#console")

        # Click stop button
        page.click("button.btn-stop")

        # Wait for response and check console
        page.wait_for_timeout(1000)
        expect(console).to_contain_text("STOP")
        expect(console).to_contain_text("success")

    def test_restart_button_updates_console(self, page: Page):
        """Test clicking Restart updates console."""
        page.goto(DASHBOARD_URL)
        console = page.locator("#console")

        # First ensure we're in started state
        page.click("button.btn-start")
        page.wait_for_timeout(500)

        # Click restart button
        page.click("button.btn-restart")

        # Wait for response and check console
        page.wait_for_timeout(1000)
        expect(console).to_contain_text("RESTART")
        expect(console).to_contain_text("success")

    def test_refresh_button_updates_status(self, page: Page):
        """Test clicking Refresh Status updates console."""
        page.goto(DASHBOARD_URL)
        console = page.locator("#console")

        # First ensure we're started
        page.click("button.btn-start")
        page.wait_for_timeout(500)

        # Click refresh button
        page.click("button.btn-refresh")

        # Wait for response and check console
        page.wait_for_timeout(1000)
        expect(console).to_contain_text("REFRESH STATUS")


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="playwright not installed")
class TestStatusBadge:
    """Tests for status badge updates."""

    def test_status_badge_shows_ready_initially(self, page: Page):
        """Test status badge shows Ready on load (dummy ops default)."""
        page.goto(DASHBOARD_URL)
        status_badge = page.locator(".status-badge")

        # Default dummy ops returns healthy
        expect(status_badge).to_have_text("Ready")
        expect(status_badge).to_have_class("status-badge ready")

    def test_status_badge_updates_on_refresh(self, page: Page):
        """Test status badge can be refreshed."""
        page.goto(DASHBOARD_URL)

        # Ensure started state
        page.click("button.btn-start")
        page.wait_for_timeout(500)

        # Click refresh
        page.click("button.btn-refresh")
        page.wait_for_timeout(1000)

        # Should still be ready (dummy ops returns healthy by default)
        status_badge = page.locator(".status-badge")
        expect(status_badge).to_have_text("Ready")


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="playwright not installed")
class TestConsole:
    """Tests for console output area."""

    def test_console_shows_initial_message(self, page: Page):
        """Test console shows initial waiting message."""
        page.goto(DASHBOARD_URL)
        console = page.locator("#console")
        expect(console).to_contain_text("Waiting for commands")

    def test_console_accumulates_output(self, page: Page):
        """Test console accumulates output from multiple actions."""
        page.goto(DASHBOARD_URL)
        console = page.locator("#console")

        # Perform multiple actions
        page.click("button.btn-start")
        page.wait_for_timeout(500)

        page.click("button.btn-stop")
        page.wait_for_timeout(500)

        # Console should have both actions
        expect(console).to_contain_text("START")
        expect(console).to_contain_text("STOP")
