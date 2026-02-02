#!/bin/bash
# Import OSM data into the website database (PostgreSQL 14 on port 5433)
#
# Usage:
#   ./import-osm-data.sh <pbf-file> [container-name]
#
# Example:
#   ./import-osm-data.sh us-northeast-latest.osm.pbf osm-website

set -e

PBF_FILE="${1:?Usage: $0 <pbf-file> [container-name]}"
CONTAINER="${2:-osm-website}"

# Database connection settings (PostgreSQL 14 - website database)
DB_HOST="127.0.0.1"
DB_PORT="5433"
DB_NAME="openstreetmap"
DB_USER="openstreetmap"
DB_PASS="openstreetmap"

echo "=== OSM Data Import ==="
echo "PBF file: $PBF_FILE"
echo "Container: $CONTAINER"

# Check if PBF file exists
[ -f "$PBF_FILE" ] || { echo "ERROR: PBF file not found: $PBF_FILE"; exit 1; }

# Check if container is running
docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$" || { echo "ERROR: Container '$CONTAINER' is not running"; exit 1; }

# Copy PBF file into container
echo "Copying PBF file into container..."
docker cp "$PBF_FILE" "$CONTAINER:/tmp/import.osm.pbf"

# Import using osmosis (truncate first, then import)
echo "Importing OSM data..."
echo "Started at: $(date)"
docker exec "$CONTAINER" osmosis \
    --truncate-apidb host="$DB_HOST" port="$DB_PORT" database="$DB_NAME" user="$DB_USER" password="$DB_PASS" \
    --read-pbf file=/tmp/import.osm.pbf \
    --log-progress interval=10 \
    --write-apidb host="$DB_HOST" port="$DB_PORT" database="$DB_NAME" user="$DB_USER" password="$DB_PASS" validateSchemaVersion=no

echo "Finished at: $(date)"

# Cleanup
docker exec "$CONTAINER" rm -f /tmp/import.osm.pbf

# Show final counts
echo ""
echo "=== Import complete ==="
docker exec "$CONTAINER" bash -c "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c \"
SELECT 'nodes' as type, COUNT(*) as count FROM current_nodes
UNION ALL SELECT 'ways', COUNT(*) FROM current_ways
UNION ALL SELECT 'relations', COUNT(*) FROM current_relations;
\""
