"""Shopping Admin site fixtures."""

import pytest

# Constants
AUTOLOGIN_HEADER = "X-M2-Admin-Auto-Login"


@pytest.fixture(scope="session")
def shopping_admin_credentials():
    """Default admin credentials for Magento backend.

    These are the pre-configured credentials in the Docker image,
    used for both testing and production environments.
    """
    return {
        "username": "admin",
        "password": "admin1234",
    }


@pytest.fixture(scope="session")
def shopping_admin_container():
    """Shopping admin container name (assumes already running)."""
    return "webarena-verified-shopping_admin"


@pytest.fixture(scope="session")
def shopping_admin_base_url(request):
    """Base URL for admin panel from CLI arg."""
    url = request.config.getoption("--shopping_admin_url")
    if url is None:
        raise ValueError("--shopping_admin_url is required")
    return url


@pytest.fixture(scope="session")
def shopping_admin_env_ctrl_url(request):
    """env-ctrl URL for shopping admin from CLI arg."""
    url = request.config.getoption("--shopping_admin_env_ctrl_url")
    if url is None:
        raise ValueError("--shopping_admin_env_ctrl_url is required")
    return url


@pytest.fixture(scope="session")
def shopping_admin_docker_client(shopping_admin_container, create_docker_client):
    """Docker client for shopping admin container (via docker exec)."""
    return create_docker_client(shopping_admin_container)


@pytest.fixture(scope="session")
def shopping_admin_http_client(shopping_admin_env_ctrl_url, create_http_client):
    """HTTP client for shopping admin env-ctrl server."""
    return create_http_client(shopping_admin_env_ctrl_url)


@pytest.fixture(params=[False, True], ids=["form_login", "autologin"])
def use_autologin(request):
    """Parametrized fixture to test with both form login and autologin."""
    return request.param


@pytest.fixture
def shopping_admin_get_logged_page(
    browser, shopping_admin_base_url, shopping_admin_credentials, pw_timeout, use_autologin
):
    """Factory fixture that returns a function to get a logged-in admin page.

    Supports both traditional form login and header-based autologin via the
    X-M2-Admin-Auto-Login header, controlled by the use_autologin parameter.
    """
    contexts = []
    pages = []

    def _get_logged_page():
        if use_autologin:
            # Create context with autologin header
            credentials_header = f"{shopping_admin_credentials['username']}:{shopping_admin_credentials['password']}"
            context = browser.new_context(extra_http_headers={AUTOLOGIN_HEADER: credentials_header})
            contexts.append(context)
            page = context.new_page()
            pages.append(page)
            page.goto(f"{shopping_admin_base_url}/admin")
            page.wait_for_selector(".page-title", timeout=pw_timeout)
        else:
            # Traditional form login
            context = browser.new_context()
            contexts.append(context)
            page = context.new_page()
            pages.append(page)
            page.goto(f"{shopping_admin_base_url}/admin")
            page.wait_for_selector('input[name="login[username]"]', timeout=pw_timeout)
            page.fill('input[name="login[username]"]', shopping_admin_credentials["username"])
            page.fill('input[name="login[password]"]', shopping_admin_credentials["password"])
            page.click("button.action-login")
            page.wait_for_selector(".page-title", timeout=pw_timeout)
        return page

    yield _get_logged_page

    # Cleanup
    for page in pages:
        page.close()
    for context in contexts:
        context.close()


# Default product ID for modification tests
PRODUCT_ID = 1


@pytest.fixture
def get_test_product(shopping_admin_base_url, pw_timeout):
    """Factory fixture to get test product info with optional reset.

    Captures the original product name when called and resets to it after the test.

    Usage:
        def test_something(shopping_admin_get_logged_page, get_test_product):
            page = shopping_admin_get_logged_page()
            product = get_test_product(page)  # returns {"id": 1, "name": "...", "original_name": "..."}
            # ... test logic ...
            # product name auto-resets to original_name after test

        def test_readonly(shopping_admin_get_logged_page, get_test_product):
            page = shopping_admin_get_logged_page()
            product = get_test_product(page, no_reset=True)  # no reset needed
    """
    products_to_reset = []  # Track (page, product_id, original_name) for teardown

    def _get_test_product(page, product_id=PRODUCT_ID, no_reset=False):
        # Navigate to product edit page
        page.goto(f"{shopping_admin_base_url}/admin/catalog/product/edit/id/{product_id}/", timeout=pw_timeout)
        page.wait_for_selector('input[name="product[name]"]', timeout=pw_timeout)

        # Capture original name dynamically
        name_input = page.locator('input[name="product[name]"]')
        original_name = name_input.input_value()

        if not no_reset:
            products_to_reset.append((page, product_id, original_name))

        return {
            "id": product_id,
            "name": original_name,
            "original_name": original_name,
        }

    yield _get_test_product

    # Teardown: reset all products to their original names
    for page, product_id, original_name in products_to_reset:
        try:
            page.goto(f"{shopping_admin_base_url}/admin/catalog/product/edit/id/{product_id}/", timeout=pw_timeout)
            page.wait_for_selector('input[name="product[name]"]', timeout=pw_timeout)

            name_input = page.locator('input[name="product[name]"]')
            current_name = name_input.input_value()

            if current_name != original_name:
                name_input.fill(original_name)
                page.click("button#save-button, button:has-text('Save')")
                page.wait_for_selector("text=You saved the product", timeout=pw_timeout)
        except Exception:
            pass  # Best effort cleanup
