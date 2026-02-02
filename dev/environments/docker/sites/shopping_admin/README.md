# Shopping Admin (Magento)

Port: 7780

## Fixes

### Header Authentication

**Problem:** UI login via Playwright is slow and requires maintaining test credentials.

**Fix:** Magento plugin intercepts admin requests and authenticates via `X-M2-Admin-Auto-Login: username:password` header.

**Files:** `AutoLoginPlugin.php`, `di.xml`, `module.xml`, `registration.php`

**Usage:**
```python
context = await browser.new_context(
    extra_http_headers={"X-M2-Admin-Auto-Login": "admin:admin1234"}
)
```

### Mass Action Protection

**Problem:** Bulk delete actions in admin panel can accidentally destroy test data.

**Fix:** Plugins disable mass delete actions for products and reviews.

**Files:** `DisableProductMassActionsPlugin.php`, `DisableReviewMassActionsPlugin.php`
