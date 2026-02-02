# Shopping Admin Environment - Final Image
#
# Base image created by: ./create_optimized_image.sh
# This Dockerfile adds env-ctrl on top of the optimized base.
#
# Build (from repo root):
#   docker build -t shopping_admin:latest -f dev/environments/docker/sites/shopping_admin/Dockerfile .
#
# Run:
#   docker run -d -p 7780:80 -p 8877:8877 shopping_admin:latest

ARG BASE_IMAGE=am1n3e/webarena-verified-shopping-admin-base:latest
FROM ${BASE_IMAGE}
ARG ENV_CTRL_PORT=8877

WORKDIR /var/www/html

# Environment control configuration
ENV WA_ENV_CTRL_TYPE=shopping_admin
ENV WA_ENV_CTRL_AVAILABLE=true
ENV WA_ENV_CTRL_ENABLE=true
ENV WA_ENV_CTRL_PORT=${ENV_CTRL_PORT}
ENV WA_ENV_CTRL_EXTERNAL_SITE_URL=http://localhost:7780
ENV WA_CONTAINER_PORT=80

# Resource optimization settings (applied by custom entrypoint)
ENV NGINX_WORKER_PROCESSES=2
ENV ES_JAVA_OPTS="-Xms512m -Xmx512m"
ENV MYSQL_INNODB_BUFFER_POOL_SIZE=256M
ENV MYSQL_MAX_CONNECTIONS=20

# Copy environment_control package and env-ctrl CLI
COPY packages/environment_control/environment_control /usr/local/environment_control
COPY --chmod=755 packages/environment_control/environment_control/env-ctrl /usr/local/bin/env-ctrl

# Copy env-ctrl supervisor configs
COPY dev/environments/docker/sites/shopping_admin/docker_overrides/etc/supervisor.d/env-ctrl.ini /etc/supervisor.d/env-ctrl.ini
COPY dev/environments/docker/sites/shopping_admin/docker_overrides/etc/supervisor.d/env-ctrl-init.ini /etc/supervisor.d/env-ctrl-init.ini

# Copy custom entrypoint that applies resource optimizations
COPY --chmod=755 dev/environments/docker/sites/shopping_admin/docker_overrides/entrypoint.sh /custom-entrypoint.sh

# Expose ports (nginx: 80, env-ctrl)
EXPOSE 80 ${ENV_CTRL_PORT}

# Use custom entrypoint (calls original entrypoint after applying optimizations)
ENTRYPOINT ["/custom-entrypoint.sh"]
CMD ["supervisord", "-n", "-j", "/supervisord.pid"]
