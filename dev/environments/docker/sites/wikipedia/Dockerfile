FROM ghcr.io/kiwix/kiwix-serve:3.3.0

ARG ENV_CTRL_PORT=8877

# Install Python and supervisor
RUN apk add --no-cache python3 supervisor

# Copy environment_control package and env-ctrl CLI
COPY packages/environment_control/environment_control /usr/local/environment_control
COPY --chmod=755 packages/environment_control/environment_control/env-ctrl /usr/local/bin/env-ctrl

# Copy redirect index.html
COPY dev/environments/docker/sites/wikipedia/index.html /srv/index.html

# Copy supervisord config
COPY dev/environments/docker/sites/wikipedia/supervisord.conf /etc/supervisord.conf

# Set environment type for env-ctrl
ENV WA_ENV_CTRL_TYPE=wikipedia

# Default ZIM file path (can be overridden)
ENV WA_ENV_CTRL_ZIM_FILE=/data/wikipedia_en_all_maxi_2022-05.zim

# Default ports (can be overridden)
ENV WA_CONTAINER_PORT=8080
ENV WA_ENV_CTRL_KIWIX_PORT=${WA_CONTAINER_PORT}
ENV WA_ENV_CTRL_PORT=${ENV_CTRL_PORT}

# Site URL for the dashboard link (can be overridden)
ENV WA_ENV_CTRL_EXTERNAL_SITE_URL=http://localhost:8888

# Expose ports (kiwix: 8080, env-ctrl)
EXPOSE 8080 ${ENV_CTRL_PORT}

# Copy entrypoint script
COPY dev/environments/docker/sites/wikipedia/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
