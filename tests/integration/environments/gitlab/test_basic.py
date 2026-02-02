"""Basic HTTP health tests for GitLab Docker container.

Tests basic connectivity to the GitLab instance without requiring Playwright.

Usage:
    pytest tests/integration/environments/gitlab/test_basic.py
"""

import urllib.request

import pytest


@pytest.mark.integration_docker_gitlab
@pytest.mark.flaky(reruns=2)
def test_gitlab_homepage_responds(gitlab_container, gitlab_base_url):
    """Test that homepage responds with 200."""
    req = urllib.request.Request(gitlab_base_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200


@pytest.mark.integration_docker_gitlab
@pytest.mark.flaky(reruns=2)
def test_gitlab_login_page_accessible(gitlab_container, gitlab_base_url):
    """Test that login page is accessible."""
    login_url = f"{gitlab_base_url}/users/sign_in"
    req = urllib.request.Request(login_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200


@pytest.mark.integration_docker_gitlab
@pytest.mark.flaky(reruns=2)
def test_gitlab_api_accessible(gitlab_container, gitlab_base_url):
    """Test that GitLab API endpoint is accessible."""
    api_url = f"{gitlab_base_url}/api/v4/projects"
    req = urllib.request.Request(api_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200
