# GitLab

GitLab Community Edition for source code management and CI/CD.

| Property | Value |
|----------|-------|
| Port | 8023 |
| Env-Ctrl Port | 8024 |
| Image | `am1n3e/webarena-verified-gitlab` |
| Container | `webarena-verified-gitlab` |

## Quick Start

```bash
# Using Docker Compose
docker compose up -d gitlab

# Using Invoke
inv envs.docker.pull --site gitlab
inv envs.docker.start --site gitlab
```

Access at: http://localhost:8023

## Resource Requirements

GitLab requires significant resources:

- **Memory:** Minimum 4GB RAM recommended
- **CPU:** Multiple cores for responsive performance
- **Startup time:** May take several minutes for all services to initialize

## Optimizations

The optimized image includes:

- Reduced image size (~78% smaller than original)
- Environment control (env-ctrl) for runtime management
- Optimized GitLab configuration for test workloads
