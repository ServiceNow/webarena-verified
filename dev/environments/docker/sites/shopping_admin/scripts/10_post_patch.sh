#!/bin/bash
#
# Post-patch script for Shopping Admin (Magento) container
# Starts services, configures base URL, compiles Magento module
#
set -euo pipefail
set -x

BUILD_DRY_RUN="${BUILD_DRY_RUN:-false}"

echo "========================================"
echo "[services] Starting services and waiting for ready..."
echo "========================================"

env-ctrl start --wait --timeout "${BUILD_TIMEOUT:-300}"

echo "[services] Configuring base URL: ${BUILD_BASE_URL}"
env-ctrl setup init --base-url "${BUILD_BASE_URL}"

echo "========================================"
echo "[magento] Compiling Magento module..."
echo "========================================"

if [ "$BUILD_DRY_RUN" = "true" ]; then
    echo "[dry-run] Skipping Magento compilation"
else
    php /var/www/magento2/bin/magento module:enable WebArena_AutoLogin
    php /var/www/magento2/bin/magento setup:di:compile
    php /var/www/magento2/bin/magento cache:flush
fi

echo "[magento] Stopping services..."
env-ctrl stop

echo "========================================"
echo "[magento] Done"
echo "========================================"
