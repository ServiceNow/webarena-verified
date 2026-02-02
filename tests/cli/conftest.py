"""Pytest configuration for CLI tests."""

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def webarena_verified_docker_img(request):
    """Return the Docker image to test."""
    return request.config.getoption("--webarena-verified-docker-img")


@pytest.fixture
def docker():
    """Check that docker is available and return the CLI name."""
    docker_path = shutil.which("docker")
    if docker_path is None:
        raise RuntimeError("'docker' is missing or not available in PATH.")
    return "docker"


@pytest.fixture
def uvx():
    """Check that uvx is available and return the CLI name."""
    uvx_path = shutil.which("uvx")
    if uvx_path is None:
        raise RuntimeError("'uvx' is missing or not available in PATH.")
    return "uvx"


@pytest.fixture
def get_test_asset_path(request):
    """Factory fixture that returns a path to a test asset.

    Usage:
        def test_example(get_test_asset_path):
            config_path = get_test_asset_path("cli/config.demo.json")
    """
    assets_dir = request.config.rootpath / "tests" / "assets"

    if not assets_dir.exists():
        raise RuntimeError(f"Test assets directory not found: {assets_dir}. Invalid test setup.")

    def _get_path(relative_path: str) -> Path:
        path = assets_dir / relative_path
        if not path.exists():
            raise FileNotFoundError(f"Test asset not found: {path}")
        return path

    return _get_path
