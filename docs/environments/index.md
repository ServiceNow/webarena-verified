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

### Using the CLI (Recommended)

The easiest way to run environments is using the built-in CLI:

```bash
# Start a site (waits for services to be ready)
webarena-verified env start --site shopping

# Check status
webarena-verified env status --site shopping

# Stop a site
webarena-verified env stop --site shopping

# Stop all running sites
webarena-verified env stop-all
```

Start multiple sites:

```bash
webarena-verified env start --site shopping
webarena-verified env start --site shopping_admin
webarena-verified env start --site reddit
webarena-verified env start --site gitlab
```

### Wikipedia and Map Data

Wikipedia and Map require external data files to be downloaded before starting:

```bash
# Wikipedia (~100GB download)
webarena-verified env setup init --site wikipedia --data-dir ./downloads
webarena-verified env start --site wikipedia --data-dir ./downloads

# Map (~60GB download)
webarena-verified env setup init --site map --data-dir ./downloads
webarena-verified env start --site map
```

See the [Wikipedia](wikipedia.md) and [Map](map.md) documentation for details.

### Using Docker Directly

You can also run environments directly with Docker:

```bash
# Shopping (Magento)
docker run -d --name webarena-verified-shopping -p 7770:80 -p 7771:8877 am1n3e/webarena-verified-shopping

# Shopping Admin
docker run -d --name webarena-verified-shopping_admin -p 7780:80 -p 7781:8877 am1n3e/webarena-verified-shopping_admin

# Reddit (Postmill)
docker run -d --name webarena-verified-reddit -p 9999:80 -p 9998:8877 am1n3e/webarena-verified-reddit

# GitLab
docker run -d --name webarena-verified-gitlab -p 8023:8023 -p 8024:8877 am1n3e/webarena-verified-gitlab
```

## CLI Command Reference

### Container Lifecycle

```bash
webarena-verified env start --site <site>                    # Start container (waits by default)
webarena-verified env start --site <site> --no-wait          # Start without waiting
webarena-verified env start --site <site> --port 8080        # Custom port
webarena-verified env stop --site <site>                     # Stop and remove container
webarena-verified env stop-all                               # Stop all containers
webarena-verified env status --site <site>                   # Check status
```

### Data Setup (Wikipedia, Map)

```bash
webarena-verified env setup init --site <site> --data-dir ./data   # Download and setup volumes
webarena-verified env setup clean --site <site>                     # Remove volumes
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
