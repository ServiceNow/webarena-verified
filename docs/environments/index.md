# Environments

WebArena-Verified uses Docker containers to provide isolated, reproducible test environments for each website in the benchmark.

## Available Environments

| Environment | Description | Port | Env-Ctrl Port | Documentation |
|-------------|-------------|------|---------------|---------------|
| Shopping Admin | Magento admin panel | 7780 | 7781 | [shopping_admin.md](shopping_admin.md) |
| Shopping | Magento storefront | 7770 | 7771 | [shopping.md](shopping.md) |
| Reddit | Postmill forum | 9999 | 9998 | [reddit.md](reddit.md) |
| GitLab | GitLab CE | 8023 | 8024 | [gitlab.md](gitlab.md) |
| Wikipedia | MediaWiki | 8888 | 8889 | [wikipedia.md](wikipedia.md) |
| Map | OpenStreetMap | 3030 | 3031 | [map.md](map.md) |

## Docker Images

All environments are available as optimized Docker images on Docker Hub:

| Site | Image |
|------|-------|
| Shopping Admin | `am1n3e/webarena-verified-shopping_admin` |
| Shopping | `am1n3e/webarena-verified-shopping` |
| Reddit | `am1n3e/webarena-verified-reddit` |
| GitLab | `am1n3e/webarena-verified-gitlab` |
| Wikipedia | `am1n3e/webarena-verified-wikipedia` |
| Map | `am1n3e/webarena-verified-map` |

## Size Improvements

Optimized images are significantly smaller than their original counterparts:

| Environment | Original Size | Optimized Size | Reduction |
|-------------|---------------|----------------|-----------|
| Shopping Admin | 19.9 GB | 2.9 GB | ~85% smaller |
| Shopping | 117 GB | 13.3 GB | ~89% smaller |
| Reddit | 107 GB | 8.41 GB | ~92% smaller |
| GitLab | 155 GB | 31.6 GB | ~80% smaller |
| Wikipedia | - | 115 MB | - |
| Map | - | 3.28 GB | - |

**Benefits of optimized images:**

- Smaller storage and memory footprint
- HTTP header-based authentication (bypasses UI login)
- Environment control (env-ctrl) for management via CLI or HTTP
- All original functionality preserved

## Environment Variables

Docker Compose uses environment variables for port configuration:

| Variable | Default | Description |
|----------|---------|-------------|
| `WA_SHOPPING_ADMIN_PORT` | 7780 | Shopping Admin main port |
| `WA_SHOPPING_PORT` | 7770 | Shopping main port |
| `WA_GITLAB_PORT` | 8023 | GitLab main port |
| `WA_REDDIT_PORT` | 9999 | Reddit main port |
| `WA_WIKIPEDIA_PORT` | 8888 | Wikipedia main port |
| `WA_MAP_PORT` | 3030 | Map main port |

Each site also has an `_ENV_CTRL_PORT` variable (e.g., `WA_SHOPPING_ADMIN_ENV_CTRL_PORT`).

## Quick Start

The easiest way to run environments is using Docker Compose:

```bash
# Start all environments
docker compose up -d

# Or start specific services
docker compose up -d shopping_admin shopping

# Check status
docker compose ps

# Stop all
docker compose down
```

Alternatively, use the Invoke tasks for more control:

```bash
# List available sites
inv envs.sites

# Pull and start a site
inv envs.docker.pull --site shopping_admin
inv envs.docker.start --site shopping_admin
inv envs.docker.check --site shopping_admin

# Stop when done
inv envs.docker.stop --site shopping_admin
```

### Wikipedia and Map Data

Wikipedia and Map require external data files to be downloaded before starting:

```bash
# Download data for Wikipedia
inv envs.docker.data-download --site wikipedia
inv envs.docker.setup --site wikipedia --data-dir ./data

# Download data for Map (tiles + routing ~60GB)
inv envs.docker.data-download --site map
inv envs.docker.setup --site map --data-dir ./data
```

See the [Wikipedia](wikipedia.md) and [Map](map.md) documentation for details.

## Command Reference

### Container Lifecycle

```bash
inv envs.docker.start --site <site>              # Start container
inv envs.docker.start --site <site> --original   # Start with original image
inv envs.docker.start --site <site> --port 8080  # Custom port
inv envs.docker.stop --site <site>               # Stop and remove container
inv envs.docker.check --site <site>              # Health check
```

### Image Management

```bash
inv envs.docker.pull --site <site>               # Pull from Docker Hub
inv envs.docker.pull --site <site> --original    # Download original tar file
inv envs.docker.build --site <site>              # Build from Dockerfile
inv envs.docker.create-base-img --site <site>    # Create optimized base image
inv envs.docker.publish --site <site> --tag 1.0.0  # Push to Docker Hub
```

### Data Management

```bash
inv envs.docker.data-download                    # Download all data files
inv envs.docker.data-download --site wikipedia   # Download specific site data
inv envs.docker.setup --site map --data-dir ./data  # Set up volumes for a site
```

### Testing

```bash
inv envs.docker.test --site <site>               # Run integration tests
inv envs.docker.test --site <site> --headed      # Run with visible browser
```

## Troubleshooting

### Container not starting

```bash
# Check container logs
docker logs webarena-verified-<site>

# Check services inside container
docker exec webarena-verified-<site> supervisorctl status
```

### Health check failing

```bash
# Use env-ctrl to check status
inv envs.docker.check --site <site>

# Or directly via HTTP
curl http://localhost:<env-ctrl-port>/health
```

## Further Reading

- [Environment Control](environment_control.md) - The `env-ctrl` package for runtime management
