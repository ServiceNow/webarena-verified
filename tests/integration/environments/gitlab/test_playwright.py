"""Playwright UI tests for GitLab Docker container.

Tests GitLab functionality using browser automation.

Test categories:
- User Login: Authentication flow
- Issue Management: Create and update issues
- Project Management: Update project settings

Usage:
    pytest tests/integration/environments/gitlab/test_playwright.py
    pytest tests/integration/environments/gitlab/test_playwright.py --headed
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.docker, pytest.mark.integration_docker_gitlab]

# =============================================================================
# User Login Tests
# =============================================================================


@pytest.mark.flaky(reruns=2)
def test_gitlab_user_login(gitlab_container, gitlab_base_url, gitlab_credentials, page, pw_timeout):
    """Test user login flow."""
    page.goto(f"{gitlab_base_url}/users/sign_in")

    # Wait for and fill login form using test IDs
    page.get_by_test_id("username-field").fill(gitlab_credentials["username"])
    page.get_by_test_id("password-field").fill(gitlab_credentials["password"])
    page.get_by_test_id("sign-in-button").click()

    # Wait for redirect to dashboard and verify logged in
    page.wait_for_url("**/", timeout=pw_timeout)
    expect(page.get_by_role("heading", name="Projects")).to_be_visible(timeout=pw_timeout)


# =============================================================================
# Issue Management Tests
# =============================================================================


@pytest.mark.flaky(reruns=2)
def test_gitlab_create_issue(gitlab_container, gitlab_base_url, gitlab_logged_in_page, pw_timeout):
    """Test creating a new issue."""
    page = gitlab_logged_in_page
    project_path = "byteblaze/a11y-syntax-highlighting"

    # Navigate to new issue page
    page.goto(f"{gitlab_base_url}/{project_path}/-/issues/new")

    # Fill in issue details using role-based selectors
    issue_title = "Test Issue Created by Playwright"
    issue_description = "This is a test issue created by automated Playwright tests."

    page.get_by_role("textbox", name="Title (required)").fill(issue_title)
    page.get_by_role("textbox", name="Description").fill(issue_description)
    page.get_by_role("button", name="Create issue").click()

    # Wait for issue to be created and verify
    page.wait_for_url(f"**/{project_path}/-/issues/*", timeout=pw_timeout)
    expect(page.get_by_role("heading", name=issue_title)).to_be_visible(timeout=pw_timeout)


@pytest.mark.flaky(reruns=2)
def test_gitlab_update_issue_title(gitlab_container, gitlab_base_url, gitlab_logged_in_page, pw_timeout):
    """Test updating an existing issue's title."""
    page = gitlab_logged_in_page
    project_path = "byteblaze/a11y-webring.club"
    issue_number = "21"

    # Navigate to existing issue
    page.goto(f"{gitlab_base_url}/{project_path}/-/issues/{issue_number}")

    # Get original title
    original_title = page.locator("h1.title").first.inner_text()

    # Click edit button
    page.get_by_role("button", name="Edit title and description").click()

    # Wait for edit form and update title
    title_input = page.get_by_role("textbox", name="Title")
    title_input.wait_for(timeout=pw_timeout)
    updated_title = f"{original_title} [Updated]"
    title_input.fill(updated_title)

    # Save changes
    page.get_by_role("button", name="Save changes").click()
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Verify title was updated
    expect(page.locator("h1.title").first).to_contain_text("[Updated]", timeout=pw_timeout)

    # Restore original title
    page.get_by_role("button", name="Edit title and description").click()
    title_input = page.get_by_role("textbox", name="Title")
    title_input.wait_for(timeout=pw_timeout)
    title_input.fill(original_title)
    page.get_by_role("button", name="Save changes").click()


@pytest.mark.flaky(reruns=2)
def test_gitlab_close_and_reopen_issue(gitlab_container, gitlab_base_url, gitlab_logged_in_page, pw_timeout):
    """Test closing and reopening an issue."""
    page = gitlab_logged_in_page
    project_path = "byteblaze/a11y-webring.club"
    issue_number = "21"

    # Navigate to existing issue
    page.goto(f"{gitlab_base_url}/{project_path}/-/issues/{issue_number}")
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Define button locators
    reopen_button = page.get_by_role("button", name="Reopen issue").first
    close_button = page.get_by_role("button", name="Close issue").first

    # Check if issue is already closed and reopen it first if needed
    if reopen_button.is_visible():
        # Issue is closed, reopen it first
        reopen_button.click()
        page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Now close the issue
    close_button.wait_for(state="visible", timeout=pw_timeout)
    close_button.click()
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Verify issue is closed by checking "Reopen issue" button is now visible
    expect(reopen_button).to_be_visible(timeout=pw_timeout)

    # Reopen the issue
    reopen_button.click()
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Verify issue is open again by checking "Close issue" button is visible
    expect(close_button).to_be_visible(timeout=pw_timeout)


# =============================================================================
# Project Management Tests
# =============================================================================


@pytest.mark.flaky(reruns=2)
def test_gitlab_update_project_description(gitlab_container, gitlab_base_url, gitlab_logged_in_page, pw_timeout):
    """Test updating a project's description."""
    page = gitlab_logged_in_page
    project_path = "byteblaze/a11y-syntax-highlighting"

    # Navigate to project settings
    page.goto(f"{gitlab_base_url}/{project_path}/edit")

    # Get the description textarea
    description_input = page.get_by_role("textbox", name="Project description")
    description_input.wait_for(timeout=pw_timeout)

    # Get original description
    original_description = description_input.input_value()

    # Update description
    updated_description = f"{original_description} [Test Update]"
    description_input.fill(updated_description)

    # Save changes
    page.get_by_role("button", name="Save changes").first.click()
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Verify description was updated
    expect(description_input).to_have_value(updated_description, timeout=pw_timeout)

    # Restore original description
    description_input.fill(original_description)
    page.get_by_role("button", name="Save changes").first.click()
    page.wait_for_load_state("networkidle", timeout=pw_timeout)


@pytest.mark.flaky(reruns=2)
def test_gitlab_navigate_project_repository(gitlab_container, gitlab_base_url, gitlab_logged_in_page, pw_timeout):
    """Test navigating to project repository."""
    page = gitlab_logged_in_page
    project_path = "byteblaze/a11y-syntax-highlighting"

    # Navigate to repository
    page.goto(f"{gitlab_base_url}/{project_path}/-/tree/main")
    page.wait_for_load_state("networkidle", timeout=pw_timeout)

    # Verify we can see files in the repository (use .first() as README.md appears in both
    # the file table and the readme preview section)
    expect(page.get_by_role("link", name="README.md").first).to_be_visible(timeout=pw_timeout)
