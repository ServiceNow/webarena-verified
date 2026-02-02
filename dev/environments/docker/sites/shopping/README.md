# Shopping (Magento Storefront)

Port: 7770

## Fixes

### Header Authentication

**Problem:** UI login via Playwright is slow and requires maintaining test credentials.

**Fix:** Magento plugin intercepts frontend requests and authenticates customers via `X-M2-Customer-Auto-Login: email:password` header.

**Files:** `CustomerAutoLogin/Plugin/CustomerAutoLoginPlugin.php`, `CustomerAutoLogin/etc/di.xml`, `CustomerAutoLogin/etc/module.xml`, `CustomerAutoLogin/registration.php`

**Usage:**
```python
context = await browser.new_context(
    extra_http_headers={"X-M2-Customer-Auto-Login": "emma.lopez@gmail.com:Password.123"}
)
```
