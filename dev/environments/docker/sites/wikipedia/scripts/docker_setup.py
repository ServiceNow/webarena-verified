"""Docker setup for wikipedia site.

Sets up Docker volume for Wikipedia containing the ZIM file.
Uses a single container for download and copy operations.
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

SITE = WebArenaSite.WIKIPEDIA
VOLUME_SUFFIX = "data"
SCRIPT_PATH = Path(__file__).parent / "setup_volumes.sh"


def _print_dry_run_info(ctx: Context, data_urls: tuple[str, ...], data_dir: Path, vol_name: str) -> None:
    """Print what would happen in dry-run mode, checking actual state."""
    # Check which files exist
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

    # Check volume state
    logging_utils.print_info("")
    logging_utils.print_info("Volumes:")
    if not docker_setup_helpers.volume_exists(ctx, vol_name):
        logging_utils.print_info(f"  [CREATE + COPY] {vol_name}")
    elif docker_setup_helpers.volume_is_empty(ctx, vol_name):
        logging_utils.print_info(f"  [COPY] {vol_name}")
    else:
        logging_utils.print_info(f"  [SKIP] {vol_name} (has data)")


def setup(ctx: Context, data_dir: Path, dry_run: bool = False, keep_downloads: bool = False) -> None:
    """Set up wikipedia Docker volume from ZIM file.

    Uses a single container to download missing files and copy to empty volume.

    Args:
        ctx: Invoke context for running commands.
        data_dir: Directory to store/find data files.
        dry_run: Show what would be done without doing it.
        keep_downloads: Not used (files are kept in data_dir for reuse).
    """
    settings = get_settings()
    volume_prefix = settings.volume_prefix
    data_urls = settings.wikipedia.data_urls
    vol_name = docker_setup_helpers.get_volume_name(volume_prefix, SITE.value, VOLUME_SUFFIX)

    if dry_run:
        _print_dry_run_info(ctx, data_urls, data_dir, vol_name)
        logging_utils.print_info("")
        logging_utils.print_info("Dry run complete - no changes made")
        return

    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create volume first (outside container)
    docker_setup_helpers.create_volume(ctx, vol_name)

    # Run setup script in container
    urls_str = " ".join(data_urls)
    cmd = (
        f"docker run --rm "
        f'-e DATA_URLS="{urls_str}" '
        f"-v {data_dir}:/data "
        f"-v {SCRIPT_PATH}:/setup.sh:ro "
        f"-v {vol_name}:/volume "
        f"alpine sh /setup.sh"
    )

    logging_utils.print_info("Running setup in container...")
    ctx.run(cmd, pty=True)

    logging_utils.print_success("Setup complete!")
