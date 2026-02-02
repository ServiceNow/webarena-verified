# Docker Site Optimizations

This directory contains optimized Docker images for WebArena sites. Each site has patches and configurations that fix issues with the original images.

## What Are Optimizations?

The original WebArena Docker images have various issues:
- **Data integrity bugs** - Vote counts reset, scores miscalculated
- **Testing friction** - Manual login required, rate limits block automation
- **Network issues** - Private network restrictions break internal requests
- **Missing tooling** - No runtime control or health checks

Our optimized images fix these issues while preserving the original functionality.

## How Optimizations Are Applied

### Base Image Pipeline

```
Original Image → Start Container → Run Setup Scripts → Squash → Base Image
```

1. **Pull original image** - Download the unmodified WebArena image
2. **Start container** - Run container from original image
3. **Apply patches** - Copy override files and run setup scripts
4. **Squash layers** - Create single-layer optimized image
5. **Publish** - Push to Docker Hub

### Setup Scripts

Each site has scripts in `sites/<site>/scripts/` that run in order:

| Script | Purpose |
|--------|---------|
| `00_apply_patches.sh` | Copy override files, install env-ctrl |
| `10_post_patch.sh` | Post-patch commands (compile, enable modules) |
| `20_optimize.sh` | Site-specific optimizations |
| `60_cleanup.sh` | Remove logs, caches, temp files |
| `90_verify.sh` | Verify patches applied correctly |

### Override Files

Patch files live in `sites/<site>/docker_overrides/`. These are copied into the container during `00_apply_patches.sh`.

## Runtime Control (env-ctrl)

All optimized images include the `env-ctrl` CLI for runtime operations:

```bash
env-ctrl init --base-url http://localhost:6680/  # Configure base URL
env-ctrl start --wait                            # Start services
env-ctrl stop                                    # Stop services
env-ctrl status                                  # Health check
```

## Sites

| Site | Port | Fixes |
|------|------|-------|
| [shopping_admin](sites/shopping_admin/) | 6680 | Header auth, mass action protection |
| [shopping](sites/shopping/) | 7770 | Header auth for customers |
| [reddit](sites/reddit/) | 9999 | Vote system, header auth, URL rewriting, rate limits |
| [gitlab](sites/gitlab/) | 8023 | - |
| [wikipedia](sites/wikipedia/) | 8888 | - |
| [map](sites/map/) | 3030 | Combined image with tiles + routing |

See each site's README for specific fixes.
