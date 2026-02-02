# ============================================================================
# SOURCE IMAGES (for COPY --from)
# All source images use linux/amd64 to match the base image architecture
# ============================================================================
ARG BUILDPLATFORM=linux/amd64
FROM --platform=$BUILDPLATFORM overv/openstreetmap-tile-server@sha256:b6a79da39b6d0758368f7c62d22e49dd3ec59e78b194a5ef9dee2723b1f3fa79 AS tile-server
FROM --platform=$BUILDPLATFORM ghcr.io/project-osrm/osrm-backend:v5.27.1 AS osrm-backend
FROM --platform=$BUILDPLATFORM mediagis/nominatim:4.2 AS nominatim

# ============================================================================
# BASE STAGE - Binaries and packages (rarely changes)
# ============================================================================
FROM --platform=$BUILDPLATFORM am1n3e/openstreetmap-website-web:base AS base

ENV DEBIAN_FRONTEND=noninteractive

# Add PostgreSQL apt repository for PostgreSQL 15
RUN apt-get update \
 && apt-get install --no-install-recommends -y curl ca-certificates gnupg \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt jammy-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Install PostgreSQL 14 & 15, supervisor, git, and tile server dependencies
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
      git \
      postgresql-14 \
      postgresql-contrib-14 \
      postgresql-14-postgis-3 \
      postgresql-15 \
      postgresql-15-postgis-3 \
      supervisor \
      apache2 \
      libapache2-mod-tile \
      renderd \
      osm2pgsql \
      osmium-tool \
      fonts-noto-cjk \
      fonts-noto-hinted \
      fonts-noto-unhinted \
      fonts-hanazono \
      fontconfig \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Copy tile server configurations from tile-server image
COPY --from=tile-server /etc/renderd.conf /etc/renderd.conf
COPY --from=tile-server /etc/postgresql/15/main/postgresql.custom.conf.tmpl /etc/postgresql/15/main/postgresql.custom.conf.tmpl
COPY --from=tile-server /home/renderer/src/openstreetmap-carto-backup /home/renderer/src/openstreetmap-carto-backup
COPY --from=tile-server /home/renderer/src/regional /home/renderer/src/regional
COPY --from=tile-server /run.sh /tile-server-run.sh

# Install carto (Node.js tool to compile map styles to mapnik.xml)
RUN npm install -g carto

# Create renderer user and setup directories
RUN useradd -m -s /bin/bash renderer \
 && mkdir -p /data/database /data/tiles /data/style /var/cache/renderd/tiles /run/renderd /var/log/tiles \
 && chown -R renderer: /data /var/cache/renderd /run/renderd /var/log/tiles \
 && ln -sf /data/style /home/renderer/src/openstreetmap-carto

# Pre-build mapnik.xml from default style (will be copied to /data/style at runtime if empty)
RUN cd /home/renderer/src/openstreetmap-carto-backup \
 && carto project.mml > mapnik.xml

# Copy OSRM binary from osrm-backend image
COPY --from=osrm-backend /usr/local/bin/osrm-routed /usr/local/bin/osrm-routed

# Install OSRM runtime dependencies (boost libraries)
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
      libboost-program-options1.74.0 \
      libboost-filesystem1.74.0 \
      libboost-iostreams1.74.0 \
      libboost-thread1.74.0 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# === NOMINATIM ===
# Copy Nominatim binaries and configs from nominatim stage
COPY --from=nominatim /usr/local/bin/nominatim /usr/local/bin/nominatim
COPY --from=nominatim /usr/local/lib/nominatim /usr/local/lib/nominatim
COPY --from=nominatim /usr/local/lib/python3.10 /usr/local/lib/python3.10
COPY --from=nominatim /usr/local/share/nominatim /usr/local/share/nominatim
COPY --from=nominatim /usr/local/etc/nominatim /usr/local/etc/nominatim
COPY --from=nominatim /nominatim /nominatim-base

# Install Nominatim PHP and Python dependencies, plus brotli for asset patching
RUN apt-get update && apt-get install --no-install-recommends -y \
    php8.1-fpm \
    php8.1-pgsql \
    php8.1-intl \
    php8.1-cgi \
    libapache2-mod-php8.1 \
    python3-yaml \
    python3-icu \
    python3-psycopg2 \
    python3-dotenv \
    brotli \
    python3-psutil \
    python3-jinja2 \
    python3-datrie \
    python3-sqlalchemy \
    python3-asyncpg \
    sudo \
    locales \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen \
 && locale-gen

# Create Nominatim user and directories
RUN useradd -m -s /bin/bash nominatim \
 && mkdir -p /nominatim /data/nominatim/postgres /data/nominatim/flatnode /var/log/nominatim \
 && chown -R nominatim: /nominatim /var/log/nominatim

# ============================================================================
# FINAL STAGE - PostgreSQL configs and Rails compilation (iterate quickly)
# ============================================================================
FROM base AS final

ARG ENV_CTRL_PORT=8877

ENV DEBIAN_FRONTEND=noninteractive
ENV OSM_COMMIT=d4a014d3a6ca3f8f7d03528d39e4707dc256bc60
ENV PG_VERSION=15

# Environment control configuration
ENV WA_ENV_CTRL_TYPE=map
ENV WA_ENV_CTRL_AVAILABLE=true
ENV WA_ENV_CTRL_ENABLE=true
ENV WA_ENV_CTRL_PORT=${ENV_CTRL_PORT}
ENV WA_ENV_CTRL_EXTERNAL_SITE_URL=http://localhost:8080
ENV WA_CONTAINER_PORT=8080

# Drop auto-created clusters and create fresh ones with explicit ports
RUN pg_dropcluster --stop 14 main 2>/dev/null || true \
 && pg_dropcluster --stop 15 main 2>/dev/null || true

# Initialize PostgreSQL 14 cluster (website database) on port 5433
RUN pg_createcluster 14 main -p 5433 --start \
 && pg_ctlcluster 14 main stop \
 && echo "host all all 0.0.0.0/0 trust" >> /etc/postgresql/14/main/pg_hba.conf \
 && echo "listen_addresses='*'" >> /etc/postgresql/14/main/postgresql.conf

# Initialize PostgreSQL 15 cluster (tile database) on port 5432 (renderd default)
RUN pg_createcluster 15 main -p 5432 --start \
 && pg_ctlcluster 15 main stop \
 && echo "host all all 0.0.0.0/0 trust" >> /etc/postgresql/15/main/pg_hba.conf \
 && echo "listen_addresses='*'" >> /etc/postgresql/15/main/postgresql.conf \
 && mkdir -p /etc/postgresql/15/main/conf.d

# Initialize PostgreSQL 14 cluster for Nominatim on port 5434
RUN pg_createcluster 14 nominatim -p 5434 --start \
 && pg_ctlcluster 14 nominatim stop \
 && echo "host all all 0.0.0.0/0 trust" >> /etc/postgresql/14/nominatim/pg_hba.conf \
 && echo "listen_addresses='*'" >> /etc/postgresql/14/nominatim/postgresql.conf

# Configure Apache for tile serving on port 8080, OSRM proxy, and Nominatim on port 8085
RUN echo "Listen 8080" >> /etc/apache2/ports.conf \
 && echo "Listen 8085" >> /etc/apache2/ports.conf \
 && a2enmod tile headers proxy proxy_http php8.1
COPY dev/environments/docker/sites/map/docker_overrides/tile-server.conf /etc/apache2/sites-available/tile-server.conf
COPY dev/environments/docker/sites/map/docker_overrides/nominatim.conf /etc/apache2/sites-available/nominatim.conf
RUN a2ensite tile-server nominatim

# Install image optimization tools for Rails asset pipeline (image_optim gem)
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
      pngcrush \
      advancecomp \
      optipng \
      pngquant \
      jhead \
      jpegoptim \
      libjpeg-turbo-progs \
      gifsicle \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g svgo

# Clone OSM website app at exact commit
RUN rm -rf /app/* /app/.[!.]* \
 && git clone https://github.com/openstreetmap/openstreetmap-website.git /app \
 && cd /app && git checkout $OSM_COMMIT \
 && rm -rf /app/.git

WORKDIR /app

# Install Rails dependencies
RUN bundle install && bundle exec bin/yarn install

# Setup Rails config files
RUN cp config/example.storage.yml config/storage.yml
COPY dev/environments/docker/sites/map/docker_overrides/database.yml config/database.yml
# Copy local settings BEFORE asset precompilation so URLs are baked into JS
COPY dev/environments/docker/sites/map/docker_overrides/settings.local.yml config/settings.local.yml

# Production mode configuration
ENV RAILS_ENV=production
ENV SECRET_KEY_BASE=1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b

# Patch tile URL to use local tile server via Apache proxy (relative URL)
RUN sed -i 's|https://tile.openstreetmap.org/|/tile/|g' \
    vendor/assets/leaflet/leaflet.osm.js

# Remove non-OSRM routing engines (only local OSRM is available)
RUN rm -f app/assets/javascripts/index/directions/graphhopper.js \
         app/assets/javascripts/index/directions/fossgis_valhalla.js

# Precompile assets at build time
# - RAILS_SERVE_STATIC_FILES enables serving precompiled assets
# - i18n:js:export generates JavaScript translations for embed.js.erb
RUN SECRET_KEY_BASE=$SECRET_KEY_BASE \
    RAILS_ENV=production \
    RAILS_SERVE_STATIC_FILES=true \
    bundle exec rails i18n:js:export assets:precompile

# Patch compiled JS to use relative URLs for browser requests
# Server-side Rails uses absolute URLs from settings.local.yml (http://localhost:8080/...)
# Client-side browser JS needs relative URLs (/nominatim/, /osrm/) to work with any host port
RUN find public/assets -name "*.js" -exec \
    sed -i 's|http://localhost:8080/nominatim/|/nominatim/|g; s|http://localhost:8080/osrm/|/osrm/|g' {} \;

# Supervisor config
RUN mkdir -p /var/log/supervisor
COPY dev/environments/docker/sites/map/docker_overrides/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY dev/environments/docker/sites/map/docker_overrides/entrypoint.sh /entrypoint.sh
COPY dev/environments/docker/sites/map/scripts/warmup_tiles.py /warmup_tiles.py
RUN chmod +x /entrypoint.sh

# Copy environment_control package and env-ctrl CLI
COPY packages/environment_control/environment_control /usr/local/environment_control
COPY --chmod=755 packages/environment_control/environment_control/env-ctrl /usr/local/bin/env-ctrl

# Ports: Apache unified (8080 - proxies Rails + tiles + OSRM + Nominatim), internal services below
# Internal: Rails (3000), Nominatim (8085), OSRM routing (5000-5002), PostgreSQL 15 tiles (5432), PostgreSQL 14 website (5433), PostgreSQL 14 nominatim (5434), env-ctrl
EXPOSE 8080 3000 5000 5001 5002 8085 5432 5433 5434 ${ENV_CTRL_PORT}

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
