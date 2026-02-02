"""GitLab site fixtures."""

import pytest


@pytest.fixture(scope="session")
def gitlab_credentials():
    """Default user credentials for GitLab.

    These are the pre-configured credentials in the Docker image,
    used for both testing and production environments.
    """
    return {
        "username": "byteblaze",
        "password": "hello1234",
    }


@pytest.fixture(scope="session")
def gitlab_base_url(request):
    """Base URL for GitLab from CLI arg."""
    url = request.config.getoption("--gitlab_url")
    if url is None:
        raise ValueError("--gitlab_url is required")
    return url


@pytest.fixture(scope="session")
def gitlab_env_ctrl_url(request):
    """env-ctrl URL for GitLab from CLI arg."""
    url = request.config.getoption("--gitlab_env_ctrl_url")
    if url is None:
        raise ValueError("--gitlab_env_ctrl_url is required")
    return url


@pytest.fixture(scope="session")
def gitlab_container():
    """GitLab container name (assumes already running)."""
    return "webarena-verified-gitlab"


@pytest.fixture(scope="session")
def gitlab_docker_client(gitlab_container, create_docker_client):
    """Docker client for GitLab container (via docker exec)."""
    return create_docker_client(gitlab_container)


@pytest.fixture(scope="session")
def gitlab_http_client(gitlab_env_ctrl_url, create_http_client):
    """HTTP client for GitLab env-ctrl server."""
    return create_http_client(gitlab_env_ctrl_url)


@pytest.fixture
def gitlab_logged_in_page(page, gitlab_base_url, gitlab_credentials, pw_timeout):
    """Page fixture that's already logged in to GitLab."""
    page.goto(f"{gitlab_base_url}/users/sign_in")
    # Use test IDs for reliable selectors
    page.get_by_test_id("username-field").fill(gitlab_credentials["username"])
    page.get_by_test_id("password-field").fill(gitlab_credentials["password"])
    page.get_by_test_id("sign-in-button").click()
    # Wait for dashboard to confirm login
    page.wait_for_url("**/", timeout=pw_timeout)
    return page
