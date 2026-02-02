# Wikipedia

MediaWiki-based encyclopedia with pre-populated content.

| Property | Value |
|----------|-------|
| Port | 8888 |
| Env-Ctrl Port | 8889 |
| Image | `am1n3e/webarena-verified-wikipedia` |
| Container | `webarena-verified-wikipedia` |

## Quick Start

Wikipedia requires external data files (~100GB) to be downloaded before starting.

```bash
# 1. Download data and set up volumes
webarena-verified env setup init --site wikipedia --data-dir ./downloads

# 2. Start the container
webarena-verified env start --site wikipedia --data-dir ./downloads
```

Or using Docker directly:

```bash
# Download ZIM file first, then run
docker run -d --name webarena-verified-wikipedia \
  -p 8888:8080 -p 8889:8874 \
  -v /path/to/downloads:/data:ro \
  am1n3e/webarena-verified-wikipedia
```

Access at: http://localhost:8888

## Optimizations

The optimized image includes:

- Environment control (env-ctrl) for runtime management
- Pre-configured MediaWiki settings
- Volume mounts for Wikipedia content database
