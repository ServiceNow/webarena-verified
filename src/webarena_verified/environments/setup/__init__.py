"""Setup utilities for WebArena Docker environments.

This package provides functions for setting up Docker volumes with data
required by WebArena sites (wikipedia, map) and cleaning up those volumes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from webarena_verified.types.task import WebArenaSite

from ..container.config import get_container_config, get_sites_with_setup
from .docker_ops import (
    copy_file_to_volume,
    create_volume,
    download_file,
    extract_tar_to_volume,
    remove_volume,
    volume_exists,
    volume_is_empty,
)

if TYPE_CHECKING:
    from pathlib import Path

# Type for progress callbacks
ProgressCallback = Callable[[str, str], None]  # (phase, message)


def _print_default(phase: str, message: str) -> None:
    """Default progress callback that prints to stdout."""
    print(f"[{phase}] {message}")


def setup_init(  # noqa: C901, PLR0912, PLR0915
    *,
    site: WebArenaSite | None,
    data_dir: Path,
    dry_run: bool = False,
    progress: ProgressCallback | None = None,
) -> dict[str, list[str]]:
    """Initialize Docker volumes for a site (or all sites).

    Downloads required data files and sets up Docker volumes with the data.
    Operations are idempotent: existing files won't be re-downloaded and
    non-empty volumes won't be overwritten.

    Args:
        site: Site to initialize, or None for all sites requiring setup.
        data_dir: Directory to store/find downloaded data files.
        dry_run: If True, show what would be done without making changes.
        progress: Optional callback for progress messages.

    Returns:
        Dict with keys:
            - "downloads": List of files downloaded
            - "volumes_created": List of volumes created
            - "volumes_populated": List of volumes that were populated with data
            - "skipped": List of operations skipped (file/volume already exists)

    Raises:
        ValueError: If site doesn't support setup.
        RuntimeError: If setup fails.
    """
    if progress is None:
        progress = _print_default

    # Determine which sites to set up
    if site is not None:
        sites = [site]
    else:
        sites = get_sites_with_setup()

    result: dict[str, list[str]] = {
        "downloads": [],
        "volumes_created": [],
        "volumes_populated": [],
        "skipped": [],
    }

    for s in sites:
        config = get_container_config(site=s)
        if config.setup is None or not config.setup.data_urls:
            if site is not None:
                raise ValueError(f"Site {s.value} doesn't require setup (no data files to download)")
            continue

        progress("SITE", f"Setting up {s.value}")

        # Ensure data directory exists
        data_dir.mkdir(parents=True, exist_ok=True)

        # Download data files
        for url in config.setup.data_urls:
            filename = url.rsplit("/", 1)[-1]
            file_path = data_dir / filename

            if file_path.exists():
                progress("SKIP", f"File exists: {filename}")
                result["skipped"].append(f"download:{filename}")
            else:
                if dry_run:
                    progress("DRY-RUN", f"Would download: {url}")
                else:
                    progress("DOWNLOAD", f"Downloading {filename}...")
                    download_file(url, data_dir, filename)
                    result["downloads"].append(filename)

        # Set up volumes
        for vol_spec in config.setup.volumes:
            vol_name = vol_spec.volume_name

            # Create volume if needed
            if not volume_exists(vol_name):
                if dry_run:
                    progress("DRY-RUN", f"Would create volume: {vol_name}")
                else:
                    progress("CREATE", f"Creating volume: {vol_name}")
                    create_volume(vol_name)
                    result["volumes_created"].append(vol_name)
            else:
                progress("SKIP", f"Volume exists: {vol_name}")
                result["skipped"].append(f"create:{vol_name}")

            # Populate volume if empty
            if not dry_run and volume_exists(vol_name) and volume_is_empty(vol_name):
                if vol_spec.source_tar:
                    # Extract from tar file
                    tar_path = data_dir / vol_spec.source_tar
                    if tar_path.exists():
                        progress("EXTRACT", f"Extracting to {vol_name}...")
                        extract_tar_to_volume(
                            tar_path,
                            vol_name,
                            extract_path=vol_spec.tar_extract_path,
                            strip_components=vol_spec.strip_components,
                        )
                        result["volumes_populated"].append(vol_name)
                    else:
                        progress("WARN", f"Tar file not found: {vol_spec.source_tar}")
                elif s == WebArenaSite.WIKIPEDIA and vol_name.endswith("_data"):
                    # Special case: Wikipedia copies ZIM file directly
                    zim_files = list(data_dir.glob("*.zim"))
                    if zim_files:
                        progress("COPY", f"Copying ZIM file to {vol_name}...")
                        copy_file_to_volume(zim_files[0], vol_name)
                        result["volumes_populated"].append(vol_name)
            elif dry_run and vol_spec.source_tar:
                if volume_exists(vol_name) and not volume_is_empty(vol_name):
                    progress("DRY-RUN", f"Would skip (has data): {vol_name}")
                else:
                    progress("DRY-RUN", f"Would extract to: {vol_name}")

    if dry_run:
        progress("DONE", "Dry run complete - no changes made")
    else:
        progress("DONE", "Setup complete")

    return result


def setup_clean(  # noqa: C901
    *,
    site: WebArenaSite | None,
    force: bool = False,
    progress: ProgressCallback | None = None,
) -> dict[str, list[str]]:
    """Remove Docker volumes for a site (or all sites).

    Args:
        site: Site to clean, or None for all sites.
        force: If False, prompt for confirmation before removing.
        progress: Optional callback for progress messages.

    Returns:
        Dict with keys:
            - "removed": List of volumes removed
            - "failed": List of volumes that failed to remove (e.g., in use)

    Raises:
        SystemExit: If user declines confirmation (only when force=False).
    """
    if progress is None:
        progress = _print_default

    # Determine which sites to clean
    if site is not None:
        sites = [site]
    else:
        sites = get_sites_with_setup()

    # Collect volumes to remove
    volumes_to_remove: list[str] = []
    for s in sites:
        config = get_container_config(site=s)
        if config.setup is None:
            continue

        for vol_spec in config.setup.volumes:
            if volume_exists(vol_spec.volume_name):
                volumes_to_remove.append(vol_spec.volume_name)

    if not volumes_to_remove:
        progress("INFO", "No volumes found to remove")
        return {"removed": [], "failed": []}

    # Confirmation prompt
    if not force:
        print(f"\nThis will remove {len(volumes_to_remove)} volume(s):")
        for vol in volumes_to_remove:
            print(f"  - {vol}")
        try:
            response = input("\nContinue? [y/N]: ").strip().lower()
        except EOFError:
            response = "n"

        if response not in ("y", "yes"):
            progress("ABORT", "Cleanup aborted")
            raise SystemExit(0)

    # Remove volumes
    result: dict[str, list[str]] = {"removed": [], "failed": []}
    for vol_name in volumes_to_remove:
        try:
            progress("REMOVE", f"Removing {vol_name}...")
            remove_volume(vol_name)
            result["removed"].append(vol_name)
        except RuntimeError as e:
            progress("ERROR", f"Failed to remove {vol_name}: {e}")
            result["failed"].append(vol_name)

    progress("DONE", f"Removed {len(result['removed'])} volume(s)")
    return result


def list_site_volumes(*, site: WebArenaSite | None = None) -> dict[str, list[str]]:
    """List Docker volumes for a site (or all sites).

    Args:
        site: Site to list volumes for, or None for all.

    Returns:
        Dict mapping site name to list of existing volume names.
    """
    sites = [site] if site is not None else get_sites_with_setup()
    result: dict[str, list[str]] = {}

    for s in sites:
        config = get_container_config(site=s)
        if config.setup is None:
            continue

        volumes: list[str] = []
        for vol_spec in config.setup.volumes:
            if volume_exists(vol_spec.volume_name):
                volumes.append(vol_spec.volume_name)

        if volumes:
            result[s.value] = volumes

    return result


__all__ = [
    "list_site_volumes",
    "setup_clean",
    "setup_init",
]
