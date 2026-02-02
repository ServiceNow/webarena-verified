"""Map (OpenStreetMap) site fixtures."""

import pytest


@pytest.fixture(scope="session")
def map_base_url(request):
    """Base URL for OpenStreetMap website from CLI arg."""
    url = request.config.getoption("--map_url")
    if url is None:
        raise ValueError("--map_url is required")
    return url


@pytest.fixture(scope="session")
def map_tile_url(request):
    """Tile server URL for OpenStreetMap from CLI arg."""
    url = request.config.getoption("--map_tile_url")
    if url is None:
        raise ValueError("--map_tile_url is required")
    return url


@pytest.fixture(scope="session")
def map_container():
    """Map container name (assumes already running)."""
    return "osm-website"
