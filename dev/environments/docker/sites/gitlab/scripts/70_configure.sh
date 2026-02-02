#!/bin/bash
#
# Run gitlab-ctl reconfigure during build (not at runtime)
# This eliminates ~2 minute reconfigure overhead on every container start
#
set -euo pipefail

BUILD_DRY_RUN="${BUILD_DRY_RUN:-false}"
SLEEP_INTERVAL=5

if [ "$BUILD_DRY_RUN" = "true" ]; then
    echo "[dry-run] Skipping reconfigure"
    exit 0
fi

echo "========================================"
echo "[configure] Starting GitLab reconfigure..."
echo "========================================"

cleanup() {
    echo "[configure] Cleaning up..."
    gitlab-ctl stop 2>/dev/null || true
    pkill -f runsvdir-start 2>/dev/null || true
}
trap cleanup EXIT

echo "[configure] Starting runsvdir..."
/opt/gitlab/embedded/bin/runsvdir-start &
# Give runsvdir time to initialize before polling
sleep "$SLEEP_INTERVAL"

echo "[configure] Waiting for runsvdir to be ready..."
for i in {1..120}; do
    if gitlab-ctl status >/dev/null 2>&1; then
        echo "[configure] runsvdir ready (attempt $i)"
        break
    fi
    sleep "$SLEEP_INTERVAL"
done
if ! gitlab-ctl status >/dev/null 2>&1; then
    echo "[configure] ERROR: runsvdir failed to start"
    exit 1
fi

echo "[configure] Copying optimized gitlab.rb..."
cp /build-site/docker_overrides/gitlab.rb /etc/gitlab/gitlab.rb

echo "[configure] Running gitlab-ctl reconfigure..."
gitlab-ctl reconfigure

echo "[configure] Stopping services..."
gitlab-ctl stop
sleep "$SLEEP_INTERVAL"

# Verify services stopped
if gitlab-ctl status 2>&1 | grep -q "^run:"; then
    echo "[configure] WARNING: Some services still running, forcing stop..."
    gitlab-ctl kill
    sleep "$SLEEP_INTERVAL"
fi

echo "========================================"
echo "[configure] Done"
echo "========================================"
