# Docker Images

WebArena-Verified provides optimized Docker images for all test environments. These images are significantly smaller than the originals while preserving exact content and functionality.

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

## Available Images

| Site | Default Port | Env-Ctrl Port | Image |
|------|--------------|---------------|-------|
| `shopping_admin` | 7780 | 7781 | `am1n3e/webarena-verified-shopping_admin` |
| `shopping` | 7770 | 7771 | `am1n3e/webarena-verified-shopping` |
| `gitlab` | 8023 | 8024 | `am1n3e/webarena-verified-gitlab` |
| `reddit` | 9999 | 9998 | `am1n3e/webarena-verified-reddit` |
| `wikipedia` | 8888 | 8889 | `am1n3e/webarena-verified-wikipedia` |
| `map` | 3030 | 3031 | `am1n3e/webarena-verified-map` |

## Size Improvements

Optimized images are significantly smaller than their original counterparts:

| Environment | Original Size | Optimized Size | Reduction |
|------------|---------------|----------------|-----------|
| Shopping Admin | 19.9 GB | 4.98 GB | **~70% smaller** |
| Shopping | 117 GB | 17.8 GB | **~85% smaller** |
| Reddit | 107 GB | 19 GB | **~82% smaller** |
| GitLab | 155 GB | 34 GB | **~78% smaller** |

**Benefits:**

- Smaller storage and memory footprint
- HTTP header-based authentication bypassing UI login
- Environment control (env-ctrl) for management via CLI or HTTP
- All functionality preserved

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

## Auto-Login Headers

Optimized images support HTTP header-based authentication, bypassing UI login.

### Shopping Admin

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch()
    context = await browser.new_context()

    # Set auto-login header
    await context.set_extra_http_headers({
        "X-M2-Admin-Auto-Login": "admin:admin1234"
    })

    page = await context.new_page()
    await page.goto("http://localhost:7780/admin")
    # You're now logged in as admin
```

### Reddit

```python
# Reddit uses a similar header mechanism
await context.set_extra_http_headers({
    "X-Auto-Login": "admin:password"
})
```

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

### Auto-login not working (Shopping Admin)

1. Test with curl:
   ```bash
   # Should redirect to dashboard and set cookies
   curl -I -H "X-M2-Admin-Auto-Login: admin:admin1234" \
     http://localhost:7780/admin

   # Without header - should redirect to login page
   curl -I http://localhost:7780/admin
   ```

2. Check module is enabled:
   ```bash
   docker exec webarena-verified-shopping_admin \
     /var/www/magento2/bin/magento module:status WebArena_AutoLogin
   ```
