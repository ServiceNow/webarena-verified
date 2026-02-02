"""Consolidated env-ctrl tests for all sites.

Tests both Docker exec and HTTP API interfaces for each site's env-ctrl.

Usage:
    # Run all env-ctrl tests
    pytest tests/integration/environments/test_env_ctrl.py

    # Run env-ctrl tests for specific site only
    pytest tests/integration/environments/test_env_ctrl.py -m integration_docker_shopping

    # Run with verbose output
    pytest tests/integration/environments/test_env_ctrl.py -v
"""

import pytest

pytestmark = pytest.mark.docker

# Site configurations for parametrization
# Each pytest.param attaches a marker so tests can be filtered by site
SITES = [
    pytest.param("shopping", marks=pytest.mark.integration_docker_shopping),
    pytest.param("shopping_admin", marks=pytest.mark.integration_docker_shopping_admin),
    pytest.param("reddit", marks=pytest.mark.integration_docker_reddit),
    pytest.param("gitlab", marks=pytest.mark.integration_docker_gitlab),
    pytest.param("wikipedia", marks=pytest.mark.integration_docker_wikipedia),
    pytest.param("map", marks=pytest.mark.integration_docker_map),
]


@pytest.fixture
def docker_client(request, create_docker_client):
    """Create Docker client for the parametrized site."""
    site = request.param
    container_name = f"webarena-verified-{site}"
    return create_docker_client(container_name)


@pytest.fixture
def http_client(request, create_http_client):
    """Create HTTP client for the parametrized site.

    Uses --{site}_env_ctrl_url CLI argument (e.g., --shopping_env_ctrl_url).
    """
    site = request.param
    env_ctrl_url = request.config.getoption(f"--{site}_env_ctrl_url")
    if env_ctrl_url is None:
        raise ValueError(f"--{site}_env_ctrl_url not specified")
    return create_http_client(env_ctrl_url)


# --- Docker Client Tests ---


@pytest.mark.flaky(reruns=2)
@pytest.mark.parametrize("docker_client", SITES, indirect=True)
def test_env_ctrl_docker_status(docker_client):
    """Test env-ctrl status via docker exec."""
    result = docker_client.status()
    assert result.success, f"Docker client status failed: {result.message}"


# --- HTTP Client Tests ---


@pytest.mark.flaky(reruns=2)
@pytest.mark.parametrize("http_client", SITES, indirect=True)
def test_env_ctrl_http_status(http_client):
    """Test env-ctrl status via HTTP API."""
    result = http_client.status()
    assert result.get("success"), f"HTTP client status failed: {result.get('message')}"
