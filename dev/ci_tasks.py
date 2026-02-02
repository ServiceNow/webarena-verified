"""CI helper tasks for automated testing."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from invoke import task

if TYPE_CHECKING:
    from invoke.context import Context

from dev.utils import logging_utils
from dev.utils.path_utils import get_repo_root

# CI-specific ZIM file for Wikipedia tests (small ~2.7MB file)
CI_WIKIPEDIA_ZIM_URL = "https://download.kiwix.org/zim/wikipedia/wikipedia_en_ray-charles_maxi_2026-02.zim"
CI_WIKIPEDIA_ZIM_NAME = "wikipedia_en_ray-charles_maxi_2026-02.zim"

# Monaco OSM data URL for map CI tests (~656KB)
MONACO_PBF_URL = "https://download.geofabrik.de/europe/monaco-latest.osm.pbf"
MONACO_PBF_NAME = "monaco-latest.osm.pbf"

# OSRM routing profiles and file naming
OSRM_PROFILES = ("car", "bike", "foot")
MONACO_OSRM_PREFIX = "monaco"  # Output files will be monaco.osrm.*


@task(name="setup-wikipedia")
@logging_utils.with_banner()
def setup_wikipedia(ctx: Context, output_dir: str | None = None) -> None:
    """Download tiny Wikipedia ZIM file for CI testing.

    Downloads the Ray Charles ZIM (~2.7MB) instead of the full Wikipedia (~100GB).
    The ZIM file is saved to the output directory for mounting at runtime.

    Args:
        output_dir: Directory to save the ZIM file (default: data/wikipedia at repo root).
    """
    repo_root = get_repo_root()
    default_dir = repo_root / "data" / "wikipedia"
    target_dir = Path(output_dir) if output_dir else default_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    zim_path = target_dir / CI_WIKIPEDIA_ZIM_NAME

    if zim_path.exists():
        logging_utils.print_info(f"ZIM file already exists: {zim_path}")
        return

    logging_utils.print_info("Downloading CI Wikipedia ZIM file...")
    logging_utils.print_info(f"  URL: {CI_WIKIPEDIA_ZIM_URL}")
    logging_utils.print_info(f"  To:  {zim_path}")

    ctx.run(f'curl -L -o "{zim_path}" "{CI_WIKIPEDIA_ZIM_URL}"')

    logging_utils.print_success(f"Downloaded: {zim_path}")


# ==============================================================================
# Map CI Tasks (Monaco test data)
# ==============================================================================


@task(name="generate-map-data")
@logging_utils.with_banner()
def generate_map_data(ctx: Context, output_dir: str | None = None) -> None:
    """Generate Monaco test data for map CI using Docker containers.

    Produces volume-ready data that can be mounted directly by the map container.
    The output structure matches what the map entrypoint expects:
      - database/postgres/  (PostgreSQL 15 tile data)
      - nominatim/postgres/ (PostgreSQL 14 Nominatim data)
      - routing/{car,bike,foot}/ (OSRM routing files)

    This data can be cached in CI (GitHub Actions cache) for fast subsequent runs.

    Args:
        output_dir: Directory to save generated data (default: data/map at repo root).
    """
    repo_root = get_repo_root()
    default_dir = repo_root / "data" / "map"
    output_path = Path(output_dir).resolve() if output_dir else default_dir
    output_path.mkdir(parents=True, exist_ok=True)

    pbf_path = output_path / MONACO_PBF_NAME

    # Create subdirectories matching map container volume structure
    (output_path / "database").mkdir(parents=True, exist_ok=True)
    (output_path / "nominatim").mkdir(parents=True, exist_ok=True)
    for profile in OSRM_PROFILES:
        (output_path / "routing" / profile).mkdir(parents=True, exist_ok=True)

    # Step 1: Download Monaco PBF
    logging_utils.print_info("Step 1/4: Downloading Monaco OSM PBF...")
    if pbf_path.exists():
        logging_utils.print_info(f"  PBF already exists: {pbf_path}")
    else:
        ctx.run(f'curl -L -o "{pbf_path}" "{MONACO_PBF_URL}"')
        logging_utils.print_success(f"  Downloaded: {pbf_path}")

    # Step 2: Generate tile database (PostgreSQL data directory)
    logging_utils.print_info("Step 2/4: Generating tile database...")
    tile_db_path = output_path / "database" / "postgres"
    if tile_db_path.exists() and (tile_db_path / "PG_VERSION").exists():
        logging_utils.print_info(f"  Tile database exists: {tile_db_path}")
    else:
        _generate_tile_database(ctx, output_path, pbf_path)
        logging_utils.print_success(f"  Created: {tile_db_path}")

    # Step 3: Generate OSRM routing data
    logging_utils.print_info("Step 3/4: Processing OSRM routing data...")
    _generate_osrm_data(ctx, output_path, pbf_path)

    # Step 4: Generate Nominatim database (PostgreSQL data directory)
    logging_utils.print_info("Step 4/4: Generating Nominatim database...")
    nominatim_db_path = output_path / "nominatim" / "postgres"
    if nominatim_db_path.exists() and (nominatim_db_path / "PG_VERSION").exists():
        logging_utils.print_info(f"  Nominatim database exists: {nominatim_db_path}")
    else:
        _generate_nominatim_database(ctx, output_path, pbf_path)
        logging_utils.print_success(f"  Created: {nominatim_db_path}")

    # Clean up PBF file to save space in cache
    if pbf_path.exists():
        pbf_path.unlink()
        logging_utils.print_info("Cleaned up PBF file to save cache space")

    logging_utils.print_success(f"Monaco test data generated in: {output_path}")
    logging_utils.print_info("Data structure:")
    logging_utils.print_info("  database/postgres/  - Tile database (PostgreSQL 15)")
    logging_utils.print_info("  nominatim/postgres/ - Nominatim database (PostgreSQL 14)")
    logging_utils.print_info("  routing/{car,bike,foot}/ - OSRM routing files")


def _generate_tile_database(ctx: Context, output_path: Path, pbf_path: Path) -> None:
    """Generate PostgreSQL data directory for tile database using osm2pgsql."""
    container_name = "map-ci-tile-import"
    tile_db_path = output_path / "database" / "postgres"

    # Clean up any existing data and container
    if tile_db_path.exists():
        shutil.rmtree(tile_db_path)
    ctx.run(f"docker rm -f {container_name} 2>/dev/null || true")

    try:
        # Start tile server container in import mode
        logging_utils.print_info("  Starting tile server container...")
        ctx.run(f"docker run -d --name {container_name} -e THREADS=2 overv/openstreetmap-tile-server:2.4.0 import")

        # Wait for PostgreSQL to be ready
        logging_utils.print_info("  Waiting for PostgreSQL to start...")
        ctx.run(
            f"docker exec {container_name} bash -c "
            f"'for i in $(seq 1 60); do pg_isready -U renderer -d gis && break || sleep 2; done'"
        )

        # Copy PBF file into container
        ctx.run(f'docker cp "{pbf_path}" {container_name}:/data/region.osm.pbf')

        # Import using osm2pgsql
        logging_utils.print_info("  Importing OSM data with osm2pgsql...")
        ctx.run(
            f"docker exec {container_name} osm2pgsql -d gis "
            f"--create --slim -G --hstore "
            f"-S /home/renderer/src/openstreetmap-carto/openstreetmap-carto.style "
            f"--tag-transform-script /home/renderer/src/openstreetmap-carto/openstreetmap-carto.lua "
            f"-C 512 /data/region.osm.pbf"
        )

        # Create indexes
        logging_utils.print_info("  Creating indexes...")
        ctx.run(
            f"docker exec {container_name} bash -c "
            f"'cd /home/renderer/src/openstreetmap-carto && "
            f"psql -d gis -f indexes.sql 2>/dev/null || true'"
        )

        # Stop PostgreSQL cleanly before copying data
        logging_utils.print_info("  Stopping PostgreSQL...")
        ctx.run(f"docker exec {container_name} su - renderer -c 'pg_ctl stop -D /data/database/postgres -m fast'")

        # Copy PostgreSQL data directory out of container
        logging_utils.print_info("  Copying database files...")
        ctx.run(f'docker cp {container_name}:/data/database/postgres "{tile_db_path}"')

    finally:
        ctx.run(f"docker rm -f {container_name} 2>/dev/null || true")


def _generate_osrm_data(ctx: Context, output_path: Path, pbf_path: Path) -> None:
    """Generate OSRM routing data for all profiles."""
    osrm_image = "ghcr.io/project-osrm/osrm-backend:v5.27.1"

    for profile in OSRM_PROFILES:
        profile_dir = output_path / "routing" / profile
        osrm_marker = profile_dir / f"{MONACO_OSRM_PREFIX}.osrm.mldgr"

        # Check if already processed
        if osrm_marker.exists():
            logging_utils.print_info(f"  {profile}: Already processed")
            continue

        logging_utils.print_info(f"  {profile}: Processing...")

        # Copy PBF to profile directory for processing
        profile_pbf = profile_dir / MONACO_PBF_NAME
        shutil.copy(pbf_path, profile_pbf)

        # Extract
        ctx.run(
            f'docker run --rm -v "{profile_dir}:/data" {osrm_image} '
            f"osrm-extract -p /opt/{profile}.lua /data/{MONACO_PBF_NAME}"
        )

        # Partition
        ctx.run(f'docker run --rm -v "{profile_dir}:/data" {osrm_image} osrm-partition /data/{MONACO_OSRM_PREFIX}.osrm')

        # Customize
        ctx.run(f'docker run --rm -v "{profile_dir}:/data" {osrm_image} osrm-customize /data/{MONACO_OSRM_PREFIX}.osrm')

        # Clean up PBF copy and intermediate files to save space
        profile_pbf.unlink(missing_ok=True)
        for f in profile_dir.glob("*.osm.pbf"):
            f.unlink(missing_ok=True)

        logging_utils.print_success(f"  {profile}: Done")


def _generate_nominatim_database(ctx: Context, output_path: Path, pbf_path: Path) -> None:
    """Generate PostgreSQL data directory for Nominatim database."""
    container_name = "map-ci-nominatim-import"
    nominatim_path = output_path / "nominatim"
    nominatim_db_path = nominatim_path / "postgres"

    # Clean up any existing data and container
    if nominatim_db_path.exists():
        shutil.rmtree(nominatim_db_path)
    ctx.run(f"docker rm -f {container_name} 2>/dev/null || true")

    try:
        # Start Nominatim container with import mode
        logging_utils.print_info("  Starting Nominatim container...")
        ctx.run(
            f"docker run -d --name {container_name} "
            f'-v "{pbf_path}:/nominatim/data.osm.pbf:ro" '
            f"-e PBF_PATH=/nominatim/data.osm.pbf "
            f"--shm-size=1g "
            f"mediagis/nominatim:4.2"
        )

        # Wait for import to complete
        logging_utils.print_info("  Waiting for Nominatim import...")
        ctx.run(
            f"docker exec {container_name} bash -c '"
            f"for i in $(seq 1 300); do "
            f'  if psql -U nominatim -d nominatim -c "SELECT 1" >/dev/null 2>&1; then '
            f'    if psql -U nominatim -d nominatim -c "SELECT 1 FROM placex LIMIT 1" >/dev/null 2>&1; then '
            f'      echo "Import complete"; exit 0; '
            f"    fi; "
            f"  fi; "
            f"  sleep 5; "
            f"done; "
            f'echo "Timeout waiting for import"; exit 1\''
        )

        # Stop PostgreSQL cleanly before copying data
        logging_utils.print_info("  Stopping PostgreSQL...")
        ctx.run(f"docker exec {container_name} bash -c 'pg_ctl stop -D /var/lib/postgresql/14/main -m fast || true'")

        # Copy PostgreSQL data directory out of container
        logging_utils.print_info("  Copying database files...")
        ctx.run(f'docker cp {container_name}:/var/lib/postgresql/14/main "{nominatim_db_path}"')

    finally:
        ctx.run(f"docker rm -f {container_name} 2>/dev/null || true")
