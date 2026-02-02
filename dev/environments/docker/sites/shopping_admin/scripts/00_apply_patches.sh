#!/bin/bash
#
# Bootstrap and apply patches for Shopping Admin (Magento) container
# Sets up env-ctrl, copies entrypoint, and applies patches
#
set -euo pipefail

WA_ENV_CTRL_ROOT="${WA_ENV_CTRL_ROOT:-/opt}"
OVERRIDES_DIR="/build-site/docker_overrides"
AUTOLOGIN_DIR="/var/www/magento2/app/code/WebArena/AutoLogin"

echo "========================================"
echo "[bootstrap] Setting up env-ctrl..."
echo "========================================"

echo "[bootstrap] Copying env-ctrl package to ${WA_ENV_CTRL_ROOT}/environment_control"
cp -r "${BUILD_ENV_CTRL_SRC}" "${WA_ENV_CTRL_ROOT}/environment_control"

echo "[bootstrap] Creating env-ctrl wrapper at /usr/local/bin/env-ctrl"
cat > /usr/local/bin/env-ctrl << EOF
#!/bin/sh
export PYTHONPATH="${WA_ENV_CTRL_ROOT}"
exec python3 -m environment_control.cli "\$@"
EOF
chmod +x /usr/local/bin/env-ctrl

echo "========================================"
echo "[setup] Copying entrypoint..."
echo "========================================"

echo "[setup] Copying /build-site/entrypoint.sh to /entrypoint.sh"
cp /build-site/entrypoint.sh /entrypoint.sh
chmod +x /entrypoint.sh

echo "========================================"
echo "[setup] Applying patches..."
echo "========================================"

echo "[patch] Creating AutoLogin module directory structure at ${AUTOLOGIN_DIR}"
mkdir -p "${AUTOLOGIN_DIR}/etc" "${AUTOLOGIN_DIR}/Plugin"

echo "[patch] Copying registration.php to ${AUTOLOGIN_DIR}/registration.php"
cp "${OVERRIDES_DIR}/registration.php" "${AUTOLOGIN_DIR}/registration.php"

echo "[patch] Copying module.xml to ${AUTOLOGIN_DIR}/etc/module.xml"
cp "${OVERRIDES_DIR}/module.xml" "${AUTOLOGIN_DIR}/etc/module.xml"

echo "[patch] Copying di.xml to ${AUTOLOGIN_DIR}/etc/di.xml"
cp "${OVERRIDES_DIR}/di.xml" "${AUTOLOGIN_DIR}/etc/di.xml"

echo "[patch] Copying AutoLoginPlugin.php to ${AUTOLOGIN_DIR}/Plugin/AutoLoginPlugin.php"
cp "${OVERRIDES_DIR}/AutoLoginPlugin.php" "${AUTOLOGIN_DIR}/Plugin/AutoLoginPlugin.php"

echo "========================================"
echo "[setup] Fixing ownership..."
echo "========================================"

echo "[setup] Setting ownership to www-data:www-data for ${AUTOLOGIN_DIR}"
chown -R www-data:www-data "${AUTOLOGIN_DIR}"

echo "========================================"
echo "[setup] Enabling Magento module..."
echo "========================================"

echo "[magento] Running: php /var/www/magento2/bin/magento module:enable WebArena_AutoLogin"
php /var/www/magento2/bin/magento module:enable WebArena_AutoLogin

echo "[magento] Running: php /var/www/magento2/bin/magento setup:di:compile"
php /var/www/magento2/bin/magento setup:di:compile

echo "[magento] Running: php /var/www/magento2/bin/magento cache:flush"
php /var/www/magento2/bin/magento cache:flush

echo "========================================"
echo "[setup] Done"
echo "========================================"
