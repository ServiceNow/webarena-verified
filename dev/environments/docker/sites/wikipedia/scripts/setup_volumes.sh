#!/bin/sh
# Setup script for wikipedia site volume
# Downloads ZIM file (if missing) and copies to volume (if empty)
#
# Environment variables:
#   DATA_URLS - space-separated list of file URLs to download
#
# Volume mounts expected:
#   /data - directory for downloaded files
#   /volume - target volume for ZIM files

set -e

echo "=== Wikipedia Volume Setup ==="

# Install aria2c for fast parallel downloads
echo "Installing aria2c..."
apk add --no-cache aria2

# Download files if not present
echo ""
echo "=== Downloading files ==="
for url in $DATA_URLS; do
    filename=$(basename "$url")
    if [ -f "/data/$filename" ]; then
        echo "SKIP: $filename already exists"
    else
        echo "Downloading $filename..."
        aria2c -x 16 -s 16 --file-allocation=none -d /data -o "$filename" "$url"
    fi
done

# Copy to volume if empty
echo ""
echo "=== Copying to volume ==="
if [ -n "$(ls -A /volume 2>/dev/null)" ]; then
    echo "SKIP: volume is not empty"
else
    echo "Copying ZIM files to volume..."
    cp /data/*.zim /volume/ 2>/dev/null || echo "No ZIM files to copy"
fi

echo ""
echo "=== Setup complete ==="
