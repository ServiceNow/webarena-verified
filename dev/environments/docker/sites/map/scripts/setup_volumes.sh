#!/bin/sh
# Setup script for map site volumes
# Downloads tars (if missing) and extracts to volumes (if empty)
#
# Environment variables:
#   DATA_URLS - space-separated list of tar URLs to download
#
# Volume mounts expected:
#   /data - directory for tar files
#   /volumes/tile-db
#   /volumes/routing-car
#   /volumes/routing-bike
#   /volumes/routing-foot
#   /volumes/nominatim-db
#   /volumes/nominatim-flatnode

set -e

echo "=== Map Volume Setup ==="

# Install aria2c for fast parallel downloads
echo "Installing aria2c..."
apk add --no-cache aria2

# Download tars if not present
echo ""
echo "=== Downloading tars ==="
for url in $DATA_URLS; do
    filename=$(basename "$url")
    if [ -f "/data/$filename" ]; then
        echo "SKIP: $filename already exists"
    else
        echo "Downloading $filename..."
        aria2c -x 16 -s 16 --file-allocation=none -d /data -o "$filename" "$url"
    fi
done

# Extract to volumes if empty
echo ""
echo "=== Extracting to volumes ==="

# tile-db from osm_tile_server.tar
if [ -n "$(ls -A /volumes/tile-db 2>/dev/null)" ]; then
    echo "SKIP: tile-db is not empty"
else
    echo "Extracting tile-db..."
    tar -xf /data/osm_tile_server.tar -C /volumes/tile-db \
        --strip-components=6 'projects/ogma3/docker/volumes/osm-data/_data'
fi

# routing-car from osrm_routing.tar
if [ -n "$(ls -A /volumes/routing-car 2>/dev/null)" ]; then
    echo "SKIP: routing-car is not empty"
else
    echo "Extracting routing-car..."
    tar -xf /data/osrm_routing.tar -C /volumes/routing-car --strip-components=1 'car'
fi

# routing-bike from osrm_routing.tar
if [ -n "$(ls -A /volumes/routing-bike 2>/dev/null)" ]; then
    echo "SKIP: routing-bike is not empty"
else
    echo "Extracting routing-bike..."
    tar -xf /data/osrm_routing.tar -C /volumes/routing-bike --strip-components=1 'bike'
fi

# routing-foot from osrm_routing.tar
if [ -n "$(ls -A /volumes/routing-foot 2>/dev/null)" ]; then
    echo "SKIP: routing-foot is not empty"
else
    echo "Extracting routing-foot..."
    tar -xf /data/osrm_routing.tar -C /volumes/routing-foot --strip-components=1 'foot'
fi

# nominatim-db from nominatim_volumes.tar
# Path: projects/metis2/docker/docker/volumes/nominatim-data/_data (7 components)
if [ -n "$(ls -A /volumes/nominatim-db 2>/dev/null)" ]; then
    echo "SKIP: nominatim-db is not empty"
else
    echo "Extracting nominatim-db..."
    tar -xf /data/nominatim_volumes.tar -C /volumes/nominatim-db \
        --strip-components=7 'projects/metis2/docker/docker/volumes/nominatim-data/_data'
fi

# nominatim-flatnode from nominatim_volumes.tar
# Path: projects/metis2/docker/docker/volumes/nominatim-flatnode/_data (7 components)
if [ -n "$(ls -A /volumes/nominatim-flatnode 2>/dev/null)" ]; then
    echo "SKIP: nominatim-flatnode is not empty"
else
    echo "Extracting nominatim-flatnode..."
    tar -xf /data/nominatim_volumes.tar -C /volumes/nominatim-flatnode \
        --strip-components=7 'projects/metis2/docker/docker/volumes/nominatim-flatnode/_data'
fi

echo ""
echo "=== Setup complete ==="
