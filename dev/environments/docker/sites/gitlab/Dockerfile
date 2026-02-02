# GitLab Environment - Final Image
#
# Base image created by: ./create_optimized_image.sh
# This Dockerfile adds env-ctrl on top of the optimized base.
#
# Build (from repo root):
#   docker build -t gitlab:latest -f dev/environments/docker/sites/gitlab/Dockerfile .
#
# Run:
#   docker run -d -p 8023:8023 -p 8877:8877 gitlab:latest

ARG BASE_IMAGE=am1n3e/webarena-verified-gitlab-base:latest
FROM ${BASE_IMAGE}
ARG ENV_CTRL_PORT=8877

# Environment control configuration
ENV WA_ENV_CTRL_TYPE=gitlab
ENV WA_ENV_CTRL_AVAILABLE=true
ENV WA_ENV_CTRL_ENABLE=true
ENV WA_ENV_CTRL_PORT=${ENV_CTRL_PORT}
ENV WA_ENV_CTRL_EXTERNAL_SITE_URL=http://localhost:8023
ENV WA_CONTAINER_PORT=8023

# Copy environment_control package and env-ctrl CLI
COPY packages/environment_control/environment_control /usr/local/environment_control
COPY --chmod=755 packages/environment_control/environment_control/env-ctrl /usr/local/bin/env-ctrl

# Symlink GitLab's embedded python3 so env-ctrl can find it
RUN ln -sf /opt/gitlab/embedded/bin/python3 /usr/local/bin/python3

# Copy GitLab configuration variants (small ~3GB, default ~6GB, large ~10GB)
COPY dev/environments/docker/sites/gitlab/docker_overrides/gitlab.rb /opt/gitlab-configs/gitlab.rb
COPY dev/environments/docker/sites/gitlab/docker_overrides/gitlab.small.rb /opt/gitlab-configs/gitlab.small.rb
COPY dev/environments/docker/sites/gitlab/docker_overrides/gitlab.large.rb /opt/gitlab-configs/gitlab.large.rb

# Copy entrypoint that starts env-ctrl independently
COPY --chmod=755 dev/environments/docker/sites/gitlab/docker_overrides/entrypoint.sh /opt/entrypoint.sh

# Use custom entrypoint
ENTRYPOINT ["/opt/entrypoint.sh"]

# Expose ports (gitlab: 8023, env-ctrl)
EXPOSE 8023 ${ENV_CTRL_PORT}
