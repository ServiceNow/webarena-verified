"""Default container configurations for WebArena sites.

This module provides default Docker container configurations for each WebArena site.
These defaults can be overridden by user configurations in config.json.
"""

from __future__ import annotations

from webarena_verified.types.config import ContainerConfig, ContainerSetupConfig, ContainerVolumeSpec
from webarena_verified.types.task import WebArenaSite

# Default container configurations for all sites
DEFAULT_CONTAINER_CONFIGS: dict[WebArenaSite, ContainerConfig] = {
    WebArenaSite.SHOPPING: ContainerConfig(
        docker_img="am1n3e/webarena-verified-shopping",
        container_port=80,
        env_ctrl_port=8877,
        host_port=7770,
        host_env_ctrl_port=7771,
        health_check_path="/customer/account/login",
    ),
    WebArenaSite.SHOPPING_ADMIN: ContainerConfig(
        docker_img="am1n3e/webarena-verified-shopping_admin",
        container_port=80,
        env_ctrl_port=8877,
        host_port=7780,
        host_env_ctrl_port=7781,
        health_check_path="/",
    ),
    WebArenaSite.REDDIT: ContainerConfig(
        docker_img="am1n3e/webarena-verified-reddit",
        container_port=80,
        env_ctrl_port=8877,
        host_port=9999,
        host_env_ctrl_port=9998,
        health_check_path="/login",
    ),
    WebArenaSite.GITLAB: ContainerConfig(
        docker_img="am1n3e/webarena-verified-gitlab",
        container_port=8023,  # GitLab uses non-standard port
        env_ctrl_port=8877,
        host_port=8023,
        host_env_ctrl_port=8024,
        health_check_path="/users/sign_in",
    ),
    WebArenaSite.WIKIPEDIA: ContainerConfig(
        docker_img="am1n3e/webarena-verified-wikipedia",
        container_port=8080,
        env_ctrl_port=8874,
        host_port=8888,
        host_env_ctrl_port=8889,
        health_check_path="/",
        data_dir_mount="/data",
        setup=ContainerSetupConfig(
            data_urls=("http://metis.lti.cs.cmu.edu/webarena-images/wikipedia_en_all_maxi_2022-05.zim",),
            volumes=(),
        ),
    ),
    WebArenaSite.MAP: ContainerConfig(
        docker_img="am1n3e/webarena-verified-map",
        container_port=8080,
        env_ctrl_port=8877,
        host_port=3000,
        host_env_ctrl_port=3001,
        health_check_path="/",
        setup=ContainerSetupConfig(
            data_urls=(
                "https://webarena-map-server-data.s3.amazonaws.com/osm_tile_server.tar",
                "https://webarena-map-server-data.s3.amazonaws.com/nominatim_volumes.tar",
                "https://webarena-map-server-data.s3.amazonaws.com/osrm_routing.tar",
            ),
            volumes=(
                ContainerVolumeSpec(
                    volume_name="webarena_verified_map_tile_db",
                    mount_path="/data/database",
                    source_tar="osm_tile_server.tar",
                    tar_extract_path="data/database",
                    strip_components=2,
                ),
                ContainerVolumeSpec(
                    volume_name="webarena_verified_map_routing_car",
                    mount_path="/data/routing/car",
                    source_tar="osrm_routing.tar",
                    tar_extract_path="data/routing/car",
                    strip_components=3,
                ),
                ContainerVolumeSpec(
                    volume_name="webarena_verified_map_routing_bike",
                    mount_path="/data/routing/bike",
                    source_tar="osrm_routing.tar",
                    tar_extract_path="data/routing/bike",
                    strip_components=3,
                ),
                ContainerVolumeSpec(
                    volume_name="webarena_verified_map_routing_foot",
                    mount_path="/data/routing/foot",
                    source_tar="osrm_routing.tar",
                    tar_extract_path="data/routing/foot",
                    strip_components=3,
                ),
                ContainerVolumeSpec(
                    volume_name="webarena_verified_map_nominatim_db",
                    mount_path="/data/nominatim/postgres",
                    source_tar="nominatim_volumes.tar",
                    tar_extract_path="data/nominatim/postgres",
                    strip_components=3,
                ),
                ContainerVolumeSpec(
                    volume_name="webarena_verified_map_nominatim_flatnode",
                    mount_path="/data/nominatim/flatnode",
                    source_tar="nominatim_volumes.tar",
                    tar_extract_path="data/nominatim/flatnode",
                    strip_components=3,
                ),
                ContainerVolumeSpec(
                    volume_name="webarena_verified_map_website_db",
                    mount_path="/var/lib/postgresql/14/main",
                ),
                ContainerVolumeSpec(
                    volume_name="webarena_verified_map_tiles",
                    mount_path="/data/tiles",
                ),
                ContainerVolumeSpec(
                    volume_name="webarena_verified_map_style",
                    mount_path="/data/style",
                ),
            ),
        ),
    ),
}


def get_container_config(
    *,
    site: WebArenaSite,
    user_config: ContainerConfig | None = None,
) -> ContainerConfig:
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
