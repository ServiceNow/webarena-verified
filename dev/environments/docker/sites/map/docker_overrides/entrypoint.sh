#!/bin/bash
set -e

# PostgreSQL 14 (website database)
PG14_DATA=/var/lib/postgresql/14/main
PG14_CONFIG=/etc/postgresql/14/main

# PostgreSQL 15 (tile database)
PG15_DATA=/data/database/postgres
PG15_CONFIG=/etc/postgresql/15/main

# Nominatim (geocoding)
NOMINATIM_PG_DATA=/data/nominatim/postgres
NOMINATIM_PG_CONFIG=/etc/postgresql/14/nominatim
NOMINATIM_FLATNODE=/data/nominatim/flatnode
NOMINATIM_PROJECT=/nominatim

# Initialize PostgreSQL 14 (website database) on port 5433
init_postgres_14() {
    echo "=== Initializing PostgreSQL 14 (website) ==="

    # Check if cluster exists (handles mounted empty volume)
    if [ ! -f "$PG14_DATA/PG_VERSION" ]; then
        echo "Initializing PostgreSQL 14 cluster..."
        mkdir -p "$PG14_DATA"
        chown -R postgres: "$PG14_DATA"
        su - postgres -c "/usr/lib/postgresql/14/bin/initdb -D $PG14_DATA"
        echo "host all all 0.0.0.0/0 trust" >> "$PG14_DATA/pg_hba.conf"
    fi

    # Ensure correct ownership and permissions
    chown -R postgres: "$PG14_DATA"
    chmod 700 "$PG14_DATA"

    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D $PG14_DATA -o \"-c config_file=$PG14_CONFIG/postgresql.conf\" start -w"

    # Check if user exists
    if ! su - postgres -c "psql -p 5433 -tAc \"SELECT 1 FROM pg_roles WHERE rolname='openstreetmap'\"" | grep -q 1; then
        echo "Creating openstreetmap user..."
        su - postgres -c "psql -p 5433 -c \"CREATE USER openstreetmap SUPERUSER PASSWORD 'openstreetmap';\""
    fi

    # Check if database exists
    if ! su - postgres -c "psql -p 5433 -tAc \"SELECT 1 FROM pg_database WHERE datname='openstreetmap'\"" | grep -q 1; then
        echo "Creating openstreetmap database..."
        su - postgres -c "createdb -p 5433 -O openstreetmap openstreetmap"
    fi

    # Run migrations if schema not initialized
    cd /app
    if ! su - postgres -c "psql -p 5433 -d openstreetmap -tAc \"SELECT 1 FROM information_schema.tables WHERE table_name='users'\"" | grep -q 1; then
        echo "Running database migrations..."
        bundle exec rails db:migrate
    fi

    echo "Stopping PostgreSQL 14 after initialization..."
    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D $PG14_DATA stop -m fast"
}

# Initialize PostgreSQL 15 (tile database) on port 5432
init_postgres_15() {
    echo "=== Initializing PostgreSQL 15 (tiles) ==="

    # Check if tile data is mounted
    if [ ! -d "$PG15_DATA" ] || [ ! -f "$PG15_DATA/PG_VERSION" ]; then
        echo "WARNING: Tile database not found at $PG15_DATA"
        echo "Mount tile data to /data/database/postgres/ for tile server functionality"
        return 0
    fi

    # Fix ownership and permissions
    chown -R postgres: $PG15_DATA
    chmod 700 $PG15_DATA

    # Update data_directory in postgresql.conf to use mounted data
    sed -i "s|data_directory = '.*'|data_directory = '$PG15_DATA'|" "$PG15_CONFIG/postgresql.conf"

    # Apply custom PostgreSQL config
    if [ -f "$PG15_CONFIG/postgresql.custom.conf.tmpl" ]; then
        cp "$PG15_CONFIG/postgresql.custom.conf.tmpl" "$PG15_CONFIG/conf.d/postgresql.custom.conf"
        echo "autovacuum = on" >> "$PG15_CONFIG/conf.d/postgresql.custom.conf"
    fi

    # Start PG15 temporarily to ensure renderer user exists
    echo "Starting PostgreSQL 15 to verify renderer user..."
    su - postgres -c "/usr/lib/postgresql/15/bin/pg_ctl -D $PG15_DATA -o \"-c config_file=$PG15_CONFIG/postgresql.conf\" start -w"

    # Create renderer user if not exists
    if ! su - postgres -c "psql -p 5432 -tAc \"SELECT 1 FROM pg_roles WHERE rolname='renderer'\"" | grep -q 1; then
        echo "Creating renderer user..."
        su - postgres -c "psql -p 5432 -c \"CREATE USER renderer SUPERUSER PASSWORD 'renderer';\""
    fi

    # Check if gis database exists
    if ! su - postgres -c "psql -p 5432 -tAc \"SELECT 1 FROM pg_database WHERE datname='gis'\"" | grep -q 1; then
        echo "Creating gis database..."
        su - postgres -c "createdb -p 5432 -O renderer gis"
        su - postgres -c "psql -p 5432 -d gis -c 'CREATE EXTENSION IF NOT EXISTS postgis;'"
        su - postgres -c "psql -p 5432 -d gis -c 'CREATE EXTENSION IF NOT EXISTS hstore;'"
    fi

    echo "Stopping PostgreSQL 15 after initialization..."
    su - postgres -c "/usr/lib/postgresql/15/bin/pg_ctl -D $PG15_DATA stop -m fast"

    echo "PostgreSQL 15 tile database ready"
}

# Setup tile server styles
init_tile_styles() {
    echo "=== Initializing tile styles ==="

    # If no custom style mounted, use default osm-carto
    if [ ! "$(ls -A /data/style/ 2>/dev/null)" ]; then
        echo "Copying default OpenStreetMap Carto style..."
        cp -r /home/renderer/src/openstreetmap-carto-backup/* /data/style/
        chown -R renderer: /data/style/
    fi

    # Build mapnik.xml if not present
    if [ ! -f /data/style/mapnik.xml ]; then
        echo "Building mapnik.xml from style..."
        cd /data/style/
        if command -v carto &> /dev/null; then
            carto project.mml > mapnik.xml || echo "WARNING: carto build failed"
        else
            echo "WARNING: carto not installed, skipping mapnik.xml generation"
        fi
    fi

    # Ensure renderd directories exist with correct permissions
    mkdir -p /run/renderd /var/cache/renderd/tiles
    chown -R renderer: /run/renderd /var/cache/renderd
}

# Initialize OSRM routing data
init_osrm_routing() {
    echo "=== Initializing OSRM routing ==="

    local ROUTING_BASE=/data/routing
    local profiles=("car" "bike" "foot")
    local found=0

    for profile in "${profiles[@]}"; do
        local data_file="$ROUTING_BASE/$profile/us-northeast-latest.osrm.mldgr"
        if [ -f "$data_file" ]; then
            echo "OSRM $profile routing data found"
            found=$((found + 1))
        else
            echo "WARNING: OSRM $profile routing data not found at $ROUTING_BASE/$profile/"
        fi
    done

    if [ $found -eq 0 ]; then
        echo "No routing data found. Mount routing data to /data/routing/{car,bike,foot}/"
        echo "Expected files: us-northeast-latest.osrm.* (from osrm_routing.tar)"
    else
        echo "Found $found of 3 routing profiles"
    fi
}

# Patch JS assets to use relative URLs for Nominatim and OSRM
# This fixes the issue where precompiled assets have absolute URLs baked in
# Handles .js, .js.gz (gzip), and .js.br (brotli) files
patch_js_assets() {
    echo "=== Patching JS assets for relative URLs ==="

    local ASSETS_DIR=/app/public/assets
    local patched=0

    # Find JS files that need patching by checking .gz files (fastest to scan)
    for gz_file in "$ASSETS_DIR"/*.js.gz; do
        [ -f "$gz_file" ] || continue

        # Check if file contains the hardcoded URLs
        if zgrep -q "localhost:8080" "$gz_file" 2>/dev/null; then
            local js_file="${gz_file%.gz}"
            local br_file="${js_file}.br"

            # Patch the uncompressed JS file
            if [ -f "$js_file" ]; then
                sed -i 's|http://localhost:8080/nominatim/|/nominatim/|g; s|http://localhost:8080/osrm/|/osrm/|g' "$js_file"

                # Regenerate the gzip file
                gzip -kf "$js_file"

                # Regenerate the brotli file if it exists
                if [ -f "$br_file" ] && command -v brotli &> /dev/null; then
                    brotli -f "$js_file"
                fi

                patched=$((patched + 1))
                echo "Patched: $(basename "$js_file")"
            fi
        fi
    done

    if [ $patched -gt 0 ]; then
        echo "Patched $patched JS asset(s) for relative URLs"
    else
        echo "No JS assets needed patching"
    fi
}

# Initialize Nominatim geocoding database
init_nominatim() {
    echo "=== Initializing Nominatim ==="

    # Check if Nominatim data is mounted
    if [ ! -d "$NOMINATIM_PG_DATA" ] || [ ! -f "$NOMINATIM_PG_DATA/PG_VERSION" ]; then
        echo "WARNING: Nominatim database not found at $NOMINATIM_PG_DATA"
        echo "Mount Nominatim data to /data/nominatim/ for geocoding functionality"
        return 0
    fi

    # Fix ownership and permissions for PostgreSQL data
    # PostgreSQL requires 0700 permissions on data directory
    chown -R postgres: $NOMINATIM_PG_DATA
    chmod 700 $NOMINATIM_PG_DATA

    # Fix ownership for flatnode and project directories
    if [ -d "$NOMINATIM_FLATNODE" ]; then
        chown -R nominatim: $NOMINATIM_FLATNODE
    fi
    chown -R nominatim: $NOMINATIM_PROJECT

    # Update PostgreSQL data directory
    sed -i "s|data_directory = '.*'|data_directory = '$NOMINATIM_PG_DATA'|" "$NOMINATIM_PG_CONFIG/postgresql.conf"

    # Start PostgreSQL for Nominatim temporarily
    echo "Starting PostgreSQL 14 (nominatim) to refresh website..."
    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D $NOMINATIM_PG_DATA -o \"-c config_file=$NOMINATIM_PG_CONFIG/postgresql.conf\" start -w"

    # Copy base nominatim project files if /nominatim is empty
    if [ ! -f "$NOMINATIM_PROJECT/.env" ]; then
        echo "Copying Nominatim project files..."
        cp -a /nominatim-base/. $NOMINATIM_PROJECT/
    fi

    # Configure nominatim to use port 5434
    if ! grep -q "NOMINATIM_DATABASE_DSN" "$NOMINATIM_PROJECT/.env" 2>/dev/null; then
        echo 'NOMINATIM_DATABASE_DSN="pgsql:host=/var/run/postgresql;port=5434;dbname=nominatim"' >> "$NOMINATIM_PROJECT/.env"
    fi
    chown -R nominatim: $NOMINATIM_PROJECT

    # Refresh Nominatim website
    cd $NOMINATIM_PROJECT
    sudo -E -u nominatim nominatim refresh --website --functions 2>&1 || echo "WARNING: Nominatim refresh failed (may need manual setup)"

    # Stop after init (supervisor will restart)
    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D $NOMINATIM_PG_DATA stop -m fast"

    echo "Nominatim initialized"
}

patch_js_assets
init_postgres_14
init_postgres_15
init_nominatim
init_tile_styles
init_osrm_routing

exec "$@"
