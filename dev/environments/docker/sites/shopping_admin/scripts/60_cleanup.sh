#!/bin/bash
#
# Cleanup script for Shopping Admin (Magento) container
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
# Application cleanup
# -----------------------------------------

echo "[cleanup] Removing Elasticsearch logs..."
rm -rf /usr/share/java/elasticsearch/logs/*

echo "[cleanup] Removing Magento logs and caches..."
rm -rf /var/www/magento2/var/log/*
rm -rf /var/www/magento2/var/cache/*
rm -rf /var/www/magento2/var/page_cache/*
rm -rf /var/www/magento2/var/session/*
rm -rf /var/www/magento2/var/view_preprocessed/*
rm -rf /var/www/magento2/generated/*
rm -rf /var/www/magento2/dev/tests

echo "[cleanup] Removing Composer cache..."
rm -rf /root/.composer/cache/*
rm -rf /var/www/.composer/cache/*

echo "[cleanup] Removing apt cache..."
rm -rf /var/cache/apt/archives/*
rm -rf /var/lib/apt/lists/*

echo "[cleanup] Removing service logs..."
rm -rf /var/log/mysql/*
rm -rf /var/log/nginx/*
rm -rf /var/log/*.log
rm -rf /var/log/*/*.log

echo "[cleanup] Removing temp files..."
rm -rf /tmp/*.log
rm -rf /tmp/magento*
rm -rf /tmp/elasticsearch-*
rm -rf /tmp/*.jpg
rm -rf /tmp/sess_*
rm -rf /tmp/hsperfdata_*

echo "[cleanup] Removing stale PID files..."
rm -f /var/lib/mysql/*.pid
rm -f /run/*.pid
rm -f /supervisord.pid

echo "[cleanup] Removing MySQL recovery logs..."
rm -f /var/lib/mysql/ddl_recovery*.log

echo "[cleanup] Removing Alpine package cache..."
rm -rf /var/cache/apk/*

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

echo "[cleanup] Removing Elasticsearch temp dirs..."
rm -rf /tmp/elasticsearch-* 2>/dev/null || true

echo "[cleanup] Removing general temp files..."
rm -rf /tmp/* 2>/dev/null || true
rm -rf /var/cache/* 2>/dev/null || true
rm -rf /var/log/* 2>/dev/null || true

echo "========================================"
echo "[cleanup] Done"
echo "========================================"
