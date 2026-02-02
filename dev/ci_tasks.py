"""CI helper tasks for automated testing."""

from __future__ import annotations

import platform
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from invoke import task

if TYPE_CHECKING:
    from invoke.context import Context

from dev.utils import logging_utils
from dev.utils.path_utils import get_repo_root


def _get_docker_platform_flag() -> str:
    """Return --platform flag if running on ARM64 (Apple Silicon) to use amd64 images."""
    if platform.machine() in ("arm64", "aarch64"):
        return "--platform linux/amd64 "
    return ""


# CI-specific ZIM file for Wikipedia tests (small ~2.7MB file)
CI_WIKIPEDIA_ZIM_URL = "https://download.kiwix.org/zim/wikipedia/wikipedia_en_ray-charles_maxi_2026-02.zim"
CI_WIKIPEDIA_ZIM_NAME = "wikipedia_en_ray-charles_maxi_2026-02.zim"

# Monaco OSM data URL for map CI tests (~656KB)
MONACO_PBF_URL = "https://download.geofabrik.de/europe/monaco-latest.osm.pbf"
MONACO_PBF_NAME = "monaco-latest.osm.pbf"

# OSRM routing profiles and file naming
# Directory names -> OSRM profile lua file names
OSRM_PROFILES = {"car": "car", "bike": "bicycle", "foot": "foot"}
# Use us-northeast-latest prefix to match supervisord.conf expectations
OSRM_OUTPUT_PREFIX = "us-northeast-latest"


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
      - website/postgres/   (PostgreSQL 14 OSM website data via osmosis)
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
    (output_path / "website").mkdir(parents=True, exist_ok=True)
    for profile in OSRM_PROFILES:
        (output_path / "routing" / profile).mkdir(parents=True, exist_ok=True)

    # Step 1: Download Monaco PBF
    logging_utils.print_info("Step 1/5: Downloading Monaco OSM PBF...")
    if pbf_path.exists():
        logging_utils.print_info(f"  PBF already exists: {pbf_path}")
    else:
        ctx.run(f'curl -L -o "{pbf_path}" "{MONACO_PBF_URL}"')
        logging_utils.print_success(f"  Downloaded: {pbf_path}")

    # Step 2: Generate tile database (PostgreSQL data directory)
    logging_utils.print_info("Step 2/5: Generating tile database...")
    tile_db_path = output_path / "database" / "postgres"
    if tile_db_path.exists() and (tile_db_path / "PG_VERSION").exists():
        logging_utils.print_info(f"  Tile database exists: {tile_db_path}")
    else:
        _generate_tile_database(ctx, output_path, pbf_path)
        logging_utils.print_success(f"  Created: {tile_db_path}")

    # Step 3: Generate OSRM routing data
    logging_utils.print_info("Step 3/5: Processing OSRM routing data...")
    _generate_osrm_data(ctx, output_path, pbf_path)

    # Step 4: Generate Nominatim database (PostgreSQL data directory)
    logging_utils.print_info("Step 4/5: Generating Nominatim database...")
    nominatim_db_path = output_path / "nominatim" / "postgres"
    if nominatim_db_path.exists() and (nominatim_db_path / "PG_VERSION").exists():
        logging_utils.print_info(f"  Nominatim database exists: {nominatim_db_path}")
    else:
        _generate_nominatim_database(ctx, output_path, pbf_path)
        logging_utils.print_success(f"  Created: {nominatim_db_path}")

    # Step 5: Generate website database (PostgreSQL data directory via osmosis)
    logging_utils.print_info("Step 5/5: Generating website database (osmosis)...")
    website_db_path = output_path / "website" / "postgres"
    if website_db_path.exists() and (website_db_path / "PG_VERSION").exists():
        logging_utils.print_info(f"  Website database exists: {website_db_path}")
    else:
        _generate_website_database(ctx, output_path, pbf_path)
        logging_utils.print_success(f"  Created: {website_db_path}")

    # Keep PBF file (may be needed at runtime)
    logging_utils.print_info(f"Keeping PBF file: {pbf_path}")

    logging_utils.print_success(f"Monaco test data generated in: {output_path}")
    logging_utils.print_info("Data structure:")
    logging_utils.print_info("  database/postgres/  - Tile database (PostgreSQL 15)")
    logging_utils.print_info("  nominatim/postgres/ - Nominatim database (PostgreSQL 14)")
    logging_utils.print_info("  website/postgres/   - Website database (PostgreSQL 14, osmosis)")
    logging_utils.print_info("  routing/{car,bike,foot}/ - OSRM routing files")


def _generate_tile_database(ctx: Context, output_path: Path, pbf_path: Path) -> None:
    """Generate PostgreSQL data directory for tile database using the tile server's import."""
    container_name = "map-ci-tile-import"
    tile_db_path = output_path / "database" / "postgres"

    # Clean up any existing data and container
    if tile_db_path.exists():
        shutil.rmtree(tile_db_path)
    ctx.run(f"docker rm -f {container_name} 2>/dev/null || true")

    try:
        # Run tile server import - it exits when complete
        # This downloads external data too (water polygons ~900MB) which takes time
        logging_utils.print_info("  Running tile server import (downloads ~900MB external data)...")
        ctx.run(
            f"docker run --name {container_name} "
            f'-v "{pbf_path}:/data/region.osm.pbf:ro" '
            f"-e THREADS=2 "
            f"-e SKIP_DOWNLOAD=  "
            f"overv/openstreetmap-tile-server import",
            timeout=1800,  # 30 min timeout for download + import
        )

        # Import completed, now we need to restart to copy data
        # Start container again just to access the data
        logging_utils.print_info("  Restarting container to copy data...")
        ctx.run(f"docker start {container_name}")
        ctx.run("sleep 5")

        # Stop PostgreSQL cleanly before copying data
        logging_utils.print_info("  Stopping PostgreSQL...")
        ctx.run(
            f"docker exec {container_name} bash -c '"
            f'su - renderer -c "pg_ctl stop -D /data/database/postgres -m fast" 2>/dev/null || '
            f"pkill -INT postgres || true'",
            warn=True,
        )
        ctx.run("sleep 3")

        # Copy PostgreSQL data directory out of container
        logging_utils.print_info("  Copying database files...")
        ctx.run(f'docker cp {container_name}:/data/database/postgres "{tile_db_path}"')

    finally:
        ctx.run(f"docker rm -f {container_name} 2>/dev/null || true")


def _generate_osrm_data(ctx: Context, output_path: Path, pbf_path: Path) -> None:
    """Generate OSRM routing data for all profiles."""
    osrm_image = "ghcr.io/project-osrm/osrm-backend:v5.27.1"
    # Name the PBF copy to match the expected output prefix (so osrm-extract outputs us-northeast-latest.osrm.*)
    osrm_pbf_name = f"{OSRM_OUTPUT_PREFIX}.osm.pbf"

    for profile_dir_name, profile_lua_name in OSRM_PROFILES.items():
        profile_dir = output_path / "routing" / profile_dir_name
        osrm_marker = profile_dir / f"{OSRM_OUTPUT_PREFIX}.osrm.mldgr"

        # Check if already processed
        if osrm_marker.exists():
            logging_utils.print_info(f"  {profile_dir_name}: Already processed")
            continue

        logging_utils.print_info(f"  {profile_dir_name}: Processing...")

        # Copy PBF with the expected output name (osrm-extract uses input filename for output)
        profile_pbf = profile_dir / osrm_pbf_name
        shutil.copy(pbf_path, profile_pbf)

        # Extract (use the lua profile name, not the directory name)
        ctx.run(
            f'docker run --rm -v "{profile_dir}:/data" {osrm_image} '
            f"osrm-extract -p /opt/{profile_lua_name}.lua /data/{osrm_pbf_name}"
        )

        # Partition
        ctx.run(f'docker run --rm -v "{profile_dir}:/data" {osrm_image} osrm-partition /data/{OSRM_OUTPUT_PREFIX}.osrm')

        # Customize
        ctx.run(f'docker run --rm -v "{profile_dir}:/data" {osrm_image} osrm-customize /data/{OSRM_OUTPUT_PREFIX}.osrm')

        # Clean up PBF copy and intermediate files to save space
        profile_pbf.unlink(missing_ok=True)
        for f in profile_dir.glob("*.osm.pbf"):
            f.unlink(missing_ok=True)

        logging_utils.print_success(f"  {profile_dir_name}: Done")


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
        # Use --platform linux/amd64 on ARM64 Macs since mediagis/nominatim has no arm64 image
        platform_flag = _get_docker_platform_flag()
        logging_utils.print_info("  Starting Nominatim container...")
        ctx.run(
            f"docker run -d --name {container_name} {platform_flag}"
            f'-v "{pbf_path}:/nominatim/data.osm.pbf" '
            f"-e PBF_PATH=/nominatim/data.osm.pbf "
            f"--shm-size=1g "
            f"mediagis/nominatim:4.2"
        )

        # Wait for import to complete (use sudo -u nominatim for peer auth)
        logging_utils.print_info("  Waiting for Nominatim import...")
        ctx.run(
            f"docker exec {container_name} bash -c '"
            f"for i in $(seq 1 300); do "
            f'  if sudo -u nominatim psql -d nominatim -c "SELECT 1" >/dev/null 2>&1; then '
            f'    if sudo -u nominatim psql -d nominatim -c "SELECT 1 FROM placex LIMIT 1" >/dev/null 2>&1; then '
            f'      echo "Import complete"; exit 0; '
            f"    fi; "
            f"  fi; "
            f"  sleep 5; "
            f"done; "
            f'echo "Timeout waiting for import"; exit 1\'',
            timeout=1800,
        )

        # Stop PostgreSQL cleanly before copying data
        logging_utils.print_info("  Stopping PostgreSQL...")
        stop_cmd = (
            "sudo -u postgres pg_ctl stop -D /var/lib/postgresql/14/main -m fast || service postgresql stop || true"
        )
        ctx.run(f"docker exec {container_name} bash -c '{stop_cmd}'")

        # Copy PostgreSQL data directory out of container
        logging_utils.print_info("  Copying database files...")
        ctx.run(f'docker cp {container_name}:/var/lib/postgresql/14/main "{nominatim_db_path}"')

    finally:
        ctx.run(f"docker rm -f {container_name} 2>/dev/null || true")


def _generate_website_database(ctx: Context, output_path: Path, pbf_path: Path) -> None:
    """Generate PostgreSQL data directory for OSM website database using Rails migrations."""
    container_name = "map-ci-website-import"
    website_path = output_path / "website"
    website_db_path = website_path / "postgres"

    # Same commit as used in map Dockerfile
    osm_website_commit = "d4a014d3a6ca3f8f7d03528d39e4707dc256bc60"

    # Clean up any existing data and container
    if website_db_path.exists():
        shutil.rmtree(website_db_path)
    ctx.run(f"docker rm -f {container_name} 2>/dev/null || true")

    try:
        # Use --platform linux/amd64 on ARM64 Macs
        platform_flag = _get_docker_platform_flag()

        # Start PostgreSQL 14 with PostGIS using default postgres superuser
        # The map container entrypoint expects the postgres user to exist
        logging_utils.print_info("  Starting PostgreSQL 14 with PostGIS...")
        ctx.run(
            f"docker run -d --name {container_name} {platform_flag}-e POSTGRES_PASSWORD=postgres postgis/postgis:14-3.3"
        )

        # Wait for PostgreSQL to be ready
        logging_utils.print_info("  Waiting for PostgreSQL to be ready...")
        ctx.run(
            f"docker exec {container_name} bash -c '"
            f"for i in $(seq 1 30); do "
            f"  pg_isready -U postgres >/dev/null 2>&1 && exit 0; "
            f"  sleep 2; "
            f"done; exit 1'",
            timeout=120,
        )

        # Create openstreetmap user and database (as required by OSM website)
        logging_utils.print_info("  Creating openstreetmap user and database...")
        ctx.run(
            f"docker exec {container_name} psql -U postgres -c "
            f"\"CREATE USER openstreetmap WITH PASSWORD 'openstreetmap' CREATEDB;\""
        )
        ctx.run(
            f'docker exec {container_name} psql -U postgres -c "CREATE DATABASE openstreetmap OWNER openstreetmap;"'
        )
        ctx.run(
            f"docker exec {container_name} psql -U postgres -d openstreetmap -c "
            f'"CREATE EXTENSION IF NOT EXISTS postgis;"'
        )
        ctx.run(
            f"docker exec {container_name} psql -U postgres -d openstreetmap -c "
            f'"CREATE EXTENSION IF NOT EXISTS btree_gist;"'
        )

        # Install Ruby and dependencies for Rails migrations
        logging_utils.print_info("  Installing Ruby and dependencies...")
        ctx.run(f"docker exec {container_name} apt-get update -qq")
        ctx.run(
            f"docker exec {container_name} apt-get install -y -qq "
            f"ruby ruby-dev build-essential libpq-dev git libxml2-dev libxslt-dev "
            f"libyaml-dev libffi-dev libssl-dev zlib1g-dev nodejs npm libarchive-dev"
        )
        ctx.run(f"docker exec {container_name} gem install bundler -v 2.4.22 --no-document")

        # Clone OSM website at specific commit
        logging_utils.print_info(f"  Cloning OSM website (commit {osm_website_commit[:8]})...")
        ctx.run(
            f"docker exec {container_name} git clone https://github.com/openstreetmap/openstreetmap-website.git /app"
        )
        ctx.run(f"docker exec -w /app {container_name} git checkout {osm_website_commit}")

        # Configure database.yml
        logging_utils.print_info("  Configuring database...")
        ctx.run(
            f"docker exec {container_name} bash -c '"
            f"cat > /app/config/database.yml << EOF\n"
            f"production:\n"
            f"  adapter: postgresql\n"
            f"  database: openstreetmap\n"
            f"  username: openstreetmap\n"
            f"  password: openstreetmap\n"
            f"  host: localhost\n"
            f"  encoding: utf8\n"
            f"EOF'"
        )

        # Configure storage.yml for Active Storage (required by migrations)
        logging_utils.print_info("  Configuring Active Storage...")
        ctx.run(
            f"docker exec {container_name} bash -c '"
            f"cat > /app/config/storage.yml << EOF\n"
            f"local:\n"
            f"  service: Disk\n"
            f'  root: <%%= Rails.root.join("storage") %%>\n'
            f"EOF'"
        )

        # Install bundle dependencies (minimal for migrations)
        logging_utils.print_info("  Installing bundle dependencies...")
        ctx.run(
            f"docker exec -w /app {container_name} bundle config set --local without 'development test'",
        )
        ctx.run(
            f"docker exec -w /app {container_name} bundle install",
            timeout=600,
        )

        # Run Rails migrations to create the schema
        logging_utils.print_info("  Running Rails migrations...")
        ctx.run(
            f"docker exec -w /app -e RAILS_ENV=production {container_name} bundle exec rails db:migrate",
            timeout=300,
        )

        # Stop PostgreSQL cleanly before copying data
        logging_utils.print_info("  Stopping PostgreSQL...")
        ctx.run(
            f"docker exec {container_name} bash -c '"
            f'su postgres -c "pg_ctl stop -D /var/lib/postgresql/data -m fast" || true\'',
            warn=True,
        )
        ctx.run("sleep 3")

        # Copy PostgreSQL data directory out of container
        logging_utils.print_info("  Copying database files...")
        ctx.run(f'docker cp {container_name}:/var/lib/postgresql/data "{website_db_path}"')

    finally:
        ctx.run(f"docker rm -f {container_name} 2>/dev/null || true")
