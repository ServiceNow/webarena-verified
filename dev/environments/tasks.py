"""Environment management tasks.

Provides:
- envs.sites - List available sites
- envs.docker.* - Docker container and image operations
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from invoke import Collection, task

if TYPE_CHECKING:
    from invoke.context import Context

from dev.environments.docker import ns as docker_ns
from dev.environments.docker.utils.sites import _DOCKER_SITES, _get_container_name

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@task
def sites(ctx: Context) -> None:
    """List all available sites."""
    logger.info("Available sites:")
    for site_enum in sorted(_DOCKER_SITES, key=lambda s: s.value):
        site_name = site_enum.value
        container_name = _get_container_name(site_name)
        logger.info("  %s (container: %s)", site_name, container_name)


# --- Collection ---

ns = Collection()
ns.add_task(sites)  # ty: ignore[invalid-argument-type]

# Add docker sub-namespace
ns.add_collection(docker_ns, name="docker")
