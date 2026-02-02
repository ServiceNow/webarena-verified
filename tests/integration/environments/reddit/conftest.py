"""Reddit (Postmill) site fixtures."""

import pytest

# Header name for Postmill's autologin feature
AUTOLOGIN_HEADER = "X-Postmill-Auto-Login"


@pytest.fixture(scope="session")
def reddit_container():
    """Reddit container name (assumes already running)."""
    return "webarena-verified-reddit"


@pytest.fixture(scope="session")
def reddit_credentials():
    """Default user credentials for Reddit (Postmill).

    These are the pre-configured credentials in the Docker image,
    used for both testing and production environments.
    """
    return {
        "username": "MarvelsGrantMan136",
        "password": "test1234",
    }


@pytest.fixture(scope="session")
def reddit_base_url(request):
    """Base URL for Reddit from CLI arg."""
    url = request.config.getoption("--reddit_url")
    if url is None:
        raise ValueError("--reddit_url is required")
    return url


@pytest.fixture(scope="session")
def reddit_env_ctrl_url(request):
    """env-ctrl URL for Reddit from CLI arg."""
    url = request.config.getoption("--reddit_env_ctrl_url")
    if url is None:
        raise ValueError("--reddit_env_ctrl_url is required")
    return url


@pytest.fixture(scope="session")
def reddit_docker_client(reddit_container, create_docker_client):
    """Docker client for Reddit container (via docker exec)."""
    return create_docker_client(reddit_container)


@pytest.fixture(scope="session")
def reddit_http_client(reddit_env_ctrl_url, create_http_client):
    """HTTP client for Reddit env-ctrl server."""
    return create_http_client(reddit_env_ctrl_url)


@pytest.fixture(params=[False, True], ids=["form_login", "autologin"])
def use_autologin(request):
    """Parametrized fixture to test with both form login and autologin."""
    return request.param


@pytest.fixture
def reddit_get_logged_page(browser, reddit_base_url, reddit_credentials, pw_timeout, use_autologin):
    """Factory fixture that returns a function to get a logged-in page.

    Supports both traditional form login and header-based autologin via the
    X-Postmill-Auto-Login header, controlled by the use_autologin parameter.
    """
    contexts = []
    pages = []

    def _get_logged_page():
        if use_autologin:
            # Create context with autologin header
            credentials_header = f"{reddit_credentials['username']}:{reddit_credentials['password']}"
            context = browser.new_context(extra_http_headers={AUTOLOGIN_HEADER: credentials_header})
            contexts.append(context)
            page = context.new_page()
            pages.append(page)
            page.goto(reddit_base_url, timeout=pw_timeout)
            page.wait_for_selector(f'button:has-text("{reddit_credentials["username"]}")', timeout=pw_timeout)
        else:
            # Traditional form login
            context = browser.new_context()
            contexts.append(context)
            page = context.new_page()
            pages.append(page)
            page.goto(f"{reddit_base_url}/login", timeout=pw_timeout)
            page.wait_for_selector('input[name="_username"]', timeout=pw_timeout)
            page.fill('input[name="_username"]', reddit_credentials["username"])
            page.fill('input[name="_password"]', reddit_credentials["password"])
            page.click('button[type="submit"]')
            page.wait_for_selector(f'button:has-text("{reddit_credentials["username"]}")', timeout=pw_timeout)
        return page

    yield _get_logged_page

    # Cleanup
    for page in pages:
        page.close()
    for context in contexts:
        context.close()
