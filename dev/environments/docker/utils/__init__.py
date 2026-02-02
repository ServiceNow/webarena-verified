"""Docker utilities."""

import re

from dev.environments.docker.utils import docker_setup_helpers

# Semver pattern: MAJOR.MINOR.PATCH (e.g., 1.0.0, 2.1.3)
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

__all__ = ["SEMVER_PATTERN", "docker_setup_helpers"]
