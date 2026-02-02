#!/bin/bash
#
# Image optimization script for Reddit (Postmill) container
# Aggressively compresses images - quality is not critical for this use case
#
set -euo pipefail

BUILD_DRY_RUN="${BUILD_DRY_RUN:-false}"
IMAGE_DIR="/var/www/html/public/submission_images"

# Number of parallel workers (default: all available CPUs)
WORKERS="${WORKERS:-$(nproc 2>/dev/null || echo 4)}"

# Expected file counts (from base image)
TOTAL_GIFS=1166
TOTAL_JPGS=26169
TOTAL_PNGS=4130

if [ "$BUILD_DRY_RUN" = "true" ]; then
    echo "[dry-run] Would optimize images in $IMAGE_DIR"
    exit 0
fi

echo "========================================"
echo "[optimize] Starting aggressive image optimization..."
echo "[optimize] Directory: $IMAGE_DIR"
echo "========================================"

echo "[optimize] Removing media cache..."
rm -rf /var/www/html/public/media/cache/*

# Install optimization tools
echo "[optimize] Installing optimization tools..."
apk add --no-cache gifsicle jpegoptim pngquant parallel

initial_size=$(du -sm "$IMAGE_DIR" 2>/dev/null | cut -f1)
echo "[optimize] Initial size: ${initial_size}MB"

echo "[optimize] Files: ${TOTAL_GIFS} GIFs, ${TOTAL_JPGS} JPEGs, ${TOTAL_PNGS} PNGs"
echo "[optimize] Using ${WORKERS} parallel workers"

# Create helper script for parallel
cat > /tmp/optimize_image.sh << 'EOF'
#!/bin/sh
file="$1"
ext="${file##*.}"
ext_lower=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

case "$ext_lower" in
    jpg|jpeg)
        mogrify -verbose -resize "400x400>" "$file"
        jpegoptim -v --strip-all --max=30 "$file"
        ;;
    png)
        mogrify -verbose -resize "400x400>" "$file"
        pngquant --verbose --force --quality=20-40 --speed 1 --ext .png "$file" || true
        ;;
    gif)
        gifsicle -b -V -O3 --lossy=100 --colors 128 --resize-fit 400x400 "$file" || true
        ;;
esac
EOF
chmod +x /tmp/optimize_image.sh

# Optimize JPEGs: resize with mogrify, then compress with jpegoptim
echo ""
echo "[optimize] Optimizing JPEGs (resize 400x400, quality=30)..."
find "$IMAGE_DIR" -type f \( -iname '*.jpg' -o -iname '*.jpeg' \) -print0 2>/dev/null | \
    parallel -0 -j "$WORKERS" /tmp/optimize_image.sh
echo "[optimize] JPEG optimization complete"

# Optimize PNGs: resize with mogrify, then compress with pngquant
echo ""
echo "[optimize] Optimizing PNGs (resize 400x400, quality=20-40)..."
find "$IMAGE_DIR" -type f -iname '*.png' -print0 2>/dev/null | \
    parallel -0 -j "$WORKERS" /tmp/optimize_image.sh
echo "[optimize] PNG optimization complete"

# Optimize GIFs with gifsicle (resize + aggressive compression)
echo ""
echo "[optimize] Optimizing GIFs (resize 400x400, lossy=100, colors=128)..."
find "$IMAGE_DIR" -type f -iname '*.gif' -print0 2>/dev/null | \
    parallel -0 -j "$WORKERS" /tmp/optimize_image.sh
echo "[optimize] GIF optimization complete"

# Cleanup
echo ""
echo "[optimize] Removing optimization tools..."
apk del gifsicle jpegoptim pngquant parallel 2>/dev/null || true
rm -rf /var/cache/apk/*


final_size=$(du -sm "$IMAGE_DIR" 2>/dev/null | cut -f1)
saved=$((initial_size - final_size))

echo ""
echo "========================================"
echo "[optimize] Image optimization complete"
echo "[optimize] Before: ${initial_size}MB"
echo "[optimize] After:  ${final_size}MB"
echo "[optimize] Saved:  ${saved}MB"
echo "========================================"
