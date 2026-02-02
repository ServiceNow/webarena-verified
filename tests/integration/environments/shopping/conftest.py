"""Shopping (storefront) site fixtures."""

import pytest

# Constants
AUTOLOGIN_HEADER = "X-M2-Customer-Auto-Login"


@pytest.fixture(scope="session")
def shopping_credentials():
    """Default customer credentials for shopping storefront.

    These are the pre-configured credentials in the Docker image,
    used for both testing and production environments.
    """
    return {
        "email": "emma.lopez@gmail.com",
        "password": "Password.123",
    }


@pytest.fixture(scope="session")
def shopping_container():
    """Shopping container name (assumes already running)."""
    return "webarena-verified-shopping"


@pytest.fixture(scope="session")
def shopping_base_url(request):
    """Base URL for shopping storefront from CLI arg."""
    url = request.config.getoption("--shopping_url")
    if url is None:
        raise ValueError("--shopping_url is required")
    return url


@pytest.fixture(scope="session")
def shopping_env_ctrl_url(request):
    """env-ctrl URL for shopping from CLI arg."""
    url = request.config.getoption("--shopping_env_ctrl_url")
    if url is None:
        raise ValueError("--shopping_env_ctrl_url is required")
    return url


@pytest.fixture(scope="session")
def shopping_docker_client(shopping_container, create_docker_client):
    """Docker client for shopping container (via docker exec)."""
    return create_docker_client(shopping_container)


@pytest.fixture(scope="session")
def shopping_http_client(shopping_env_ctrl_url, create_http_client):
    """HTTP client for shopping env-ctrl server."""
    return create_http_client(shopping_env_ctrl_url)


@pytest.fixture(params=[False, True], ids=["form_login", "autologin"])
def use_autologin(request):
    """Parametrized fixture to test with both form login and autologin."""
    return request.param


@pytest.fixture
def shopping_get_logged_page(browser, shopping_base_url, shopping_credentials, pw_timeout, use_autologin):
    """Factory fixture that returns a function to get a logged-in customer page.

    Supports both traditional form login and header-based autologin via the
    X-M2-Customer-Auto-Login header, controlled by the use_autologin parameter.
    """
    contexts = []
    pages = []

    def _get_logged_page():
        if use_autologin:
            # Create context with autologin header
            credentials_header = f"{shopping_credentials['email']}:{shopping_credentials['password']}"
            context = browser.new_context(extra_http_headers={AUTOLOGIN_HEADER: credentials_header})
            contexts.append(context)
            page = context.new_page()
            pages.append(page)
            page.goto(f"{shopping_base_url}/customer/account", timeout=pw_timeout)
            page.wait_for_selector(".block-dashboard-info, .box-information", timeout=pw_timeout)
        else:
            # Traditional form login
            context = browser.new_context()
            contexts.append(context)
            page = context.new_page()
            pages.append(page)
            page.goto(f"{shopping_base_url}/customer/account/login", timeout=pw_timeout)
            page.wait_for_selector('input[name="login[username]"]', timeout=pw_timeout)
            page.fill('input[name="login[username]"]', shopping_credentials["email"])
            page.fill('input[name="login[password]"]', shopping_credentials["password"])
            page.click('button[type="submit"].action.login')
            page.wait_for_selector(".block-dashboard-info, .box-information", timeout=pw_timeout)
        return page

    yield _get_logged_page

    # Cleanup
    for page in pages:
        page.close()
    for context in contexts:
        context.close()
