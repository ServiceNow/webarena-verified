"""Pytest configuration for all tests."""

import shutil

import pytest


@pytest.fixture(scope="session")
def docker():
    """Check that docker is available and return the CLI name."""
    docker_path = shutil.which("docker")
    if docker_path is None:
        raise RuntimeError("'docker' is missing or not available in PATH.")
    return "docker"


def pytest_addoption(parser):
    """Add custom CLI options."""
    parser.addoption(
        "--webarena-verified-docker-img",
        action="store",
        default="am1n3e/webarena-verified:latest",
        help="Docker image to test (default: am1n3e/webarena-verified:latest)",
    )
