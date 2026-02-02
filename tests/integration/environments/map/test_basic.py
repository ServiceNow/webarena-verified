"""Basic HTTP health tests for OpenStreetMap Docker container.

Tests basic connectivity to the OpenStreetMap website and tile server
without requiring Playwright.

Usage:
    pytest tests/integration/environments/map/test_basic.py \
        --map_url=http://localhost:3030 \
        --map_tile_url=http://localhost:8080
"""

import urllib.request

import pytest

pytestmark = [pytest.mark.docker, pytest.mark.integration_docker_map]


@pytest.mark.flaky(reruns=2)
def test_map_homepage_responds(map_container, map_base_url):
    """Test that OpenStreetMap homepage responds with 200."""
    req = urllib.request.Request(map_base_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200


@pytest.mark.flaky(reruns=2)
def test_map_login_page_accessible(map_container, map_base_url):
    """Test that login page is accessible."""
    login_url = f"{map_base_url}/login"
    req = urllib.request.Request(login_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200


@pytest.mark.flaky(reruns=2)
def test_map_api_capabilities(map_container, map_base_url):
    """Test that OSM API capabilities endpoint is accessible."""
    api_url = f"{map_base_url}/api/capabilities"
    req = urllib.request.Request(api_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200
        content = response.read().decode("utf-8")
        assert "api" in content.lower()


@pytest.mark.flaky(reruns=2)
def test_tile_server_responds(map_container, map_tile_url):
    """Test that tile server responds with 200."""
    req = urllib.request.Request(map_tile_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200


@pytest.mark.flaky(reruns=2)
def test_tile_endpoint_accessible(map_container, map_tile_url):
    """Test that tile endpoint returns a tile image.

    Requests zoom level 0, which should always exist (single world tile).
    """
    tile_url = f"{map_tile_url}/tile/0/0/0.png"
    req = urllib.request.Request(tile_url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as response:
        assert response.status == 200
        content_type = response.headers.get("Content-Type", "")
        assert "image" in content_type or response.read(4) == b"\x89PNG"
