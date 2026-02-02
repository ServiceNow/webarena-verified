#!/bin/bash
#
# Cleanup script for GitLab container
# Removes logs, caches, and temporary files to reduce image size
#
set -euo pipefail
set -x  # Echo all commands

BUILD_DRY_RUN="${BUILD_DRY_RUN:-false}"

if [ "$BUILD_DRY_RUN" = "true" ]; then
    echo "[dry-run] Skipping cleanup"
    exit 0
fi

echo "========================================"
echo "[cleanup] Starting cleanup..."
echo "========================================"

echo "[cleanup] Removing GitLab logs..."
rm -rf /var/log/gitlab/*/*.log
rm -rf /var/log/gitlab/*/*/*.log

echo "[cleanup] Removing runit svlogd logs..."
# svlogd uses @timestamp.u and 'current' files, not .log extension
rm -f /var/log/gitlab/*/@*
rm -f /var/log/gitlab/*/current
rm -f /var/log/gitlab/*/*/@*
rm -f /var/log/gitlab/*/*/current

echo "[cleanup] Removing system logs..."
rm -rf /var/log/*.log
rm -rf /var/log/*/*.log

echo "[cleanup] Removing Prometheus data (monitoring not needed for testing)..."
rm -rf /var/opt/gitlab/prometheus/data/*

echo "[cleanup] Removing GitLab tmp and cache..."
rm -rf /var/opt/gitlab/gitlab-rails/shared/tmp/*
rm -rf /var/opt/gitlab/gitlab-rails/shared/cache/*
rm -rf /var/opt/gitlab/gitlab-rails/tmp/cache/*

echo "[cleanup] Removing backups..."
rm -rf /var/opt/gitlab/backups/*

echo "[cleanup] Removing apt cache..."
rm -rf /var/cache/apt/archives/*
rm -rf /var/lib/apt/lists/*

echo "[cleanup] Removing temp files..."
rm -rf /tmp/*

echo "[cleanup] Removing stale PID files..."
rm -f /var/opt/gitlab/gitaly/gitaly.pid
rm -f /opt/gitlab/embedded/cookbooks/cache/cinc-client-running.pid

echo "[cleanup] Removing shell history and vim swap files..."
rm -f /root/.bash_history
rm -f /root/.viminfo

# -----------------------------------------
# Shutdown services
# -----------------------------------------

echo "[cleanup] Shutting down GitLab services..."
if command -v gitlab-ctl &> /dev/null; then
    echo "[cleanup] Stopping all GitLab services..."
    gitlab-ctl stop 2>/dev/null || true
    sleep 2
else
    echo "[cleanup] gitlab-ctl not found, skipping service shutdown"
fi

echo "========================================"
echo "[cleanup] Resetting PostgreSQL WAL files..."
echo "========================================"

PG_DATA="/var/opt/gitlab/postgresql/data"
PG_CTL="/opt/gitlab/embedded/bin/pg_ctl"
PG_RESETWAL="/opt/gitlab/embedded/bin/pg_resetwal"

echo "[cleanup] WAL size before: $(du -sh ${PG_DATA}/pg_wal/ 2>/dev/null | cut -f1)"

# Start PostgreSQL to run CHECKPOINT
echo "[cleanup] Starting PostgreSQL..."
su - gitlab-psql -s /bin/sh -c "${PG_CTL} start -D ${PG_DATA} -w -t 60"

# Run CHECKPOINT to flush all data to disk
echo "[cleanup] Running CHECKPOINT..."
su - gitlab-psql -s /bin/sh -c "/opt/gitlab/embedded/bin/psql -h /var/opt/gitlab/postgresql -d gitlabhq_production -c 'CHECKPOINT;'"

# Stop PostgreSQL cleanly
echo "[cleanup] Stopping PostgreSQL..."
su - gitlab-psql -s /bin/sh -c "${PG_CTL} stop -D ${PG_DATA} -m fast -w -t 60"

# Reset WAL files
echo "[cleanup] Running pg_resetwal..."
su - gitlab-psql -s /bin/sh -c "${PG_RESETWAL} -f ${PG_DATA}"

echo "[cleanup] WAL size after: $(du -sh ${PG_DATA}/pg_wal/ 2>/dev/null | cut -f1)"

echo "========================================"
echo "[cleanup] Done"
echo "========================================"
