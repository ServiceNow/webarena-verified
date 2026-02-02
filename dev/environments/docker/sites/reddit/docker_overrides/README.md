# Reddit (Postmill) Docker Overrides

This directory contains patched PHP files that fix issues in the Postmill application. These files are applied via the `RedditOps.patch()` method after the container starts.

## Vote System Fix

**Problem:** The original Postmill code recalculates `netScore` from the votes collection whenever a vote is added. However, the imported database has `net_score` values but no corresponding records in `submission_votes` or `comment_votes` tables. This caused:
- First vote on any post/comment would reset score to ±1 instead of incrementing/decrementing
- Example: A post with score 38 would become -1 after a downvote (instead of 37)

**Solution:** Modified the vote system to use increment/decrement instead of recalculating from votes:
- New vote: `netScore += choice` (+1 for upvote, -1 for downvote)
- Vote change: `netScore += (newChoice - oldChoice)` (±2 swing)
- Vote retract: `netScore -= choice`

**Files:**
| File | Container Path |
|------|----------------|
| `Submission.php` | `/var/www/html/src/Entity/Submission.php` |
| `Comment.php` | `/var/www/html/src/Entity/Comment.php` |
| `Votable.php` | `/var/www/html/src/Entity/Contracts/Votable.php` |
| `VoteManager.php` | `/var/www/html/src/DataTransfer/VoteManager.php` |

## Header-Based Authentication (for Testing)

**Problem:** UI-based login via Playwright is slow and requires maintaining test credentials.

**Solution:** Custom Symfony authenticator that accepts `X-Postmill-Auto-Login` header with `username:password` format to authenticate as any user.

**Files:**
| File | Container Path |
|------|----------------|
| `HeaderAutologinAuthenticator.php` | `/var/www/html/src/Security/HeaderAutologinAuthenticator.php` |
| `security.yaml` | `/var/www/html/config/packages/security.yaml` |

**Usage in Playwright:**

```python
context = await browser.new_context(
    extra_http_headers={
        "X-Postmill-Auto-Login": "MarvelsGrantMan136:test1234"
    }
)
page = await context.new_page()
await page.goto("http://localhost:9999/")  # Authenticated as MarvelsGrantMan136
```

## URL Rewriting HTTP Client

**Problem:** Postmill uses Symfony's `NoPrivateNetworkHttpClient` which blocks requests to localhost/private IPs. When the container tries to fetch submission URLs that reference external hostnames (e.g., `http://reddit.example.com:9999/post/123`), the requests fail because:
1. The external hostname resolves to the container's own address
2. Private network requests are blocked by default

**Solution:** Custom HTTP client decorator that rewrites all external URLs to `http://localhost/` before making requests.

**Files:**
| File | Container Path |
|------|----------------|
| `UrlRewritingHttpClient.php` | `/var/www/html/src/HttpClient/UrlRewritingHttpClient.php` |
| `http_client.yaml` | `/var/www/html/config/packages/http_client.yaml` |

**URL rewriting examples:**
- `http://localhost:9999/post/123` → `http://localhost/post/123`
- `http://reddit.example.com/post/123` → `http://localhost/post/123`
- `https://192.168.1.100:8443/post/123` → `http://localhost/post/123`

## Rate Limit Removal

**Problem:** Postmill has rate limiting on submissions which interferes with automated testing.

**Solution:** Patched `SubmissionData.php` with `@RateLimit` annotations removed.

**Files:**
| File | Container Path |
|------|----------------|
| `SubmissionData.php` | `/var/www/html/src/DataObject/SubmissionData.php` |

## Applying Patches

### Via Python (environment_control)

```python
from environment_control.ops.sites.reddit import RedditOps

# Create executor that runs commands in the container
def exec_cmd(cmd):
    import subprocess
    result = subprocess.run(
        ['docker', 'exec', 'container_name', 'bash', '-c', cmd],
        capture_output=True, text=True
    )
    return result.returncode, result.stdout, result.stderr

# Stage patches (copy to container)
import subprocess
subprocess.run(['docker', 'cp', 'contributing/environments/docker/sites/reddit/docker_overrides/.', 'container_name:/tmp/patches/'])

# Apply patches
result = RedditOps.patch(exec_cmd=exec_cmd)
print(result.value)  # Shows applied/failed/skipped
```

### Via Manual Commands

```bash
CONTAINER_NAME="your_container_name"
OVERRIDES_DIR="contributing/environments/docker/sites/reddit/docker_overrides"

# Copy all patch files
docker cp "$OVERRIDES_DIR/." "$CONTAINER_NAME:/tmp/patches/"

# Apply patches manually
docker exec "$CONTAINER_NAME" bash -c '
    cp /tmp/patches/Submission.php /var/www/html/src/Entity/Submission.php
    cp /tmp/patches/Comment.php /var/www/html/src/Entity/Comment.php
    cp /tmp/patches/Votable.php /var/www/html/src/Entity/Contracts/Votable.php
    cp /tmp/patches/VoteManager.php /var/www/html/src/DataTransfer/VoteManager.php
    cp /tmp/patches/HeaderAutologinAuthenticator.php /var/www/html/src/Security/HeaderAutologinAuthenticator.php
    cp /tmp/patches/security.yaml /var/www/html/config/packages/security.yaml
    mkdir -p /var/www/html/src/HttpClient
    cp /tmp/patches/UrlRewritingHttpClient.php /var/www/html/src/HttpClient/UrlRewritingHttpClient.php
    cp /tmp/patches/http_client.yaml /var/www/html/config/packages/http_client.yaml
    cp /tmp/patches/SubmissionData.php /var/www/html/src/DataObject/SubmissionData.php
    chown -R www-data:www-data /var/www/html/src /var/www/html/config
    rm -rf /var/www/html/var/cache/*
'
```
