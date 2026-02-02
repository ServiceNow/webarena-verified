"""Interactive Playwright tests for the environment_control dashboard.

Tests button clicks and dynamic behavior using Playwright.

Usage:
    pytest tests/integration/environment_control/test_dashboard_interactive.py -v

Requirements:
    pip install pytest-playwright
    playwright install chromium
"""

from playwright.sync_api import Page, expect

DASHBOARD_URL = "http://localhost:8877/"


def test_dashboard_title(env_control_container, page: Page):
    """Test dashboard has correct title."""
    page.goto(DASHBOARD_URL)
    expect(page).to_have_title("WebArena Verified - Environment Control")


def test_dashboard_header(env_control_container, page: Page):
    """Test dashboard shows header text."""
    page.goto(DASHBOARD_URL)
    expect(page.locator("h1")).to_have_text("WebArena Verified")
    expect(page.locator("h2")).to_have_text("Environment Control")


def test_dashboard_shows_environment(env_control_container, page: Page):
    """Test dashboard shows environment name."""
    page.goto(DASHBOARD_URL)
    info_bar = page.locator(".info-bar")
    expect(info_bar).to_contain_text("dummy")


def test_dashboard_shows_status(env_control_container, page: Page):
    """Test dashboard shows status badge."""
    page.goto(DASHBOARD_URL)
    status_badge = page.locator(".status-badge")
    expect(status_badge).to_be_visible()


def test_init_button_exists(env_control_container, page: Page):
    """Test Initialize button exists."""
    page.goto(DASHBOARD_URL)
    button = page.locator("button.btn-init")
    expect(button).to_be_visible()
    expect(button).to_have_text("Initialize")


def test_start_button_exists(env_control_container, page: Page):
    """Test Start button exists."""
    page.goto(DASHBOARD_URL)
    button = page.locator("button.btn-start")
    expect(button).to_be_visible()
    expect(button).to_have_text("Start")


def test_stop_button_exists(env_control_container, page: Page):
    """Test Stop button exists."""
    page.goto(DASHBOARD_URL)
    button = page.locator("button.btn-stop")
    expect(button).to_be_visible()
    expect(button).to_have_text("Stop")


def test_restart_button_exists(env_control_container, page: Page):
    """Test Restart button exists."""
    page.goto(DASHBOARD_URL)
    button = page.locator("button.btn-restart")
    expect(button).to_be_visible()
    expect(button).to_have_text("Restart")


def test_refresh_button_exists(env_control_container, page: Page):
    """Test Refresh Status button exists."""
    page.goto(DASHBOARD_URL)
    button = page.locator("button.btn-refresh")
    expect(button).to_be_visible()
    expect(button).to_have_text("Refresh Status")


def test_init_button_updates_console(env_control_container, page: Page):
    """Test clicking Initialize updates console."""
    page.goto(DASHBOARD_URL)
    console = page.locator("#console")

    page.click("button.btn-init")
    page.wait_for_timeout(1000)

    expect(console).to_contain_text("INIT")
    expect(console).to_contain_text("success")


def test_start_button_updates_console(env_control_container, page: Page):
    """Test clicking Start updates console."""
    page.goto(DASHBOARD_URL)
    console = page.locator("#console")

    page.click("button.btn-start")
    page.wait_for_timeout(1000)

    expect(console).to_contain_text("START")
    expect(console).to_contain_text("success")


def test_stop_button_updates_console(env_control_container, page: Page):
    """Test clicking Stop updates console."""
    page.goto(DASHBOARD_URL)
    console = page.locator("#console")

    page.click("button.btn-stop")
    page.wait_for_timeout(1000)

    expect(console).to_contain_text("STOP")
    expect(console).to_contain_text("success")


def test_restart_button_updates_console(env_control_container, page: Page):
    """Test clicking Restart updates console."""
    page.goto(DASHBOARD_URL)
    console = page.locator("#console")

    page.click("button.btn-start")
    page.wait_for_timeout(500)

    page.click("button.btn-restart")
    page.wait_for_timeout(1000)

    expect(console).to_contain_text("RESTART")
    expect(console).to_contain_text("success")


def test_refresh_button_updates_status(env_control_container, page: Page):
    """Test clicking Refresh Status updates console."""
    page.goto(DASHBOARD_URL)
    console = page.locator("#console")

    page.click("button.btn-start")
    page.wait_for_timeout(500)

    page.click("button.btn-refresh")
    page.wait_for_timeout(1000)

    expect(console).to_contain_text("REFRESH STATUS")


def test_status_badge_shows_ready_initially(env_control_container, page: Page):
    """Test status badge shows Ready on load (dummy ops default)."""
    page.goto(DASHBOARD_URL)
    status_badge = page.locator(".status-badge")

    expect(status_badge).to_have_text("Ready")
    expect(status_badge).to_have_class("status-badge ready")


def test_status_badge_updates_on_refresh(env_control_container, page: Page):
    """Test status badge updates after refresh."""
    page.goto(DASHBOARD_URL)

    page.click("button.btn-refresh")
    page.wait_for_timeout(1000)

    # Status badge should be visible and have either Ready or Not Ready
    status_badge = page.locator(".status-badge")
    expect(status_badge).to_be_visible()
    text = status_badge.text_content()
    assert text in ("Ready", "Not Ready")


def test_console_shows_initial_message(env_control_container, page: Page):
    """Test console shows initial waiting message."""
    page.goto(DASHBOARD_URL)
    console = page.locator("#console")
    expect(console).to_contain_text("Waiting for commands")


def test_console_accumulates_output(env_control_container, page: Page):
    """Test console accumulates output from multiple actions."""
    page.goto(DASHBOARD_URL)
    console = page.locator("#console")

    page.click("button.btn-start")
    page.wait_for_timeout(500)

    page.click("button.btn-stop")
    page.wait_for_timeout(500)

    expect(console).to_contain_text("START")
    expect(console).to_contain_text("STOP")
