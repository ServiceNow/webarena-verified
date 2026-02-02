#!/bin/bash
set -euo pipefail

# GitLab Slim Image Entrypoint
# Manages runsvdir and GitLab services directly (bypasses /assets/wrapper).
# Note: gitlab-ctl reconfigure is run at build time, not here.

SLEEP_INTERVAL="${SLEEP_INTERVAL:-5}"
MAX_WAIT_ATTEMPTS=60

# Default external URL (baked at build time)
DEFAULT_EXTERNAL_URL="http://localhost:8023"
WA_ENV_CTRL_EXTERNAL_SITE_URL="${WA_ENV_CTRL_EXTERNAL_SITE_URL:-$DEFAULT_EXTERNAL_URL}"
WA_ENV_CTRL_SKIP_RECONFIGURE="${WA_ENV_CTRL_SKIP_RECONFIGURE:-false}"

RUNSVDIR_PID=""

cleanup() {
    echo "Shutting down..."
    gitlab-ctl stop 2>/dev/null || true
    [ -n "$RUNSVDIR_PID" ] && kill "$RUNSVDIR_PID" 2>/dev/null || true
}
trap cleanup SIGTERM SIGINT

echo "Starting runsvdir..."
/opt/gitlab/embedded/bin/runsvdir-start &
RUNSVDIR_PID=$!

# Wait for runsvdir to be fully ready
echo "Waiting for runsvdir to be ready..."
for i in $(seq 1 $MAX_WAIT_ATTEMPTS); do
    if gitlab-ctl status >/dev/null 2>&1; then
        echo "runsvdir is ready (attempt $i)"
        break
    fi
    sleep "$SLEEP_INTERVAL"
done
if ! gitlab-ctl status >/dev/null 2>&1; then
    echo "ERROR: runsvdir failed to start"
    exit 1
fi

# Reconfigure if external URL differs from baked default
if [ "$WA_ENV_CTRL_SKIP_RECONFIGURE" = "true" ]; then
    echo "Skipping reconfigure: WA_ENV_CTRL_SKIP_RECONFIGURE=true"
elif [ "$WA_ENV_CTRL_EXTERNAL_SITE_URL" = "$DEFAULT_EXTERNAL_URL" ]; then
    echo "Skipping reconfigure: external URL matches default ($DEFAULT_EXTERNAL_URL)"
else
    echo "Reconfigure required: external URL changed from $DEFAULT_EXTERNAL_URL to $WA_ENV_CTRL_EXTERNAL_SITE_URL"

    # Update gitlab.rb with new external_url
    echo "Updating external_url in /etc/gitlab/gitlab.rb..."
    sed -i "s|external_url 'http://localhost:8023'|external_url '$WA_ENV_CTRL_EXTERNAL_SITE_URL'|" /etc/gitlab/gitlab.rb

    # Extract port from URL and update nginx listen_port
    NEW_PORT=$(echo "$WA_ENV_CTRL_EXTERNAL_SITE_URL" | sed -n 's|.*:\([0-9]*\)$|\1|p')
    if [ -n "$NEW_PORT" ]; then
        echo "Updating nginx listen_port to $NEW_PORT..."
        sed -i "s|nginx\['listen_port'\] = 8023|nginx['listen_port'] = $NEW_PORT|" /etc/gitlab/gitlab.rb
    fi

    echo "Running gitlab-ctl reconfigure..."
    gitlab-ctl reconfigure
    echo "Reconfigure completed"
fi

# Start env-ctrl with auto-restart (if enabled)
if [ "${WA_ENV_CTRL_ENABLE:-}" = "true" ]; then
    echo "Running env-ctrl init..."
    if ! /usr/local/bin/env-ctrl init; then
        echo "ERROR: env-ctrl init failed"
        exit 1
    fi

    echo "Starting env-ctrl on port ${WA_ENV_CTRL_PORT:-8877}..."
    (
        while true; do
            /usr/local/bin/env-ctrl serve --port "${WA_ENV_CTRL_PORT:-8877}" || true
            echo "env-ctrl exited, restarting in ${SLEEP_INTERVAL}s..."
            sleep "$SLEEP_INTERVAL"
        done
    ) &
    ENV_CTRL_PID=$!
    sleep "$SLEEP_INTERVAL"
    if ! kill -0 $ENV_CTRL_PID 2>/dev/null; then
        echo "ERROR: env-ctrl failed to start"
        exit 1
    fi
fi

# Start any services that aren't running (reconfigure already done at build time)
echo "Starting GitLab services..."
if ! gitlab-ctl start; then
    echo "ERROR: Failed to start GitLab services"
    exit 1
fi

echo "GitLab is ready"

# Keep container running by waiting on runsvdir
wait $RUNSVDIR_PID
echo "runsvdir exited unexpectedly"
exit 1
