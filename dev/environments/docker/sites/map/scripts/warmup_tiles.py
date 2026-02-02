#!/usr/bin/env python3
"""Warm up tile cache for US Northeast region.

Fetches tiles via HTTP to trigger rendering and caching.

Usage (inside container):
    python3 /warmup_tiles.py
    python3 /warmup_tiles.py --zoom-max 12 --parallel 16
"""

import argparse
import math
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# US Northeast bounding box (matches OSRM routing data)
BBOX = {"min_lon": -80.5, "max_lon": -66.9, "min_lat": 37.0, "max_lat": 47.5}


def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert lat/lon to tile coordinates."""
    n = 2**zoom
    x = int((lon + 180) / 360 * n)
    lat_rad = math.radians(lat)
    y = int((1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n)
    return x, y


def fetch_tile(url: str) -> tuple[str, int | str]:
    """Fetch a single tile, return URL and HTTP status or error message."""
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            resp.read()
            return url, resp.status
    except Exception as e:
        return url, str(e)


def generate_tiles(zoom_max: int) -> list[tuple[int, int, int]]:
    """Generate all tile coordinates for the bounding box."""
    tiles = []
    for z in range(zoom_max + 1):
        x_min, y_max = lat_lon_to_tile(BBOX["min_lat"], BBOX["min_lon"], z)
        x_max, y_min = lat_lon_to_tile(BBOX["max_lat"], BBOX["max_lon"], z)
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                tiles.append((z, x, y))
    return tiles


def main() -> None:
    """Warm up tile cache with command-line arguments."""
    parser = argparse.ArgumentParser(description="Warm up tile cache")
    parser.add_argument("--zoom-max", type=int, default=10, help="Max zoom level (default: 10)")
    parser.add_argument("--parallel", type=int, default=8, help="Parallel requests (default: 8)")
    parser.add_argument("--url", default="http://localhost:8080/tile", help="Tile server URL")
    args = parser.parse_args()

    tiles = generate_tiles(args.zoom_max)
    urls = [f"{args.url}/{z}/{x}/{y}.png" for z, x, y in tiles]

    print(f"Tiles to fetch: {len(urls)} (zoom 0-{args.zoom_max})")

    completed, errors = 0, 0
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {executor.submit(fetch_tile, url): url for url in urls}
        for future in as_completed(futures):
            url, status = future.result()
            completed += 1
            if status != 200:
                errors += 1
                if errors <= 5:
                    print(f"  Error: {url} -> {status}")
            if completed % 100 == 0 or completed == len(urls):
                print(f"Progress: {completed}/{len(urls)} ({errors} errors)")

    print(f"Done: {completed - errors}/{completed} tiles cached")


if __name__ == "__main__":
    main()
