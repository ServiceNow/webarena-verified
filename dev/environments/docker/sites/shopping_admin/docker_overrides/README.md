# Shopping Admin Docker Overrides

This directory contains patch files for the Shopping Admin (Magento) container.

## AutoLogin Module

The `WebArena_AutoLogin` module provides header-based authentication for the Magento admin panel, enabling automated testing without manual login.

### Files

| File | Container Path |
|------|----------------|
| `registration.php` | `/var/www/magento2/app/code/WebArena/AutoLogin/registration.php` |
| `module.xml` | `/var/www/magento2/app/code/WebArena/AutoLogin/etc/module.xml` |
| `di.xml` | `/var/www/magento2/app/code/WebArena/AutoLogin/etc/di.xml` |
| `AutoLoginPlugin.php` | `/var/www/magento2/app/code/WebArena/AutoLogin/Plugin/AutoLoginPlugin.php` |

### How It Works

The module uses a Magento plugin to intercept FrontController dispatch:

1. Checks if request is for admin area (`adminhtml`)
2. Checks if user is already logged in
3. Looks for `X-M2-Admin-Auto-Login` HTTP header
4. Parses credentials in `username:password` format
5. Calls Magento's official `Auth::login()` API

### Usage

#### With curl

```bash
curl -H "X-M2-Admin-Auto-Login: admin:admin1234" http://localhost:6680/admin/dashboard
```

#### With Playwright

```python
context = await browser.new_context(
    extra_http_headers={
        "X-M2-Admin-Auto-Login": "admin:admin1234"
    }
)
page = await context.new_page()
await page.goto("http://localhost:6680/admin")  # Authenticated as admin
```

### Applying Patches

The patches are applied via the environment control API:

```bash
# Stage patches to container
docker cp contributing/environments/docker/sites/shopping_admin/docker_overrides/. shopping_admin:/tmp/patches/

# Apply patches via env-ctrl API
curl -X POST http://localhost:8877/patch
```

Or programmatically:

```python
from environment_control.ops.sites import ShoppingAdminOps

# Apply patches (assumes files are staged at /tmp/patches/)
result = ShoppingAdminOps.patch()
```

### Post-Installation Commands

After patching, these commands are run automatically:
1. `php bin/magento module:enable WebArena_AutoLogin` - Enable the module
2. `php bin/magento setup:di:compile` - Compile dependency injection
3. `php bin/magento cache:flush` - Clear Magento cache

### Verification

```bash
# Check module is enabled
docker exec shopping_admin php /var/www/magento2/bin/magento module:status | grep WebArena

# Should output:
# WebArena_AutoLogin
```
