#!/bin/sh
set -e

# Set ZIM file path from argument or use default
export WA_ENV_CTRL_ZIM_FILE="${1:-${WA_ENV_CTRL_ZIM_FILE:-/data/wikipedia_en_all_maxi_2022-05.zim}}"

echo "Starting Wikipedia container with ZIM file: $WA_ENV_CTRL_ZIM_FILE"

# Start supervisord (manages kiwix-serve and env-ctrl)
exec /usr/bin/supervisord -c /etc/supervisord.conf
