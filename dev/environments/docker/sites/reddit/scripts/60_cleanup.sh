#!/bin/bash
#
# Cleanup script for Reddit (Postmill) container
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

# -----------------------------------------
# PostgreSQL WAL reset (do first)
# -----------------------------------------

echo "========================================"
echo "[cleanup] Resetting PostgreSQL WAL files..."
echo "========================================"

PG_DATA="/usr/local/pgsql/data"
PG_CTL="/usr/bin/pg_ctl"
PG_RESETWAL="/usr/bin/pg_resetwal"

# Database credentials
DB_HOST="localhost"
DB_USER="postmill"
DB_PASS="postmill"
DB_NAME="postmill"

# Superuser credentials (for CHECKPOINT)
DB_SUPERUSER="postgres"
DB_SUPERPASS="postgres"

echo "[cleanup] WAL size before: $(du -sh ${PG_DATA}/pg_wal/ 2>/dev/null | cut -f1)"

# Start PostgreSQL to run CHECKPOINT
echo "[cleanup] Starting PostgreSQL..."
su - postgres -s /bin/sh -c "${PG_CTL} start -D ${PG_DATA} -w -t 60"

# Set superuser password (base image may not have it configured)
echo "[cleanup] Setting superuser password..."
su - postgres -s /bin/sh -c "psql -c \"ALTER USER ${DB_SUPERUSER} WITH PASSWORD '${DB_SUPERPASS}';\""

# Run CHECKPOINT to flush all data to disk (requires superuser)
echo "[cleanup] Running CHECKPOINT..."
PGPASSWORD="${DB_SUPERPASS}" psql -h "${DB_HOST}" -U "${DB_SUPERUSER}" -d postgres -c 'CHECKPOINT;'

# Stop PostgreSQL cleanly
echo "[cleanup] Stopping PostgreSQL..."
su - postgres -s /bin/sh -c "${PG_CTL} stop -D ${PG_DATA} -m fast -w -t 60"

# Reset WAL files
echo "[cleanup] Running pg_resetwal..."
su - postgres -s /bin/sh -c "${PG_RESETWAL} -f ${PG_DATA}"

echo "[cleanup] WAL size after: $(du -sh ${PG_DATA}/pg_wal/ 2>/dev/null | cut -f1)"

# -----------------------------------------
# Application cleanup
# -----------------------------------------

echo "[cleanup] Removing Symfony caches and logs..."
rm -rf /var/www/html/var/cache/*
rm -rf /var/www/html/var/log/*
rm -rf /var/www/html/var/sessions/*

echo "[cleanup] Removing node_modules (not needed at runtime)..."
rm -rf /var/www/html/node_modules

echo "[cleanup] Removing Elasticsearch logs..."
rm -rf /usr/share/java/elasticsearch/logs/*

echo "[cleanup] Removing system logs..."
rm -rf /var/log/*.log
rm -rf /var/log/*/*.log

echo "[cleanup] Removing yarn cache..."
rm -rf /usr/local/share/.cache/yarn

echo "[cleanup] Removing Composer cache..."
rm -rf /root/.composer/cache/*

echo "[cleanup] Removing Alpine package cache..."
rm -rf /var/cache/apk/*

echo "[cleanup] Removing stale PID files..."
rm -f /run/nginx.pid
rm -f /run/mysqld/*.pid
rm -f /supervisord.pid
rm -f /usr/local/pgsql/data/postmaster.pid

echo "[cleanup] Removing shell history..."
rm -f /root/.bash_history

# -----------------------------------------
# Shutdown services
# -----------------------------------------

echo "[cleanup] Shutting down services..."
if pgrep -x supervisord > /dev/null; then
    echo "[cleanup] Supervisord is running, stopping all services..."
    supervisorctl stop all 2>/dev/null || true
    pkill supervisord 2>/dev/null || true
    sleep 2
else
    echo "[cleanup] Supervisord not running, skipping service shutdown"
fi

# -----------------------------------------
# Final cleanup
# -----------------------------------------

# Remove ImageMagick temporary files (can be 25GB+)
echo "[cleanup] Removing ImageMagick temp files..."
rm -rf /tmp/magick-* 2>/dev/null || true

# General temp cleanup
echo "[cleanup] Removing general temp files..."
rm -rf /tmp/* 2>/dev/null || true
rm -rf /var/cache/* 2>/dev/null || true
rm -rf /var/log/* 2>/dev/null || true

# Recreate required nginx directories (removed by cleanup above)
echo "[cleanup] Recreating nginx log directories..."
mkdir -p /var/log/nginx /var/lib/nginx/logs

# Remove Python cache files
echo "[cleanup] Removing Python cache files..."
find / -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find / -type f -name '*.pyc' -delete 2>/dev/null || true

echo "========================================"
echo "[cleanup] Done"
echo "========================================"
