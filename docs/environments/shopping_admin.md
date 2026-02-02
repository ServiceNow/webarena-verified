# Shopping Admin

Magento 2 admin panel for e-commerce management.

| Property | Value |
|----------|-------|
| Port | 7780 |
| Env-Ctrl Port | 7781 |
| Image | `am1n3e/webarena-verified-shopping_admin` |
| Container | `webarena-verified-shopping_admin` |

## Quick Start

```bash
# Using Docker Compose
docker compose up -d shopping_admin

# Using Invoke
inv envs.docker.pull --site shopping_admin
inv envs.docker.start --site shopping_admin
```

Access at: http://localhost:7780/admin

## Auto-Login

The optimized image supports HTTP header-based authentication, bypassing UI login.

**Header:** `X-M2-Admin-Auto-Login: username:password`

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch()
    context = await browser.new_context(
        extra_http_headers={"X-M2-Admin-Auto-Login": "admin:admin1234"}
    )
    page = await context.new_page()
    await page.goto("http://localhost:7780/admin")
    # You're now logged in as admin
```

### Testing Auto-Login

```bash
# Should redirect to dashboard and set cookies
curl -I -H "X-M2-Admin-Auto-Login: admin:admin1234" \
  http://localhost:7780/admin

# Without header - should redirect to login page
curl -I http://localhost:7780/admin
```

### Verify Module is Enabled

```bash
docker exec webarena-verified-shopping_admin \
  /var/www/magento2/bin/magento module:status WebArena_AutoLogin
```

## Optimizations

### Header Authentication

**Problem:** UI login via Playwright is slow and requires maintaining test credentials.

**Fix:** Magento plugin intercepts admin requests and authenticates via `X-M2-Admin-Auto-Login: username:password` header.

**Files:** `AutoLoginPlugin.php`, `di.xml`, `module.xml`, `registration.php`

### Mass Action Protection

**Problem:** Bulk delete actions in admin panel can accidentally destroy test data.

**Fix:** Plugins disable mass delete actions for products and reviews.

**Files:** `DisableProductMassActionsPlugin.php`, `DisableReviewMassActionsPlugin.php`
