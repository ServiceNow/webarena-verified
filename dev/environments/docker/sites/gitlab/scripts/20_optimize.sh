#!/bin/bash
#
# Image optimization script for GitLab container
# NO-OP: GitLab has no user-uploaded images that need optimization
#
# Main size contributors that must be kept:
# - Git repositories (~13GB)
# - PostgreSQL data (~12GB)
# - Uploads (~3.4GB)
# - Binaries (~2.7GB)
#
set -euo pipefail

BUILD_DRY_RUN="${BUILD_DRY_RUN:-false}"

echo "========================================"
echo "[optimize] GitLab image optimization..."
echo "========================================"

if [ "$BUILD_DRY_RUN" = "true" ]; then
    echo "[dry-run] Would skip optimization (no-op for GitLab)"
    exit 0
fi

echo "[optimize] No image optimization needed for GitLab"
echo "[optimize] GitLab stores git repositories and database data, not user images"

echo "========================================"
echo "[optimize] Done (no-op)"
echo "========================================"
