"""Default container configurations for WebArena sites.

This module provides default Docker container configurations for each WebArena site.
These defaults can be overridden by user configurations in config.json.
"""

from __future__ import annotations

from webarena_verified.types.config import ContainerConfig, ContainerSetupConfig, ContainerVolumeSpec
from webarena_verified.types.task import WebArenaSite

# Standard env-ctrl port used across all images
ENV_CTRL_CONTAINER_PORT = 8877

# Volume name prefix for all WebArena containers
VOLUME_PREFIX = "webarena-verified"


def get_volume_name(site: WebArenaSite, suffix: str) -> str:
    """Get full volume name: {prefix}-{site}-{suffix}.

    Args:
        site: WebArena site enum.
        suffix: Volume suffix (e.g., "data", "tile-db").

    Returns:
        Full volume name (e.g., "webarena-verified-wikipedia-data").
    """
    return f"{VOLUME_PREFIX}-{site.value}-{suffix}"


# Default container configurations for all sites
DEFAULT_CONTAINER_CONFIGS: dict[WebArenaSite, ContainerConfig] = {
    WebArenaSite.SHOPPING: ContainerConfig(
        docker_img="am1n3e/webarena-verified-shopping",
        container_port=80,
        env_ctrl_port=ENV_CTRL_CONTAINER_PORT,
    ),
    WebArenaSite.SHOPPING_ADMIN: ContainerConfig(
        docker_img="am1n3e/webarena-verified-shopping_admin",
        container_port=80,
        env_ctrl_port=ENV_CTRL_CONTAINER_PORT,
    ),
    WebArenaSite.REDDIT: ContainerConfig(
        docker_img="am1n3e/webarena-verified-reddit",
        container_port=80,
        env_ctrl_port=ENV_CTRL_CONTAINER_PORT,
    ),
    WebArenaSite.GITLAB: ContainerConfig(
        docker_img="am1n3e/webarena-verified-gitlab",
        container_port=8023,  # GitLab uses non-standard port
        env_ctrl_port=ENV_CTRL_CONTAINER_PORT,
    ),
    WebArenaSite.WIKIPEDIA: ContainerConfig(
        docker_img="am1n3e/webarena-verified-wikipedia",
        container_port=80,
        env_ctrl_port=ENV_CTRL_CONTAINER_PORT,
        volumes={
            f"{VOLUME_PREFIX}-wikipedia-data": "/data",
        },
        setup=ContainerSetupConfig(
            data_urls=("http://metis.lti.cs.cmu.edu/webarena-images/wikipedia_en_all_maxi_2022-05.zim",),
            volumes=(
                ContainerVolumeSpec(
                    suffix="data",
                    mount_path="/data",
                ),
            ),
        ),
    ),
    WebArenaSite.MAP: ContainerConfig(
        docker_img="am1n3e/webarena-verified-map",
        container_port=80,
        env_ctrl_port=ENV_CTRL_CONTAINER_PORT,
        volumes={
            f"{VOLUME_PREFIX}-map-tile-db": "/data/database",
            f"{VOLUME_PREFIX}-map-routing-car": "/data/routing/car",
            f"{VOLUME_PREFIX}-map-routing-bike": "/data/routing/bike",
            f"{VOLUME_PREFIX}-map-routing-foot": "/data/routing/foot",
            f"{VOLUME_PREFIX}-map-nominatim-db": "/data/nominatim/postgres",
            f"{VOLUME_PREFIX}-map-nominatim-flatnode": "/data/nominatim/flatnode",
            f"{VOLUME_PREFIX}-map-website-db": "/var/lib/postgresql/14/main",
            f"{VOLUME_PREFIX}-map-tiles": "/data/tiles",
            f"{VOLUME_PREFIX}-map-style": "/data/style",
        },
        setup=ContainerSetupConfig(
            data_urls=(
                "https://webarena-map-server-data.s3.amazonaws.com/osm_tile_server.tar",
                "https://webarena-map-server-data.s3.amazonaws.com/nominatim_volumes.tar",
                "https://webarena-map-server-data.s3.amazonaws.com/osrm_routing.tar",
            ),
            volumes=(
                # Volumes with data extraction from tars
                ContainerVolumeSpec(
                    suffix="tile-db",
                    mount_path="/data/database",
                    source_tar="osm_tile_server.tar",
                    tar_extract_path="data/database",
                    strip_components=2,
                ),
                ContainerVolumeSpec(
                    suffix="routing-car",
                    mount_path="/data/routing/car",
                    source_tar="osrm_routing.tar",
                    tar_extract_path="data/routing/car",
                    strip_components=3,
                ),
                ContainerVolumeSpec(
                    suffix="routing-bike",
                    mount_path="/data/routing/bike",
                    source_tar="osrm_routing.tar",
                    tar_extract_path="data/routing/bike",
                    strip_components=3,
                ),
                ContainerVolumeSpec(
                    suffix="routing-foot",
                    mount_path="/data/routing/foot",
                    source_tar="osrm_routing.tar",
                    tar_extract_path="data/routing/foot",
                    strip_components=3,
                ),
                ContainerVolumeSpec(
                    suffix="nominatim-db",
                    mount_path="/data/nominatim/postgres",
                    source_tar="nominatim_volumes.tar",
                    tar_extract_path="data/nominatim/postgres",
                    strip_components=3,
                ),
                ContainerVolumeSpec(
                    suffix="nominatim-flatnode",
                    mount_path="/data/nominatim/flatnode",
                    source_tar="nominatim_volumes.tar",
                    tar_extract_path="data/nominatim/flatnode",
                    strip_components=3,
                ),
                # Empty volumes (initialized by container at runtime)
                ContainerVolumeSpec(
                    suffix="website-db",
                    mount_path="/var/lib/postgresql/14/main",
                ),
                ContainerVolumeSpec(
                    suffix="tiles",
                    mount_path="/data/tiles",
                ),
                ContainerVolumeSpec(
                    suffix="style",
                    mount_path="/data/style",
                ),
            ),
        ),
    ),
}


def get_container_config(site: WebArenaSite, user_config: ContainerConfig | None = None) -> ContainerConfig:
    """Get container config, using user override if provided.

    Args:
        site: WebArena site to get config for.
        user_config: Optional user-provided container config override.

    Returns:
        ContainerConfig for the site.

    Raises:
        ValueError: If site is not supported (HOMEPAGE) and no user config provided.
    """
    if user_config is not None:
        return user_config

    if site not in DEFAULT_CONTAINER_CONFIGS:
        raise ValueError(f"No default container config for site {site.value}. Site may not support Docker deployment.")

    return DEFAULT_CONTAINER_CONFIGS[site]


def get_sites_with_setup() -> list[WebArenaSite]:
    """Get list of sites that require setup (have data files to download).

    Returns:
        List of WebArenaSite values that have setup configuration.
    """
    return [
        site
        for site, config in DEFAULT_CONTAINER_CONFIGS.items()
        if config.setup is not None and config.setup.data_urls
    ]


__all__ = [
    "DEFAULT_CONTAINER_CONFIGS",
    "ENV_CTRL_CONTAINER_PORT",
    "VOLUME_PREFIX",
    "get_container_config",
    "get_sites_with_setup",
    "get_volume_name",
]
