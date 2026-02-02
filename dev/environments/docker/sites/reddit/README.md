# Reddit (Postmill)

Port: 9999

## Fixes

### Vote System

**Problem:** Original code recalculates `netScore` from the votes collection. The imported database has `net_score` values but no vote records, causing first vote to reset score to ±1.

**Fix:** Use increment/decrement instead of recalculating. New vote adds ±1, vote change swings ±2, retract subtracts.

**Files:** `Submission.php`, `Comment.php`, `Votable.php`, `VoteManager.php`

### Header Authentication

**Problem:** UI login via Playwright is slow and requires maintaining test credentials.

**Fix:** Custom Symfony authenticator accepts `X-Postmill-Auto-Login: username:password` header.

**Files:** `HeaderAutologinAuthenticator.php`, `security.yaml`

**Usage:**
```python
context = await browser.new_context(
    extra_http_headers={"X-Postmill-Auto-Login": "MarvelsGrantMan136:test1234"}
)
```

### URL Rewriting

**Problem:** Symfony's `NoPrivateNetworkHttpClient` blocks requests to localhost/private IPs. Container can't fetch URLs referencing its own hostname.

**Fix:** Custom HTTP client rewrites all external URLs to `http://localhost/` before making requests.

**Files:** `UrlRewritingHttpClient.php`, `http_client.yaml`

### Rate Limit Removal

**Problem:** Postmill rate limits submissions, blocking automated testing.

**Fix:** Removed `@RateLimit` annotations.

**Files:** `SubmissionData.php`
