# Environments

WebArena-Verified uses Docker containers to provide isolated, reproducible environments for each website in the benchmark. To improve reset time and reduce storage requirements, we provide recipes to create **slim images** - optimized versions of the original environments while keeping the exact content and functionality.

## Size Improvements

Slim images are significantly smaller than their original counterparts:

| Environment | Original Size | Slim Size | Reduction |
|------------|---------------|-----------|-----------|
| Shopping Admin | 19.9 GB | 4.98 GB | **~70% smaller** |
| Shopping | 117 GB | 17.8 GB | **~85% smaller** |
| Reddit | 107 GB | 19 GB | **~82% smaller** |
| GitLab | 155 GB | 34 GB | **~78% smaller** |

**Benefits:**

- Smaller storage and memory footprint
- HTTP header-based authentication bypassing UI login
- All functionality preserved

## Shopping Admin

### 1. Create the slim image

```bash
cd scripts/environments/shopping_admin
bash create_slim_image.sh
```

### 2. Run the container with auto-initialization

```bash
docker run -d --name admin-slim -p 7780:80 \
  -e MAGENTO_BASE_URL=http://localhost:7780 \
  shopping_admin_final_0719:slim
```

### Access the admin (auto-login via header in Playwright)

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

### Manual Initialization

If you want to manually initialize the environment (e.g., after stopping the container), run:

```bash
# Start container
docker run -d --name admin-slim -p 7780:80 shopping_admin_final_0719:slim

# Initialize Magento
docker exec admin-slim magento-init http://localhost:7780
```

### Troubleshooting

**Auto-login not working:**

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
   docker exec admin-slim /var/www/magento2/bin/magento module:status WebArena_AutoLogin
   ```
   Should show "Module is enabled"

3. Check DI is compiled:
   ```bash
   docker exec admin-slim ls -la /var/www/magento2/generated/code/
   ```
   Should contain compiled classes

4. Check logs:
   ```bash
   docker exec admin-slim tail -f /var/www/magento2/var/log/system.log
   ```
   Look for "Auto-login successful" or error messages

5. Recompile if needed:
   ```bash
   docker exec admin-slim /var/www/magento2/bin/magento setup:di:compile
   ```

**Container not initializing:**
- Check container logs: `docker logs admin-slim`
- Verify MAGENTO_BASE_URL is set correctly
- Wait ~30 seconds for initialization to complete

**Database reset not working:**
- Ensure archive exists: `docker exec admin-slim ls -lh /var/backups/mysql/data.tar.gz`
- Check services status: `docker exec admin-slim supervisorctl status`

## Reddit

### 1. Create the slim image

```bash
cd scripts/environments/reddit
bash create_slim_image.sh
```

**Note:** The script reuses existing data if available:
- PostgreSQL archive (~1.6GB)
- Optimized submission images (~6GB)
- This saves ~30-60 minutes on subsequent runs

### 2. Run the container

```bash
docker run -d --name reddit-slim -p 9999:80 postmill-populated-exposed-withimg:slim
```

The container is self-contained (no volume mounts needed) and auto-initializes on first start (~2-3 minutes).

### Manual Initialization

Not typically needed (container auto-initializes), but can be run manually if needed:

```bash
# Start container
docker run -d --name reddit-slim -p 9999:80 postmill-populated-exposed-withimg:slim

# Check initialization status
docker exec reddit-slim postmill-init
```

### Troubleshooting

**Container not initializing:**
- Check container logs: `docker logs reddit-slim`
- Wait ~2-3 minutes for initial data extraction
- Check initialization status: `docker exec reddit-slim cat /run/postmill.env`

**Database reset not working:**
- Ensure archives exist:
  ```bash
  docker exec reddit-slim ls -lh /var/backups/pgsql/data.tar.gz
  docker exec reddit-slim ls -lh /var/backups/images/submission_images.tar.gz
  ```
- Check services status: `docker exec reddit-slim supervisorctl status`
- Verify database integrity: `docker exec reddit-slim postmill-init` (shows validation output)

**Patches not applied:**
1. Check rate limits removed:
   ```bash
   docker exec reddit-slim grep -c '@RateLimit' /var/www/html/src/DataObject/SubmissionData.php
   ```
   Should return `0`

2. Check HTTP client configured:
   ```bash
   docker exec reddit-slim grep 'alias: postmill.http_client.default' \
     /var/www/html/config/packages/http_client.yaml
   ```
   Should show the configuration line
