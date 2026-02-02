"""Pytest configuration for integration tests.

These tests assume containers are already running. Use `inv envs.docker.start --site <site>`
to start containers before running tests.

Example:
    pytest tests/integration/environments/shopping_admin/ \
        --shopping_admin_url=http://localhost:7780 \
        --shopping_admin_env_ctrl_url=http://localhost:8877
"""

import pytest

from webarena_verified.environments.env_ctrl_client import EnvCtrlDockerClient, HttpClient


def pytest_addoption(parser):
    """Add CLI options for integration tests.

    All site-specific URL options are defined here because pytest parses
    arguments before discovering subdirectory conftest files.
    """
    # Playwright options
    parser.addoption(
        "--playwright-slow-mo",
        action="store",
        type=int,
        default=1500,
        help="Playwright slow motion in milliseconds",
    )
    parser.addoption(
        "--playwright-timeout-sec",
        action="store",
        type=int,
        default=30,
        help="Playwright timeout in seconds (default: 30)",
    )

    # Shopping Admin site
    parser.addoption(
        "--shopping_admin_url",
        action="store",
        default=None,
        help="Base URL for shopping-admin site (e.g., http://localhost:7780)",
    )
    parser.addoption(
        "--shopping_admin_env_ctrl_url",
        action="store",
        default=None,
        help="env-ctrl URL for shopping-admin site (e.g., http://localhost:8877)",
    )

    # Shopping (storefront) site
    parser.addoption(
        "--shopping_url",
        action="store",
        default=None,
        help="Base URL for shopping site (e.g., http://localhost:7770)",
    )
    parser.addoption(
        "--shopping_env_ctrl_url",
        action="store",
        default=None,
        help="env-ctrl URL for shopping site (e.g., http://localhost:8877)",
    )

    # Reddit site
    parser.addoption(
        "--reddit_url",
        action="store",
        default=None,
        help="Base URL for reddit site (e.g., http://localhost:9999)",
    )
    parser.addoption(
        "--reddit_env_ctrl_url",
        action="store",
        default=None,
        help="env-ctrl URL for reddit site (e.g., http://localhost:8877)",
    )

    # GitLab site
    parser.addoption(
        "--gitlab_url",
        action="store",
        default=None,
        help="Base URL for gitlab site (e.g., http://localhost:8023)",
    )
    parser.addoption(
        "--gitlab_env_ctrl_url",
        action="store",
        default=None,
        help="env-ctrl URL for gitlab site (e.g., http://localhost:8877)",
    )

    # Wikipedia site
    parser.addoption(
        "--wikipedia_url",
        action="store",
        default=None,
        help="Base URL for wikipedia site (e.g., http://localhost:8888)",
    )
    parser.addoption(
        "--wikipedia_env_ctrl_url",
        action="store",
        default=None,
        help="env-ctrl URL for wikipedia site (e.g., http://localhost:8877)",
    )

    # Map (OpenStreetMap) site
    parser.addoption(
        "--map_url",
        action="store",
        default=None,
        help="Base URL for map site (e.g., http://localhost:3030)",
    )
    parser.addoption(
        "--map_tile_url",
        action="store",
        default=None,
        help="Tile server URL for map site (e.g., http://localhost:8080)",
    )


@pytest.fixture(scope="session")
def playwright_slow_mo(request):
    """Get playwright slow motion from CLI option."""
    return request.config.getoption("--playwright-slow-mo")


@pytest.fixture(scope="session")
def pw_timeout(request):
    """Get playwright timeout in milliseconds from CLI option (specified in seconds)."""
    return request.config.getoption("--playwright-timeout-sec") * 1000


@pytest.fixture(scope="session")
def create_docker_client():
    """Factory fixture to create env-ctrl Docker clients."""

    def _create(container_name: str, timeout: int = 30) -> EnvCtrlDockerClient:
        return EnvCtrlDockerClient.create(container_name, timeout=timeout)

    return _create


@pytest.fixture(scope="session")
def create_http_client():
    """Factory fixture to create env-ctrl HTTP clients."""

    def _create(base_url: str, timeout: int = 30) -> HttpClient:
        return HttpClient(base_url=base_url, timeout=timeout)

    return _create
