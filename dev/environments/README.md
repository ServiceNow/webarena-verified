# Docker Image Management

Tools for creating and managing optimized Docker images for WebArena sites.

## Quick Start

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

## Creating Base Images

Build optimized base images for sites. This applies patches, runs cleanup, and squashes layers.

### Shopping Admin

```bash
inv envs.docker.pull --site shopping_admin --original
inv envs.docker.create-base-img --site shopping_admin

# Test locally
inv envs.docker.start --site shopping_admin
inv envs.docker.check --site shopping_admin

# Publish (tag must be semver, e.g., 1.0.0)
inv envs.docker.publish --site shopping_admin --tag 1.0.0
```

### Reddit

```bash
inv envs.docker.pull --site reddit --original
inv envs.docker.create-base-img --site reddit

# Test locally
inv envs.docker.start --site reddit
inv envs.docker.check --site reddit

# Publish
inv envs.docker.publish --site reddit --tag 1.0.0
```

### GitLab

```bash
inv envs.docker.pull --site gitlab --original
inv envs.docker.create-base-img --site gitlab

# Test locally
inv envs.docker.start --site gitlab
inv envs.docker.check --site gitlab

# Publish
inv envs.docker.publish --site gitlab --tag 1.0.0
```

---

## Available Sites

| Site | Default Port | Env-Ctrl Port | Image |
|------|--------------|---------------|-------|
| `shopping_admin` | 7780 | 7781 | `am1n3e/webarena-verified-shopping_admin` |
| `shopping` | 7770 | 7771 | `am1n3e/webarena-verified-shopping` |
| `gitlab` | 8023 | 8024 | `am1n3e/webarena-verified-gitlab` |
| `reddit` | 9999 | 9998 | `am1n3e/webarena-verified-reddit` |
| `wikipedia` | 8888 | 8889 | `am1n3e/webarena-verified-wikipedia` |
| `map` | 3030 | 3031 | `am1n3e/webarena-verified-map` |

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

### Testing

```bash
inv envs.docker.test --site <site>               # Run integration tests
inv envs.docker.test --site <site> --headed      # Run with visible browser
```

## Base Image Pipeline

The `create-base-img` command creates optimized images:

```
Original Image → Start Container → Run Setup Scripts → Squash → Base Image
```

Setup scripts in `sites/<site>/scripts/` run in numeric order:

| Script | Purpose |
|--------|---------|
| `00_apply_patches.sh` | Bootstrap env-ctrl, copy entrypoint, apply patches |
| `10_post_patch.sh` | Post-patch configuration (optional) |
| `20_optimize.sh` | Site-specific optimizations (optional) |
| `60_cleanup.sh` | Remove logs, caches, temp files |
| `90_verify.sh` | Verify setup completed correctly |

All patching is done via shell scripts with explicit `cp` commands - no Python patching at runtime.

## Directory Structure

```
dev/environments/
├── settings.py              # Site registry (ports, images, paths)
├── tasks.py                 # Top-level tasks (envs.sites)
└── docker/
    ├── tasks.py             # Docker tasks (envs.docker.*)
    ├── sites/               # Site-specific configs
    │   ├── shopping_admin/
    │   │   ├── Dockerfile
    │   │   ├── docker_overrides/   # Patch files
    │   │   └── scripts/            # Setup scripts
    │   ├── shopping/
    │   ├── reddit/
    │   ├── gitlab/
    │   ├── wikipedia/
    │   └── map/
    └── utils/               # Shared utilities
        ├── containers.py    # Container operations
        ├── create_base_img.py
        ├── downloads.py
        ├── dockerfile.py
        └── sites.py
```

## In-Container Operations (env-ctrl)

The `env-ctrl` CLI runs inside containers for runtime operations:

```bash
env-ctrl init --base-url http://localhost:7780/  # Set base URL
env-ctrl start --wait                            # Start services
env-ctrl stop                                    # Stop services
env-ctrl status                                  # Health check
env-ctrl serve                                   # Start REST API server
```

### Architecture

```
packages/environment_control/
├── cli.py                   # CLI entry point
├── server/app.py            # REST API server
└── ops/
    ├── base.py              # BaseOps (abstract base class)
    ├── mixins/
    │   └── supervisor.py    # SupervisorMixin
    └── sites/
        ├── shopping_admin.py  # ShoppingAdminOps
        ├── shopping.py        # ShoppingOps
        ├── reddit.py          # RedditOps
        ├── gitlab.py          # GitlabOps
        ├── wikipedia.py       # WikipediaOps
        └── map.py             # MapOps
```

Site ops classes inherit from `BaseOps` and optionally `SupervisorMixin`:
- `_init()` - Set base URL, configure site
- `_start()` / `_stop()` - Manage services
- `_get_health()` - Check service health

## Environment Variables

Override settings with `WA_DEV__` prefix:
```bash
WA_DEV__SHOPPING_ADMIN__PORT=7777
WA_DEV__SHOPPING_ADMIN__HOSTNAME=myhost.local
```
