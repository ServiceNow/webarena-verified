"""Settings for Docker image management.

All site-specific settings are defined here and accessed via the site registry.
Environment variables can override defaults using the WA_DEV_ prefix with nested delimiter.

Example environment variables:
    WA_DEV__SHOPPING_ADMIN__HOSTNAME=myhost.local
"""

from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from webarena_verified.types.task import WebArenaSite


class BaseSiteSettings(BaseModel):
    """Base class for site settings with common fields."""

    site: WebArenaSite
    """The WebArena site this settings belongs to."""

    # Docker image settings
    original_docker_img: str
    """Original unoptimized Docker image name."""

    original_docker_url: str | None = None
    """URL to download the original Docker image (tar file)."""

    docker_img: str
    """Optimized Docker image name (from Docker Hub)."""

    base_docker_img: str = ""
    """Base Docker image name for create-base-img output. If empty, not supported."""

    data_dir: str | None = None
    """Optional data directory path for external data files. If None, uses downloads/ at repo root."""

    data_urls: tuple[str, ...] = ()
    """URLs for data files that need to be downloaded (non-Docker artifacts like ZIM files)."""

    dockerfile: str | None = None
    """Path to Dockerfile relative to repo root. Used by the build task."""

    volumes: dict[str, str] = {}
    """Docker volume mounts. Maps volume name to container path."""


class ShoppingSettings(BaseSiteSettings):
    """Settings for the Shopping site."""

    site: WebArenaSite = WebArenaSite.SHOPPING
    original_docker_img: str = "shopping_final_0712"
    original_docker_url: str = "http://metis.lti.cs.cmu.edu/webarena-images/shopping_final_0712.tar"
    docker_img: str = "am1n3e/webarena-verified-shopping"
    base_docker_img: str = "am1n3e/webarena-verified-shopping-base"
    dockerfile: str = "dev/environments/docker/sites/shopping/Dockerfile"


class ShoppingAdminSettings(BaseSiteSettings):
    """Settings for the Shopping Admin site."""

    site: WebArenaSite = WebArenaSite.SHOPPING_ADMIN
    original_docker_img: str = "shopping_admin_final_0719"
    original_docker_url: str = "http://metis.lti.cs.cmu.edu/webarena-images/shopping_admin_final_0719.tar"
    docker_img: str = "am1n3e/webarena-verified-shopping_admin"
    base_docker_img: str = "am1n3e/webarena-verified-shopping-admin-base"
    dockerfile: str = "dev/environments/docker/sites/shopping_admin/Dockerfile"


class RedditSettings(BaseSiteSettings):
    """Settings for the Reddit (Postmill) site."""

    site: WebArenaSite = WebArenaSite.REDDIT
    original_docker_img: str = "postmill-populated-exposed-withimg"
    original_docker_url: str = "http://metis.lti.cs.cmu.edu/webarena-images/postmill-populated-exposed-withimg.tar"
    docker_img: str = "am1n3e/webarena-verified-reddit"
    base_docker_img: str = "am1n3e/webarena-verified-reddit-base"
    dockerfile: str = "dev/environments/docker/sites/reddit/Dockerfile"


class GitlabSettings(BaseSiteSettings):
    """Settings for the GitLab site."""

    site: WebArenaSite = WebArenaSite.GITLAB
    original_docker_img: str = "gitlab-populated-final-port8023"
    original_docker_url: str = "http://metis.lti.cs.cmu.edu/webarena-images/gitlab-populated-final-port8023.tar"
    docker_img: str = "am1n3e/webarena-verified-gitlab"
    base_docker_img: str = "am1n3e/webarena-verified-gitlab-base"
    dockerfile: str = "dev/environments/docker/sites/gitlab/Dockerfile"


class WikipediaSettings(BaseSiteSettings):
    """Settings for the Wikipedia site."""

    site: WebArenaSite = WebArenaSite.WIKIPEDIA
    original_docker_img: str = "ghcr.io/kiwix/kiwix-serve:3.3.0"
    original_docker_url: str | None = None
    docker_img: str = "am1n3e/webarena-verified-wikipedia"
    data_dir: str = "downloads"
    data_urls: tuple[str, ...] = ("http://metis.lti.cs.cmu.edu/webarena-images/wikipedia_en_all_maxi_2022-05.zim",)
    dockerfile: str = "dev/environments/docker/sites/wikipedia/Dockerfile"


class MapSettings(BaseSiteSettings):
    """Settings for the OpenStreetMap site."""

    site: WebArenaSite = WebArenaSite.MAP
    original_docker_img: str = "am1n3e/openstreetmap-website-web:base"
    original_docker_url: str | None = None
    docker_img: str = "am1n3e/webarena-verified-map"
    dockerfile: str = "dev/environments/docker/sites/map/Dockerfile"
    data_urls: tuple[str, ...] = (
        "https://webarena-map-server-data.s3.amazonaws.com/osm_tile_server.tar",
        "https://webarena-map-server-data.s3.amazonaws.com/nominatim_volumes.tar",
        "https://webarena-map-server-data.s3.amazonaws.com/osrm_routing.tar",
    )
    volumes: dict[str, str] = {
        "webarena-verified-map-tile-db": "/data/database",
        "webarena-verified-map-routing-car": "/data/routing/car",
        "webarena-verified-map-routing-bike": "/data/routing/bike",
        "webarena-verified-map-routing-foot": "/data/routing/foot",
        "webarena-verified-map-nominatim-db": "/data/nominatim/postgres",
        "webarena-verified-map-nominatim-flatnode": "/data/nominatim/flatnode",
        "webarena-verified-map-website-db": "/var/lib/postgresql/14/main",
        "webarena-verified-map-tiles": "/data/tiles",
        "webarena-verified-map-style": "/data/style",
    }


class DevSettings(BaseSettings):
    """Development settings for Docker image management."""

    model_config = SettingsConfigDict(env_prefix="WA_DEV__", env_nested_delimiter="__")

    env_ctrl_container_port: int = 8877
    """Standard env-ctrl container port used across all images."""

    env_ctrl_package_path: str = "packages/environment_control/environment_control"
    """Path to environment_control package relative to repo root. Staged to containers during optimization."""

    volume_prefix: str = "webarena-verified"
    """Prefix for Docker volume names (e.g., webarena-verified-map-tile-db)."""

    shopping: ShoppingSettings = ShoppingSettings()
    """Shopping site settings."""

    shopping_admin: ShoppingAdminSettings = ShoppingAdminSettings()
    """Shopping admin site settings."""

    reddit: RedditSettings = RedditSettings()
    """Reddit (forum) site settings."""

    gitlab: GitlabSettings = GitlabSettings()
    """GitLab site settings."""

    wikipedia: WikipediaSettings = WikipediaSettings()
    """Wikipedia site settings."""

    map: MapSettings = MapSettings()
    """OpenStreetMap site settings."""


@lru_cache
def get_settings() -> DevSettings:
    """Get development settings (cached).

    Access site settings via attributes:
        get_settings().shopping_admin
        get_settings().shopping
        get_settings().reddit
        get_settings().gitlab
        get_settings().wikipedia
    """
    return DevSettings()


__all__ = [
    "BaseSiteSettings",
    "DevSettings",
    "GitlabSettings",
    "MapSettings",
    "RedditSettings",
    "ShoppingAdminSettings",
    "ShoppingSettings",
    "WikipediaSettings",
    "get_settings",
]
