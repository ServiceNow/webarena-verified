# Reddit

Postmill-based forum platform (Reddit clone).

| Property | Value |
|----------|-------|
| Port | 9999 |
| Env-Ctrl Port | 9998 |
| Image | `am1n3e/webarena-verified-reddit` |
| Container | `webarena-verified-reddit` |

## Quick Start

```bash
# Using CLI (recommended)
webarena-verified env start --site reddit

# Using Docker directly
docker run -d --name webarena-verified-reddit -p 9999:80 -p 9998:8877 am1n3e/webarena-verified-reddit
```

Access at: http://localhost:9999

## Auto-Login

The optimized image supports HTTP header-based authentication, bypassing UI login.

**Header:** `X-Postmill-Auto-Login: username:password`

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch()
    context = await browser.new_context(
        extra_http_headers={
            "X-Postmill-Auto-Login": "MarvelsGrantMan136:test1234"
        }
    )
    page = await context.new_page()
    await page.goto("http://localhost:9999")
    # You're now logged in
```

## Optimizations

### Vote System Fix

**Problem:** Original code recalculates `netScore` from the votes collection. The imported database has `net_score` values but no vote records, causing first vote to reset score to +/-1.

**Fix:** Use increment/decrement instead of recalculating. New vote adds +/-1, vote change swings +/-2, retract subtracts.

**Files:** `Submission.php`, `Comment.php`, `Votable.php`, `VoteManager.php`

### Header Authentication

**Problem:** UI login via Playwright is slow and requires maintaining test credentials.

**Fix:** Custom Symfony authenticator accepts `X-Postmill-Auto-Login: username:password` header.

**Files:** `HeaderAutologinAuthenticator.php`, `security.yaml`

### URL Rewriting

**Problem:** Symfony's `NoPrivateNetworkHttpClient` blocks requests to localhost/private IPs. Container can't fetch URLs referencing its own hostname.

**Fix:** Custom HTTP client rewrites all external URLs to `http://localhost/` before making requests.

**Files:** `UrlRewritingHttpClient.php`, `http_client.yaml`

### Rate Limit Removal

**Problem:** Postmill rate limits submissions, blocking automated testing.

**Fix:** Removed `@RateLimit` annotations.

**Files:** `SubmissionData.php`
