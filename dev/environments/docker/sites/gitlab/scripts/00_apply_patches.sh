#!/bin/bash
#
# Bootstrap script for GitLab container
# Sets up env-ctrl package and CLI wrapper
# Note: Entrypoint is added by Dockerfile, not here
#
set -euo pipefail

WA_ENV_CTRL_ROOT="${WA_ENV_CTRL_ROOT:-/opt}"

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
echo "[bootstrap] Done"
echo "========================================"
