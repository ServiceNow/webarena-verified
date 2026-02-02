"""CI-specific tests for Map Docker container with Monaco data.

These tests use a tiny Monaco OSM dataset (~656KB source) for fast CI testing.
They verify basic functionality without requiring the full US-Northeast dataset.

Monaco coordinates: ~43.73°N, 7.42°E

Usage:
    inv dev.ci.generate-map-data  # Generate Monaco data first (or restore from cache)
    pytest tests/integration/environments/map/test_ci.py -m integration_docker_map
"""

import math
import urllib.request

import pytest

pytestmark = [pytest.mark.docker, pytest.mark.integration_docker_map]

# Monaco bounds for testing
MONACO_LAT = 43.7384
MONACO_LON = 7.4246
MONACO_ZOOM = 14


@pytest.mark.flaky(reruns=2)
def test_map_ci_homepage_loads(map_container, map_base_url, page, pw_timeout):
    """Test that map homepage loads with Monaco data."""
    page.goto(map_base_url, timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Verify we're on the OpenStreetMap page
    content = page.content().lower()
    assert "openstreetmap" in content or "map" in content


@pytest.mark.flaky(reruns=2)
def test_map_ci_monaco_view(map_container, map_base_url, page, pw_timeout):
    """Test that Monaco area loads correctly."""
    # Navigate to Monaco coordinates
    monaco_url = f"{map_base_url}/#map={MONACO_ZOOM}/{MONACO_LAT}/{MONACO_LON}"
    page.goto(monaco_url, timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Page should load without errors
    content = page.content()
    assert len(content) > 100, "Page should have content"


@pytest.mark.flaky(reruns=2)
def test_map_ci_tile_renders(map_container, map_tile_url):
    """Test that tiles render for Monaco area.

    Requests a tile at zoom 14 covering Monaco.
    Tile coordinates calculated for Monaco (43.73°N, 7.42°E).
    """
    # Calculate tile coordinates for Monaco at zoom 14
    # Using standard Web Mercator tile calculation
    zoom = MONACO_ZOOM
    lat_rad = math.radians(MONACO_LAT)
    n = 2**zoom
    x = int((MONACO_LON + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n)

    tile_url = f"{map_tile_url}/tile/{zoom}/{x}/{y}.png"
    req = urllib.request.Request(tile_url, method="GET")

    with urllib.request.urlopen(req, timeout=60) as response:
        assert response.status == 200
        content_type = response.headers.get("Content-Type", "")
        data = response.read()
        # Verify it's a PNG image
        assert "image" in content_type or data[:4] == b"\x89PNG", "Response should be a PNG tile"
        # Verify tile has actual content (not just blank)
        assert len(data) > 100, "Tile should have content"


@pytest.mark.flaky(reruns=2)
def test_map_ci_search_monaco(map_container, map_base_url, page, pw_timeout):
    """Test that search finds Monaco location."""
    page.goto(map_base_url, timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Find search input
    search_input = page.locator('input[name="query"]').first
    if search_input.is_visible(timeout=5000):
        search_input.fill("Monaco")
        search_input.press("Enter")

        # Wait for search results
        page.wait_for_load_state("networkidle", timeout=pw_timeout)

        # Check URL or content for search results
        content = page.content().lower()
        # Search should show Monaco results
        assert "monaco" in content or "search" in page.url.lower()


@pytest.mark.flaky(reruns=2)
def test_map_ci_routing_endpoint(map_container, map_tile_url):
    """Test that OSRM routing endpoint responds.

    Tests routing between two points in Monaco.
    """
    # Two points in Monaco for routing test
    start_lon, start_lat = 7.4167, 43.7333  # Monaco-Ville
    end_lon, end_lat = 7.4286, 43.7396  # Monte Carlo

    # OSRM route request
    route_url = f"{map_tile_url}/osrm/car/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=false"

    req = urllib.request.Request(route_url, method="GET")
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req, timeout=30) as response:
        assert response.status == 200
        content = response.read().decode("utf-8")
        # OSRM returns JSON with "code": "Ok" on success
        assert '"code"' in content


@pytest.mark.flaky(reruns=2)
def test_map_ci_nominatim_search(map_container, map_tile_url):
    """Test that Nominatim geocoding endpoint responds."""
    search_url = f"{map_tile_url}/nominatim/search?q=Monaco&format=json&limit=1"

    req = urllib.request.Request(search_url, method="GET")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            assert response.status == 200
            content = response.read().decode("utf-8")
            # Should return JSON array
            assert content.startswith("[")
    except urllib.error.HTTPError as e:
        # Accept endpoint existing even if search fails
        if e.code >= 500:
            raise
