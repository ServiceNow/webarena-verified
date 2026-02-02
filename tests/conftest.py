"""Pytest configuration for all tests."""


def pytest_addoption(parser):
    """Add custom CLI options."""
    parser.addoption(
        "--webarena-verified-docker-img",
        action="store",
        default="am1n3e/webarena-verified:latest",
        help="Docker image to test (default: am1n3e/webarena-verified:latest)",
    )
