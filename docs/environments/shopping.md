# Shopping

Magento 2 storefront for e-commerce browsing and purchasing.

| Property | Value |
|----------|-------|
| Port | 7770 |
| Env-Ctrl Port | 7771 |
| Image | `am1n3e/webarena-verified-shopping` |
| Container | `webarena-verified-shopping` |

## Quick Start

```bash
# Using Docker Compose
docker compose up -d shopping

# Using Invoke
inv envs.docker.pull --site shopping
inv envs.docker.start --site shopping
```

Access at: http://localhost:7770

## Auto-Login

The optimized image supports HTTP header-based authentication for customer accounts, bypassing UI login.

**Header:** `X-M2-Customer-Auto-Login: email:password`

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch()
    context = await browser.new_context(
        extra_http_headers={
            "X-M2-Customer-Auto-Login": "emma.lopez@gmail.com:Password.123"
        }
    )
    page = await context.new_page()
    await page.goto("http://localhost:7770")
    # You're now logged in as a customer
```

## Optimizations

### Header Authentication

**Problem:** UI login via Playwright is slow and requires maintaining test credentials.

**Fix:** Magento plugin intercepts frontend requests and authenticates customers via `X-M2-Customer-Auto-Login: email:password` header.

**Files:** `CustomerAutoLogin/Plugin/CustomerAutoLoginPlugin.php`, `CustomerAutoLogin/etc/di.xml`, `CustomerAutoLogin/etc/module.xml`, `CustomerAutoLogin/registration.php`
