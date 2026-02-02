"""Basic HTTP health tests for Reddit (Postmill) Docker container.

Tests basic connectivity to the Reddit forum without requiring Playwright.

Usage:
    pytest tests/integration/environments/reddit/test_basic.py
"""

import http.cookiejar
import urllib.request

import pytest


@pytest.mark.integration_docker_reddit
@pytest.mark.flaky(reruns=2)
def test_reddit_homepage_responds(reddit_container, reddit_base_url):
    """Test that homepage responds with 200."""
    req = urllib.request.Request(reddit_base_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200


@pytest.mark.integration_docker_reddit
@pytest.mark.flaky(reruns=2)
def test_reddit_homepage_contains_postmill(reddit_container, reddit_base_url):
    """Test that homepage contains 'Postmill' branding."""
    req = urllib.request.Request(reddit_base_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        content = response.read().decode("utf-8")
        assert "Postmill" in content


@pytest.mark.integration_docker_reddit
@pytest.mark.flaky(reruns=2)
def test_reddit_login_page_accessible(reddit_container, reddit_base_url):
    """Test that login page is accessible."""
    login_url = f"{reddit_base_url}/login"
    # Login page does a cookie check redirect, so we need a cookie jar
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    req = urllib.request.Request(login_url, method="GET")
    with opener.open(req, timeout=10) as response:
        assert response.status == 200


@pytest.mark.integration_docker_reddit
@pytest.mark.flaky(reruns=2)
def test_reddit_forums_page_accessible(reddit_container, reddit_base_url):
    """Test that forums listing page is accessible."""
    forums_url = f"{reddit_base_url}/forums"
    req = urllib.request.Request(forums_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200
