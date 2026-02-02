#!/bin/bash
#
# Bootstrap and apply patches for Reddit (Postmill) container
# Sets up env-ctrl, copies entrypoint, and applies patches
#
set -euo pipefail

WA_ENV_CTRL_ROOT="${WA_ENV_CTRL_ROOT:-/opt}"
OVERRIDES_DIR="/build-site/docker_overrides"

echo "========================================"
echo "[bootstrap] Setting up env-ctrl..."
echo "========================================"

echo "[bootstrap] Copying env-ctrl package to ${WA_ENV_CTRL_ROOT}/environment_control"
cp -r "${BUILD_ENV_CTRL_SRC}" "${WA_ENV_CTRL_ROOT}/environment_control"

echo "[bootstrap] Creating env-ctrl wrapper at /usr/local/bin/env-ctrl"
cat >/usr/local/bin/env-ctrl <<EOF
#!/bin/sh
export PYTHONPATH="${WA_ENV_CTRL_ROOT}"
exec python3 -m environment_control.cli "\$@"
EOF
chmod +x /usr/local/bin/env-ctrl

echo "========================================"
echo "[setup] Applying patches..."
echo "========================================"

# Vote system fix - uses delta-based scoring instead of recalculating from votes
echo "[patch] Copying Submission.php to /var/www/html/src/Entity/Submission.php"
cp "${OVERRIDES_DIR}/Submission.php" /var/www/html/src/Entity/Submission.php

echo "[patch] Copying Comment.php to /var/www/html/src/Entity/Comment.php"
cp "${OVERRIDES_DIR}/Comment.php" /var/www/html/src/Entity/Comment.php

echo "[patch] Copying Votable.php to /var/www/html/src/Entity/Contracts/Votable.php"
cp "${OVERRIDES_DIR}/Votable.php" /var/www/html/src/Entity/Contracts/Votable.php

echo "[patch] Copying VoteManager.php to /var/www/html/src/DataTransfer/VoteManager.php"
cp "${OVERRIDES_DIR}/VoteManager.php" /var/www/html/src/DataTransfer/VoteManager.php

# Header-based authentication for testing
echo "[patch] Copying HeaderAutologinAuthenticator.php to /var/www/html/src/Security/HeaderAutologinAuthenticator.php"
cp "${OVERRIDES_DIR}/HeaderAutologinAuthenticator.php" /var/www/html/src/Security/HeaderAutologinAuthenticator.php

echo "[patch] Copying security.yaml to /var/www/html/config/packages/security.yaml"
cp "${OVERRIDES_DIR}/security.yaml" /var/www/html/config/packages/security.yaml

# URL rewriting HTTP client - rewrites external URLs to localhost
echo "[patch] Creating directory /var/www/html/src/HttpClient"
mkdir -p /var/www/html/src/HttpClient

echo "[patch] Copying UrlRewritingHttpClient.php to /var/www/html/src/HttpClient/UrlRewritingHttpClient.php"
cp "${OVERRIDES_DIR}/UrlRewritingHttpClient.php" /var/www/html/src/HttpClient/UrlRewritingHttpClient.php

echo "[patch] Copying http_client.yaml to /var/www/html/config/packages/http_client.yaml"
cp "${OVERRIDES_DIR}/http_client.yaml" /var/www/html/config/packages/http_client.yaml

# Rate limit removal for testing
echo "[patch] Copying SubmissionData.php to /var/www/html/src/DataObject/SubmissionData.php"
cp "${OVERRIDES_DIR}/SubmissionData.php" /var/www/html/src/DataObject/SubmissionData.php

echo "========================================"
echo "[setup] Fixing ownership and clearing cache..."
echo "========================================"

echo "[setup] Setting ownership to www-data:www-data for /var/www/html/src and /var/www/html/config"
chown -R www-data:www-data /var/www/html/src /var/www/html/config

echo "[setup] Clearing Symfony cache at /var/www/html/var/cache/*"
rm -rf /var/www/html/var/cache/*

echo "========================================"
echo "[setup] Done"
echo "========================================"
