"""Wikipedia site fixtures."""

import pytest


@pytest.fixture(scope="session")
def wikipedia_base_url(request):
    """Base URL for Wikipedia from CLI arg."""
    url = request.config.getoption("--wikipedia_url")
    if url is None:
        raise ValueError("--wikipedia_url is required")
    return url


@pytest.fixture(scope="session")
def wikipedia_container():
    """Wikipedia container name (assumes already running)."""
    return "webarena-verified-wikipedia"


@pytest.fixture(scope="session")
def wikipedia_docker_client(wikipedia_container, create_docker_client):
    """Docker client for Wikipedia container (via docker exec)."""
    return create_docker_client(wikipedia_container)


@pytest.fixture(scope="session")
def wikipedia_env_ctrl_url(request):
    """env-ctrl URL for Wikipedia from CLI arg."""
    url = request.config.getoption("--wikipedia_env_ctrl_url")
    if url is None:
        raise ValueError("--wikipedia_env_ctrl_url is required")
    return url


@pytest.fixture(scope="session")
def wikipedia_http_client(wikipedia_env_ctrl_url, create_http_client):
    """HTTP client for Wikipedia env-ctrl server."""
    return create_http_client(wikipedia_env_ctrl_url)
