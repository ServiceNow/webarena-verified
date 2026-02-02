"""Dockerfile parsing utilities."""

import re
from pathlib import Path


def get_container_port(dockerfile_path: str | Path) -> int:
    """Read WA_CONTAINER_PORT from a Dockerfile.

    Parses the Dockerfile for an ENV instruction setting WA_CONTAINER_PORT.

    Args:
        dockerfile_path: Path to the Dockerfile.

    Returns:
        The container port value, or 80 if not defined.
    """
    path = Path(dockerfile_path)
    if not path.exists():
        return 80

    content = path.read_text()
    # Match: ENV WA_CONTAINER_PORT=<value> or ENV WA_CONTAINER_PORT <value>
    match = re.search(r"ENV\s+WA_CONTAINER_PORT[=\s]+(\d+)", content)
    return int(match.group(1)) if match else 80
