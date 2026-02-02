"""Playwright UI tests for Reddit (Postmill) Docker container.

Tests the Reddit forum functionality using browser automation.

Test categories:
- User Login: Authentication flow
- Forum Navigation: Navigate to subreddit pages
- Content Verification: Verify forum content exists
- Logged-in User: Profile access
- Image Loading: Post image verification
- Docker Override Tests: Verify fixes from docker_overrides/README.md
  - Vote System Fix: Voting increments/decrements scores correctly
  - Rate Limit Removal: Multiple submissions can be created quickly
  - URL Rewriting: Link submissions with external URLs work correctly

Usage:
    pytest tests/integration/environments/reddit/test_playwright.py
    pytest tests/integration/environments/reddit/test_playwright.py --playwright-timeout-sec=60
"""

import urllib.request
import uuid

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.docker, pytest.mark.integration_docker_reddit]

# User Login Test


@pytest.mark.flaky(reruns=2)
def test_reddit_user_login(reddit_container, reddit_base_url, reddit_credentials, page, pw_timeout):
    """Test user login flow."""
    login_url = f"{reddit_base_url}/login"

    page.goto(login_url)

    # Wait for login form (Postmill uses _username/_password field names)
    page.wait_for_selector('input[name="_username"]', timeout=pw_timeout)

    # Fill in credentials
    page.fill('input[name="_username"]', reddit_credentials["username"])
    page.fill('input[name="_password"]', reddit_credentials["password"])

    # Click login button
    page.click('button[type="submit"]')

    # Wait for username button in navbar (indicates successful login)
    page.wait_for_selector(f'button:has-text("{reddit_credentials["username"]}")', timeout=pw_timeout)

    # Verify logged in (username should appear somewhere)
    assert reddit_credentials["username"] in page.content()


# Forum Navigation Tests


@pytest.mark.flaky(reruns=2)
def test_reddit_navigate_to_askreddit(reddit_container, reddit_base_url, page, pw_timeout):
    """Test navigation to AskReddit forum."""
    page.goto(reddit_base_url)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Navigate to AskReddit forum
    page.goto(f"{reddit_base_url}/f/AskReddit")
    page.wait_for_selector("h1, .forum-title, .submission-list", timeout=pw_timeout)

    # Verify we're on the AskReddit page
    content = page.content().lower()
    assert "askreddit" in content


@pytest.mark.flaky(reruns=2)
def test_reddit_forums_list_has_content(reddit_container, reddit_base_url, page, pw_timeout):
    """Test that forums list page has forum entries."""
    page.goto(f"{reddit_base_url}/forums")
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Should have multiple forum links
    forum_links = page.locator('a[href*="/f/"]')
    assert forum_links.count() > 10, "Expected at least 10 forums"


# Content Verification Tests


@pytest.mark.flaky(reruns=2)
def test_reddit_has_submissions(reddit_container, reddit_base_url, page, pw_timeout):
    """Test that /all page has submission posts."""
    # Homepage defaults to "Featured" filter with no content, so use /all instead
    page.goto(f"{reddit_base_url}/all")
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Look for submission entries
    submissions = page.locator("article, .submission, .submission-row")
    assert submissions.count() > 0, "Expected submissions on /all page"


@pytest.mark.flaky(reruns=2)
def test_reddit_askreddit_has_posts(reddit_container, reddit_base_url, page, pw_timeout):
    """Test that AskReddit forum has posts."""
    page.goto(f"{reddit_base_url}/f/AskReddit")
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Look for submission entries
    submissions = page.locator("article, .submission, .submission-row")
    assert submissions.count() > 0, "Expected posts in AskReddit"


# Logged-in User Tests


@pytest.mark.flaky(reruns=2)
def test_reddit_logged_in_user_profile(
    reddit_container, reddit_base_url, reddit_credentials, reddit_get_logged_page, pw_timeout
):
    """Test that logged-in user can access their profile."""
    page = reddit_get_logged_page()

    # Navigate to user profile
    page.goto(f"{reddit_base_url}/user/{reddit_credentials['username']}")
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Verify username is displayed in the page heading (sidebar)
    expect(page.locator("h1.page-heading")).to_contain_text(reddit_credentials["username"])


# Image Loading Tests

# Posts from different forums to test image loading
# Format: pytest.param(post_url, forum_name, id="image_N")
TEST_POSTS_FOR_IMAGES = [
    pytest.param("/f/aww/58888/lovely-eyes-full-of-love", "aww", id="image_1"),
    pytest.param("/f/memes/127582/it-s-out-of-control", "memes", id="image_2"),
    pytest.param("/f/Art/10111/a-big-eater-me-pumpkin-carving-2022", "Art", id="image_3"),
    pytest.param("/f/photoshopbattles/45340/psbattle-halloween-costume", "photoshopbattles", id="image_4"),
    pytest.param("/f/gifs/19936/ok-time-for-you-to-go-to-bed", "gifs", id="image_5"),
    pytest.param(
        "/f/EarthPorn/98297/2-years-later-this-is-still-one-of-the-most-incredible", "EarthPorn", id="image_6"
    ),
    pytest.param("/f/OldSchoolCool/35802/twins-photographed-in-1937-and-2012", "OldSchoolCool", id="image_7"),
    pytest.param("/f/GetMotivated/55022/image-experience-never-goes-wasted", "GetMotivated", id="image_8"),
    pytest.param("/f/pics/45604/a-trejo-thanksgiving", "pics", id="image_9"),
    pytest.param("/f/pics/110715/amazing-shot-of-a-blue-jay-pestering-a-bald-eagle", "pics_2", id="image_10"),
]


@pytest.mark.flaky(reruns=2)
@pytest.mark.parametrize(("post_url", "forum"), TEST_POSTS_FOR_IMAGES)
def test_post_images_load(reddit_container, reddit_base_url, page, pw_timeout, post_url, forum):
    """Test that post images load correctly.

    Verifies that images in Reddit posts are accessible and not broken.
    """
    page.goto(f"{reddit_base_url}{post_url}", timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Find post images (Postmill uses .submission__image class)
    images = page.locator(".submission__image")
    image_count = images.count()

    assert image_count > 0, f"No images found in post from {forum}"

    # Collect image URLs and verify they are accessible
    broken_images = []
    for i in range(image_count):
        src = images.nth(i).get_attribute("src")
        if src and src.startswith("http"):
            try:
                req = urllib.request.Request(src, method="HEAD")
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status != 200:
                        broken_images.append(f"{src} (status: {response.status})")
                    else:
                        # Verify image has content (not empty/placeholder)
                        content_length = int(response.headers.get("Content-Length", 0))
                        if content_length == 0:
                            broken_images.append(f"{src} (empty content)")
            except Exception as e:
                broken_images.append(f"{src} (error: {e})")

    assert len(broken_images) == 0, f"Found broken images in {forum}: {broken_images}"


# Docker Override Tests
# These tests verify the fixes documented in:
# dev/environments/docker/sites/reddit/docker_overrides/README.md


@pytest.mark.flaky(reruns=2)
def test_reddit_vote_increments_score(reddit_container, reddit_base_url, reddit_get_logged_page, pw_timeout):
    """Test that voting increments/decrements score correctly.

    Verifies the vote system fix that uses increment/decrement instead of
    recalculating from the votes table (which would reset imported scores).

    The original Postmill code recalculates netScore from the votes collection
    whenever a vote is added. However, the imported database has net_score values
    but no corresponding records in submission_votes tables. This fix ensures:
    - First vote on a post increments/decrements the score (not resets to ±1)
    - Example: A post with score 38 becomes 39 after upvote (not 1)
    """
    page = reddit_get_logged_page()

    # Navigate to a specific post (not the forum listing) to avoid reordering issues
    # This post has score 38 in the original dataset
    post_url = f"{reddit_base_url}/f/AskReddit/10224/why-bleaching-your-butthole-isn-t-called-changing-your-ring"
    page.goto(post_url, timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Find the vote section (there's only one on a single post page)
    score_element = page.locator(".vote__net-score").first
    upvote_button = page.locator(".vote__up").first

    # Get initial score
    initial_score_text = score_element.inner_text(timeout=pw_timeout)
    initial_score = int(initial_score_text)

    # Score should be > 1 (imported data has real scores)
    assert initial_score > 1, f"Expected score > 1 for imported data, got {initial_score}"

    # Click upvote - this submits a form via POST
    upvote_button.click()

    # Wait for score to actually change (the page may reload or use AJAX)
    # Use expect to wait for the text to NOT be the initial value
    expect(score_element).not_to_have_text(str(initial_score), timeout=pw_timeout)

    # Get new score
    new_score_text = score_element.inner_text(timeout=pw_timeout)
    new_score = int(new_score_text)

    # The key test: score should change by exactly ±1 or ±2 (if changing vote direction)
    # NOT reset to 1/-1 which would indicate the bug
    score_diff = abs(new_score - initial_score)
    assert score_diff in (1, 2), (
        f"Vote should change score by 1 or 2, not {score_diff}. Initial: {initial_score}, New: {new_score}."
    )

    # Critical: if initial score was > 5 and new score is 1 or -1, the fix is broken
    # This catches the bug where voting recalculates from empty votes table
    if initial_score > 5:
        assert abs(new_score) > 1, (
            f"Score was reset to {new_score} instead of incrementing from {initial_score}. "
            "This indicates the vote system fix is not applied - votes are being "
            "recalculated from the (empty) votes table instead of incremented."
        )


@pytest.mark.flaky(reruns=2)
def test_reddit_no_rate_limit_on_submissions(reddit_container, reddit_base_url, reddit_get_logged_page, pw_timeout):
    """Test that submissions can be created without rate limiting.

    Verifies that the @RateLimit annotation was removed from SubmissionData,
    allowing multiple submissions to be created in quick succession.
    """
    page = reddit_get_logged_page()
    created_submissions = []

    # Create 2 submissions quickly back-to-back
    for i in range(2):
        page.goto(f"{reddit_base_url}/submit", timeout=pw_timeout)
        page.wait_for_load_state("networkidle", timeout=pw_timeout)

        # Generate unique title
        unique_id = uuid.uuid4().hex[:8]
        title = f"Test submission {i + 1} - {unique_id}"

        # Fill in title (Postmill uses textarea for title)
        page.fill('textarea[name="submission[title]"]', title)

        # Fill in body (optional but good practice)
        page.fill('textarea[name="submission[body]"]', f"This is test submission {i + 1} for rate limit testing.")

        # Select forum using select2 widget
        # Click the select2 container to open dropdown
        page.click(".select2-selection")
        page.wait_for_selector(".select2-search__field", timeout=pw_timeout)
        # Type to search for AskReddit
        page.fill(".select2-search__field", "AskReddit")
        page.wait_for_timeout(300)  # Wait for search results
        # Click the matching option
        page.click(".select2-results__option:has-text('AskReddit')")

        # Submit
        page.click('button:has-text("Create submission")')

        # Wait for navigation (successful submission redirects to the new post)
        page.wait_for_load_state("networkidle", timeout=pw_timeout)

        # Check we're not on the submit page anymore (no rate limit error)
        current_url = page.url
        assert "/submit" not in current_url, (
            f"Submission {i + 1} failed - still on submit page. This may indicate rate limiting is still active."
        )

        # Verify the title appears on the page (we're on the new submission)
        page_content = page.content()
        assert title in page_content or unique_id in page_content, (
            f"Submission {i + 1} title not found on page after submit. URL: {current_url}"
        )

        created_submissions.append(title)

    # Both submissions should have been created successfully
    assert len(created_submissions) == 2, "Expected 2 submissions to be created without rate limiting"


@pytest.mark.flaky(reruns=2)
def test_reddit_link_submission_with_external_url(
    reddit_container, reddit_base_url, reddit_get_logged_page, pw_timeout
):
    """Test that link submissions referencing the external port work correctly.

    Verifies the UrlRewritingHttpClient that rewrites external URLs (e.g.,
    http://localhost:9999/path) to internal localhost (http://localhost/path),
    allowing link submissions that would otherwise be blocked by Postmill's
    NoPrivateNetworkHttpClient.

    Without this fix, submitting a link to the same site on the external port
    would fail because Postmill blocks requests to localhost/private IPs.
    """
    page = reddit_get_logged_page()

    page.goto(f"{reddit_base_url}/submit", timeout=pw_timeout)
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Generate unique title
    unique_id = uuid.uuid4().hex[:8]
    title = f"Link test - {unique_id}"

    # Ensure URL radio is selected (should be default)
    url_radio = page.locator('input[type="radio"][value="url"]')
    if url_radio.count() > 0 and not url_radio.is_checked():
        url_radio.click()

    # Fill in URL pointing to the external port (this tests the URL rewriting)
    # We use a URL to an existing post on the same site
    external_url = f"{reddit_base_url}/f/AskReddit/10224/why-bleaching-your-butthole-isn-t-called-changing-your-ring"
    page.fill('input[name="submission[url]"]', external_url)

    # Fill in title (Postmill uses textarea for title)
    page.fill('textarea[name="submission[title]"]', title)

    # Select forum using select2 widget
    page.click(".select2-selection")
    page.wait_for_selector(".select2-search__field", timeout=pw_timeout)
    page.fill(".select2-search__field", "AskReddit")
    page.wait_for_timeout(300)  # Wait for search results
    page.click(".select2-results__option:has-text('AskReddit')")

    # Submit
    page.click('button:has-text("Create submission")')

    # Wait for result
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    current_url = page.url
    page_content = page.content()

    # Check for common error messages that would indicate the URL rewriting failed
    error_indicators = [
        "could not fetch",
        "private network",
        "blocked",
        "invalid url",
        "connection refused",
    ]
    page_content_lower = page_content.lower()
    for error in error_indicators:
        assert error not in page_content_lower, (
            f"Found error indicator '{error}' in page. URL rewriting may not be working correctly."
        )

    # Verify we're not still on the submit page with an error
    # A successful submission redirects to the new post
    if "/submit" in current_url:
        # Still on submit page - check if there's a form error
        error_elements = page.locator(".form-error, .error, .alert-danger, .flash-error")
        if error_elements.count() > 0:
            error_text = error_elements.first.inner_text()
            pytest.fail(f"Submission failed with error: {error_text}. This may indicate URL rewriting is not working.")

    # Verify the submission was created (title should appear on page)
    assert title in page_content or unique_id in page_content, (
        f"Link submission title not found. URL: {current_url}. The submission may have failed due to URL blocking."
    )
