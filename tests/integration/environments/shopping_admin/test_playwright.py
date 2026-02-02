"""Playwright UI tests for Shopping Admin Docker container.

Tests the Magento admin panel functionality using browser automation.

Test categories:
- Admin Login: Authentication flow
- Admin Navigation: Menu navigation to Products and Customers pages
- Admin Reports: Sales report generation with date filtering
- Product Modification: Edit product name and verify persistence in admin

Usage:
    pytest tests/integration/environments/shopping_admin/test_playwright.py
    pytest tests/integration/environments/shopping_admin/test_playwright.py --playwright-timeout-sec=60
"""

import time

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.docker, pytest.mark.integration_docker_shopping_admin]

# Admin Login Test


@pytest.mark.flaky(reruns=2)
def test_admin_login(shopping_admin_container, shopping_admin_base_url, shopping_admin_credentials, page, pw_timeout):
    """Test admin login flow."""
    admin_url = f"{shopping_admin_base_url}/admin"

    page.goto(admin_url)

    # Wait for login form
    page.wait_for_selector('input[name="login[username]"]', timeout=pw_timeout)

    # Fill in credentials
    page.fill('input[name="login[username]"]', shopping_admin_credentials["username"])
    page.fill('input[name="login[password]"]', shopping_admin_credentials["password"])

    # Click login button
    page.click("button.action-login")

    # Wait for dashboard to load
    page.wait_for_selector(".page-title", timeout=pw_timeout)

    # Verify we're on the dashboard
    assert "Dashboard" in page.content()


# Admin Navigation Tests


@pytest.mark.flaky(reruns=2)
def test_deep_link_navigation(
    shopping_admin_container, shopping_admin_base_url, shopping_admin_get_logged_page, pw_timeout
):
    """Test navigation to a deep link (Products page)."""
    page = shopping_admin_get_logged_page()

    # Navigate to Products (Catalog > Products)
    page.click("#menu-magento-catalog-catalog")
    page.click('a[href*="catalog/product"]')

    # Wait for products page
    page.wait_for_selector(".page-title", timeout=pw_timeout)

    # Verify we're on the products page
    assert "Products" in page.content()


@pytest.mark.flaky(reruns=2)
def test_navigate_to_customers(
    shopping_admin_container, shopping_admin_base_url, shopping_admin_get_logged_page, pw_timeout
):
    """Test navigation to Customers page."""
    page = shopping_admin_get_logged_page()

    # Navigate to Customers > All Customers
    page.click("#menu-magento-customer-customer")
    page.click('a[href*="customer/index"]')

    # Wait for customers page
    page.wait_for_selector(".page-title", timeout=pw_timeout)

    # Verify we're on the customers page
    assert "Customers" in page.content()


# Admin Reports Tests


@pytest.mark.flaky(reruns=2)
def test_generate_report(shopping_admin_container, shopping_admin_base_url, shopping_admin_get_logged_page, pw_timeout):
    """Test generating a sales report with date range."""
    page = shopping_admin_get_logged_page()

    # Navigate directly to Orders Report page
    page.goto(f"{shopping_admin_base_url}/admin/reports/report_sales/sales/", timeout=pw_timeout)
    page.wait_for_selector("h1", timeout=pw_timeout)

    expect(page.locator("h1")).to_contain_text("Orders Report")

    # Fill date range
    page.fill('input[name="from"]', "01/01/2023")
    page.fill('input[name="to"]', "12/31/2023")

    # Generate report
    page.click("button:has-text('Show Report')")

    # Wait for table with data rows
    page.wait_for_selector("table tbody tr", timeout=pw_timeout)

    # Verify report was generated (check for records text or table presence)
    records_el = page.locator("text=/\\d+ records found/")
    if records_el.count() > 0:
        assert records_el.first.is_visible()
    else:
        # At minimum, table should be loaded
        assert page.locator("table tbody tr").count() > 0


# Admin Product Modification Tests


@pytest.mark.flaky(reruns=2)
def test_modify_product(
    shopping_admin_container, shopping_admin_base_url, shopping_admin_get_logged_page, get_test_product, pw_timeout
):
    """Test modifying product name and verifying persistence in admin."""
    page = shopping_admin_get_logged_page()
    product = get_test_product(page)  # Navigates to product, captures original name, will reset after

    # Update name with timestamp
    timestamp = int(time.time())
    test_name = f"{timestamp} {product['original_name']}"
    name_input = page.locator('input[name="product[name]"]')
    name_input.fill(test_name)

    # Save
    page.click("button#save-button, button:has-text('Save')")
    page.wait_for_selector("text=You saved the product", timeout=pw_timeout)

    # Verify in admin by opening product in new tab
    verify_page = page.context.new_page()
    verify_page.goto(f"{shopping_admin_base_url}/admin/catalog/product/edit/id/{product['id']}/", timeout=pw_timeout)
    verify_page.wait_for_selector('input[name="product[name]"]', timeout=pw_timeout)

    # Check the product name field contains the timestamp
    saved_name = verify_page.locator('input[name="product[name]"]').input_value()
    assert str(timestamp) in saved_name, f"Expected timestamp {timestamp} in saved name '{saved_name}'"
    verify_page.close()

    # No manual revert needed - fixture resets to original_name automatically
