# Docker Image Management

Tools for creating and managing optimized Docker images for WebArena sites.

## Quick Start

```bash
# List available sites
inv envs.sites

# Pull and start a site
inv envs.docker.pull --site shopping-admin
inv envs.docker.start --site shopping-admin
inv envs.docker.check --site shopping-admin

# Stop when done
inv envs.docker.stop --site shopping-admin
```

## Creating Base Images

Build optimized base images for sites. This applies patches, runs cleanup, and squashes layers.

### Shopping Admin

```bash
inv envs.docker.pull --site shopping-admin --original
inv envs.docker.create-base-img --site shopping-admin

# Test locally
inv envs.docker.start --site shopping-admin
inv envs.docker.check --site shopping-admin

# Publish (tag must be semver, e.g., 1.0.0)
inv envs.docker.publish --site shopping-admin --tag 1.0.0
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

| Site | Port | Image |
|------|------|-------|
| `wikipedia` | 8888 | `am1n3e/webarena-verified:wikipedia` |
| `shopping-admin` | 6680 | `am1n3e/webarena-verified:shopping_admin` |
| `shopping` | 7770 | `am1n3e/webarena-verified:shopping` |
| `reddit` | 9999 | `am1n3e/webarena-verified:reddit` |
| `gitlab` | 8023 | `am1n3e/webarena-verified:gitlab` |

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

Setup scripts in `sites/<site>/scripts/` run in order:
1. `00_apply_patches.sh` - Bootstrap env-ctrl, copy entrypoint, apply patches
2. `10_cleanup.sh` - Remove logs, caches, temp files
3. `20_optimize.sh` - Site-specific optimizations (optional)

All patching is done via shell scripts with explicit `cp` commands - no Python patching at runtime.

## Directory Structure

```
contributing/environments/
├── settings.py              # Site registry (ports, images, paths)
├── tasks.py                 # Top-level tasks (envs.sites)
└── docker/
    ├── tasks.py             # Docker tasks (envs.docker.*)
    ├── sites/               # Site-specific configs
    │   ├── shopping_admin/
    │   │   ├── entrypoint.sh
    │   │   ├── docker_overrides/   # Patch files
    │   │   └── scripts/            # Setup scripts
    │   ├── reddit/
    │   ├── gitlab/
    │   └── ...
    ├── utils/               # Shared utilities
    │   ├── containers.py    # Container operations
    │   ├── create_base_img.py
    │   └── downloads.py
    └── monitoring/          # Gatus health monitoring
```

## In-Container Operations (env-ctrl)

The `env-ctrl` CLI runs inside containers for runtime operations:

```bash
env-ctrl init --base-url http://localhost:6680/  # Set base URL
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
        └── wikipedia.py       # WikipediaOps
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
