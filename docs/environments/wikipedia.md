# Wikipedia

MediaWiki-based encyclopedia with pre-populated content.

| Property | Value |
|----------|-------|
| Port | 8888 |
| Env-Ctrl Port | 8889 |
| Image | `am1n3e/webarena-verified-wikipedia` |
| Container | `webarena-verified-wikipedia` |

## Quick Start

```bash
# Using Docker Compose
docker compose up -d wikipedia

# Using Invoke
inv envs.docker.pull --site wikipedia
inv envs.docker.start --site wikipedia
```

Access at: http://localhost:8888

## Data Requirements

Wikipedia requires external data files to be downloaded and mounted:

```bash
# Download Wikipedia data
inv envs.docker.data-download --site wikipedia

# Set up volumes
inv envs.docker.setup --site wikipedia --data-dir ./data
```

## Optimizations

The optimized image includes:

- Environment control (env-ctrl) for runtime management
- Pre-configured MediaWiki settings
- Volume mounts for Wikipedia content database
