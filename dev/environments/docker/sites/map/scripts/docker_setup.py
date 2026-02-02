"""Docker setup for map site.

Sets up Docker volumes for the OpenStreetMap site including:
- Tile database (osm_tile_server.tar)
- Routing data for car/bike/foot (osrm_routing.tar)
- Nominatim geocoding data (nominatim_volumes.tar)

Uses a single container for all download and extraction operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dev.environments.docker.utils import docker_setup_helpers
from dev.environments.settings import get_settings
from dev.utils import logging_utils
from webarena_verified.types.task import WebArenaSite

if TYPE_CHECKING:
    from invoke.context import Context

SITE = WebArenaSite.MAP
SCRIPT_PATH = Path(__file__).parent / "setup_volumes.sh"

# Volumes that need data extraction from tar files (must match setup_volumes.sh)
# Maps volume suffix -> source tar file
VOLUMES_WITH_DATA = {
    "tile-db": "osm_tile_server.tar",
    "routing-car": "osrm_routing.tar",
    "routing-bike": "osrm_routing.tar",
    "routing-foot": "osrm_routing.tar",
    "nominatim-db": "nominatim_volumes.tar",
    "nominatim-flatnode": "nominatim_volumes.tar",
}

# Volumes initialized empty (container populates at runtime)
VOLUMES_EMPTY = [
    "website-db",  # PostgreSQL 14 for OSM website - initialized by entrypoint
    "tiles",  # Tile cache - rendered on demand by renderd
    "style",  # Map style - copied from backup by entrypoint
]

# All volume suffixes
ALL_VOLUME_SUFFIXES = list(VOLUMES_WITH_DATA.keys()) + VOLUMES_EMPTY


def _create_volumes(ctx: Context, volume_prefix: str) -> None:
    """Create all required Docker volumes."""
    for suffix in ALL_VOLUME_SUFFIXES:
        vol_name = docker_setup_helpers.get_volume_name(volume_prefix, SITE.value, suffix)
        docker_setup_helpers.create_volume(ctx, vol_name)


def _build_docker_command(data_dir: Path, volume_prefix: str, data_urls: tuple[str, ...]) -> str:
    """Build docker run command with all volume mounts."""
    # Mount data directory and script
    mounts = [
        f"-v {data_dir}:/data",
        f"-v {SCRIPT_PATH}:/setup.sh:ro",
    ]

    # Mount only volumes that need data extraction
    for suffix in VOLUMES_WITH_DATA:
        vol_name = docker_setup_helpers.get_volume_name(volume_prefix, SITE.value, suffix)
        mounts.append(f"-v {vol_name}:/volumes/{suffix}")

    mount_args = " ".join(mounts)
    urls_str = " ".join(data_urls)

    return f'docker run --rm -e DATA_URLS="{urls_str}" {mount_args} alpine sh /setup.sh'


def _print_dry_run_info(ctx: Context, data_urls: tuple[str, ...], data_dir: Path, volume_prefix: str) -> None:
    """Print what would happen in dry-run mode, checking actual state."""
    # Check which tars exist
    logging_utils.print_info("Downloads:")
    for url in data_urls:
        filename = url.rsplit("/", 1)[-1]
        file_path = data_dir / filename
        if file_path.exists():
            size_gb = file_path.stat().st_size / (1024 * 1024 * 1024)
            logging_utils.print_info(f"  [SKIP] {filename} ({size_gb:.1f}GB exists)")
        else:
            logging_utils.print_info(f"  [DOWNLOAD] {filename}")
            logging_utils.print_info(f"             {url}")

    # Check volumes that need data extraction
    logging_utils.print_info("")
    logging_utils.print_info("Volumes (with data extraction):")
    for suffix, tar_name in VOLUMES_WITH_DATA.items():
        vol_name = docker_setup_helpers.get_volume_name(volume_prefix, SITE.value, suffix)

        if not docker_setup_helpers.volume_exists(ctx, vol_name):
            logging_utils.print_info(f"  [CREATE + EXTRACT] {vol_name} (from {tar_name})")
        elif docker_setup_helpers.volume_is_empty(ctx, vol_name):
            logging_utils.print_info(f"  [EXTRACT] {vol_name} (from {tar_name})")
        else:
            logging_utils.print_info(f"  [SKIP] {vol_name} (has data)")

    # Check empty volumes (container-initialized)
    logging_utils.print_info("")
    logging_utils.print_info("Volumes (container-initialized):")
    for suffix in VOLUMES_EMPTY:
        vol_name = docker_setup_helpers.get_volume_name(volume_prefix, SITE.value, suffix)

        if not docker_setup_helpers.volume_exists(ctx, vol_name):
            logging_utils.print_info(f"  [CREATE] {vol_name}")
        else:
            logging_utils.print_info(f"  [SKIP] {vol_name} (exists)")


def setup(ctx: Context, data_dir: Path, dry_run: bool = False, keep_downloads: bool = False) -> None:
    """Set up map Docker volumes from data files.

    Uses a single container to download missing tars and extract to empty volumes.

    Args:
        ctx: Invoke context for running commands.
        data_dir: Directory to store/find data files.
        dry_run: Show what would be done without doing it.
        keep_downloads: Not used (tars are kept in data_dir for reuse).
    """
    settings = get_settings()
    volume_prefix = settings.volume_prefix
    data_urls = settings.map.data_urls

    if dry_run:
        _print_dry_run_info(ctx, data_urls, data_dir, volume_prefix)
        logging_utils.print_info("")
        logging_utils.print_info("Dry run complete - no changes made")
        return

    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create volumes first (outside container)
    _create_volumes(ctx, volume_prefix)

    # Run setup script in container
    cmd = _build_docker_command(data_dir, volume_prefix, data_urls)
    logging_utils.print_info("Running setup in container...")
    ctx.run(cmd, pty=True)

    logging_utils.print_success("Setup complete!")
