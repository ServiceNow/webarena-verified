#!/bin/bash
#
# Image optimization script for Shopping Admin (Magento) container
# Resizes and compresses product catalog images using mogrify
#
set -euo pipefail

BUILD_DRY_RUN="${BUILD_DRY_RUN:-false}"
IMAGE_DIR="/var/www/magento2/pub/media/catalog/product"

if [ "$BUILD_DRY_RUN" = "true" ]; then
    echo "[dry-run] Would optimize JPEG images in $IMAGE_DIR"
    exit 0
fi
IMAGE_MAX_SIZE="400x400>"
JPEG_QUALITY=60
THREADS=$(nproc 2>/dev/null || echo 4)

echo "========================================"
echo "[optimize] Starting image optimization..."
echo "[optimize] Directory: $IMAGE_DIR"
echo "[optimize] Max size: $IMAGE_MAX_SIZE"
echo "[optimize] Quality: $JPEG_QUALITY"
echo "[optimize] Threads: $THREADS"
echo "========================================"

echo "[optimize] Removing product image cache..."
rm -rf /var/www/magento2/pub/media/catalog/product/cache
install -d -o www-data -g www-data -m 2775 /var/www/magento2/pub/media/catalog/product/cache

if ! command -v parallel &> /dev/null; then
    echo "[optimize] Installing GNU parallel..."
    apk add --no-cache parallel || true
fi

echo "[optimize] Running mogrify..."
find "$IMAGE_DIR" -type f \( -iname '*.jpg' -o -iname '*.jpeg' \) -print0 2>/dev/null | \
    parallel -0 -n 50 -j "$THREADS" "mogrify -resize '$IMAGE_MAX_SIZE' -quality $JPEG_QUALITY -strip {} && printf '.'" 2>/dev/null || true
echo

echo "========================================"
echo "[optimize] Done"
echo "========================================"
