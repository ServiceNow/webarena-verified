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
# Using CLI (recommended)
webarena-verified env start --site gitlab

# Using Docker directly
docker run -d --name webarena-verified-gitlab -p 8023:8023 -p 8024:8877 am1n3e/webarena-verified-gitlab
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
