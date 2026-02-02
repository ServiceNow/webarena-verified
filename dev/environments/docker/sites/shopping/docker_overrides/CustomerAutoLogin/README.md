# Shopping Customer AutoLogin Module

The `WebArena_CustomerAutoLogin` module provides header-based customer authentication for the Magento storefront, enabling automated testing without manual login.

## Files

| File | Container Path |
|------|----------------|
| `registration.php` | `/var/www/magento2/app/code/WebArena/CustomerAutoLogin/registration.php` |
| `etc/module.xml` | `/var/www/magento2/app/code/WebArena/CustomerAutoLogin/etc/module.xml` |
| `etc/di.xml` | `/var/www/magento2/app/code/WebArena/CustomerAutoLogin/etc/di.xml` |
| `Plugin/CustomerAutoLoginPlugin.php` | `/var/www/magento2/app/code/WebArena/CustomerAutoLogin/Plugin/CustomerAutoLoginPlugin.php` |

## How It Works

The module uses a Magento plugin to intercept FrontController dispatch:

1. Checks if request is for frontend area
2. Checks if customer is already logged in
3. Looks for `X-M2-Customer-Auto-Login` HTTP header (format: `email:password`)
4. Authenticates customer via `AccountManagementInterface::authenticate()`
5. Logs them in via `CustomerSession::setCustomerDataAsLoggedIn()`

## Usage

### With curl

```bash
curl -H "X-M2-Customer-Auto-Login: emma.lopez@gmail.com:Password.123" http://localhost:7770/customer/account/
```

### With Playwright

```python
context = await browser.new_context(
    extra_http_headers={
        "X-M2-Customer-Auto-Login": "emma.lopez@gmail.com:Password.123"
    }
)
page = await context.new_page()
await page.goto("http://localhost:7770/customer/account/")  # Logged in as Emma
```

## Applying Patches

The patches are applied via the environment control API:

```bash
# Stage patches to container
docker cp contributing/environments/docker/sites/shopping/docker_overrides/CustomerAutoLogin shopping:/tmp/patches/WebArena/CustomerAutoLogin/

# Apply patches via env-ctrl API
curl -X POST http://localhost:8877/patch
```

## Post-Installation Commands

After patching, these commands are run automatically:
1. `php bin/magento module:enable WebArena_CustomerAutoLogin` - Enable the module
2. `php bin/magento setup:di:compile` - Compile dependency injection
3. `php bin/magento cache:flush` - Clear Magento cache

## Verification

```bash
# Check module is enabled
docker exec shopping php /var/www/magento2/bin/magento module:status | grep WebArena

# Check logs for auto-login activity
docker exec shopping tail /var/www/magento2/var/log/system.log | grep auto-login
```
