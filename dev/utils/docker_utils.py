"""Docker-related utilities for building and pushing images."""

import subprocess
import tomllib

import semver

# Docker image
DOCKER_IMAGE = "am1n3e/webarena-verified"

# Git remote
GIT_REPO_URL = "https://github.com/ServiceNow/webarena-verified.git"


def get_version() -> str:
    """Get version from pyproject.toml."""
    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    return pyproject["project"]["version"]


def validate_semver(version: str) -> None:
    """Validate that version is a valid semver string.

    Args:
        version: The version string to validate (e.g., "1.0.0")

    Raises:
        ValueError: If version is not a valid semver
    """
    try:
        semver.Version.parse(version)
    except ValueError as e:
        raise ValueError(f"Invalid semver version '{version}': {e}") from e


def check_repo_clean_at_tag(version: str) -> None:
    """Verify the git repo is clean and HEAD is at the version tag.

    Args:
        version: The version string (e.g., "0.1.0") to check against tag "v{version}"

    Raises:
        RuntimeError: If repo has uncommitted/untracked files or HEAD is not at the tag
        ValueError: If version is not a valid semver
    """
    try:
        semver.Version.parse(version)
    except ValueError as e:
        raise ValueError(f"Invalid semver version '{version}': {e}") from e

    tag = f"v{version}"

    # Check for uncommitted or untracked files
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    if result.stdout.strip():
        raise RuntimeError(
            f"Repository has uncommitted or untracked files. Please commit or stash changes before building.\n"
            f"Dirty files:\n{result.stdout}"
        )

    # Check if HEAD is at the expected tag
    result = subprocess.run(
        ["git", "describe", "--exact-match", "--tags", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"HEAD is not at any tag. Please checkout tag '{tag}' before building.")

    current_tag = result.stdout.strip()
    if current_tag != tag:
        raise RuntimeError(
            f"HEAD is at tag '{current_tag}', but expected '{tag}'. Please checkout tag '{tag}' before building."
        )


def confirm(prompt: str) -> bool:
    """Prompt user for yes/no confirmation."""
    while True:
        response = input(f"{prompt} [y/n]: ").strip().lower()
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'")
