"""Release management tasks."""

from __future__ import annotations

import sys
import tomllib
from enum import Enum
from typing import TYPE_CHECKING

import semver
from invoke import task

if TYPE_CHECKING:
    from invoke.context import Context

from dev.utils import logging_utils
from dev.utils.path_utils import get_repo_root


class BumpType(str, Enum):
    """Version bump types."""

    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


def _get_current_version() -> semver.Version:
    """Read current version from pyproject.toml."""
    pyproject_path = get_repo_root() / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    version_str = data["project"]["version"]
    return semver.Version.parse(version_str)


def _bump_version(current: semver.Version, bump: BumpType) -> semver.Version:
    """Calculate new version based on bump type."""
    if bump == BumpType.MAJOR:
        return current.bump_major()
    elif bump == BumpType.MINOR:
        return current.bump_minor()
    else:
        return current.bump_patch()


def _update_pyproject_version(new_version: semver.Version) -> None:
    """Update version in pyproject.toml."""
    pyproject_path = get_repo_root() / "pyproject.toml"
    content = pyproject_path.read_text()

    # Read current version to find exact string to replace
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    old_version = data["project"]["version"]

    updated = content.replace(f'version = "{old_version}"', f'version = "{new_version}"', 1)
    pyproject_path.write_text(updated)


def _tag_exists(ctx: Context, tag: str) -> bool:
    """Check if a git tag exists on remote."""
    result = ctx.run(f"git ls-remote --tags origin refs/tags/{tag}", hide=True, warn=True)
    return bool(result.stdout.strip())


@task(name="bump-version")
@logging_utils.with_banner()
def bump_version(ctx: Context, bump: str) -> None:
    """Bump version in pyproject.toml.

    Args:
        bump: Version bump type (patch, minor, major).
    """
    try:
        bump_type = BumpType(bump)
    except ValueError:
        logging_utils.print_error(f"Invalid bump type: {bump}. Must be one of: patch, minor, major")
        sys.exit(1)

    current = _get_current_version()
    new_version = _bump_version(current, bump_type)

    logging_utils.print_info(f"Bumping version: {current} -> {new_version}")
    _update_pyproject_version(new_version)
    logging_utils.print_success(f"Updated pyproject.toml to version {new_version}")


@task(name="lint")
@logging_utils.with_banner()
def lint(ctx: Context) -> None:
    """Run linting and type checking."""
    logging_utils.print_info("Running ruff check...")
    ctx.run("uv run ruff check")

    logging_utils.print_info("Running ruff format check...")
    ctx.run("uv run ruff format --check")

    logging_utils.print_info("Running ty check...")
    ctx.run("uv run ty check src dev tests")

    logging_utils.print_success("All checks passed")


@task(name="test")
@logging_utils.with_banner()
def test(ctx: Context, docker_img: str = "webarena-verified:test") -> None:
    """Run tests.

    Args:
        docker_img: Docker image to use for tests.
    """
    logging_utils.print_info("Installing Playwright browsers...")
    ctx.run("uv run playwright install chromium --with-deps")

    logging_utils.print_info("Building Docker image...")
    ctx.run(f"docker build -t {docker_img} .")

    logging_utils.print_info("Running tests...")
    ctx.run(
        f"uv run pytest --webarena-verified-docker-img {docker_img} "
        "--ignore=tests/integration/environment_control/ "
        "--ignore=tests/integration/environments/"
    )

    logging_utils.print_success("All tests passed")


@task(name="tag")
@logging_utils.with_banner()
def create_tag(ctx: Context, version: str | None = None) -> None:
    """Create and push a git tag for current version.

    Args:
        version: Version to tag (default: read from pyproject.toml).
    """
    if version is None:
        version = str(_get_current_version())

    tag = f"v{version}"

    if _tag_exists(ctx, tag):
        logging_utils.print_error(f"Tag {tag} already exists")
        sys.exit(1)

    logging_utils.print_info(f"Creating tag {tag}...")
    ctx.run(f'git tag -a "{tag}" -m "Release {tag}"')

    logging_utils.print_info(f"Pushing tag {tag}...")
    ctx.run(f'git push origin "{tag}"')

    logging_utils.print_success(f"Created and pushed tag {tag}")


@task(name="create-release")
@logging_utils.with_banner()
def create_release(ctx: Context, version: str | None = None) -> None:
    """Create a GitHub release for current version.

    Args:
        version: Version to release (default: read from pyproject.toml).
    """
    if version is None:
        version = str(_get_current_version())

    tag = f"v{version}"

    logging_utils.print_info(f"Creating GitHub release {tag}...")
    ctx.run(f'gh release create "{tag}" --generate-notes --title "{tag}"')

    logging_utils.print_success(f"Created GitHub release {tag}")


@task(name="release", pre=[lint])
@logging_utils.with_banner()
def release(ctx: Context, bump: str, skip_tests: bool = False) -> None:
    """Run full release workflow: bump, lint, test, commit, tag, release.

    Args:
        bump: Version bump type (patch, minor, major).
        skip_tests: Skip running tests (for CI where tests run separately).
    """
    try:
        bump_type = BumpType(bump)
    except ValueError:
        logging_utils.print_error(f"Invalid bump type: {bump}. Must be one of: patch, minor, major")
        sys.exit(1)

    # Calculate versions
    current = _get_current_version()
    new_version = _bump_version(current, bump_type)
    tag = f"v{new_version}"

    # Check tag doesn't exist
    if _tag_exists(ctx, tag):
        logging_utils.print_error(f"Tag {tag} already exists")
        sys.exit(1)

    # Bump version
    logging_utils.print_info(f"Bumping version: {current} -> {new_version}")
    _update_pyproject_version(new_version)

    # Run tests (unless skipped)
    if not skip_tests:
        test(ctx)

    # Commit version bump
    logging_utils.print_info("Committing version bump...")
    ctx.run("git add pyproject.toml")
    ctx.run(f'git commit -m "Bump version to {new_version}"')
    ctx.run("git push")

    # Create and push tag
    logging_utils.print_info(f"Creating tag {tag}...")
    ctx.run(f'git tag -a "{tag}" -m "Release {tag}"')
    ctx.run(f'git push origin "{tag}"')

    # Create GitHub release
    logging_utils.print_info(f"Creating GitHub release {tag}...")
    ctx.run(f'gh release create "{tag}" --generate-notes --title "{tag}"')

    logging_utils.print_success(f"Released {tag}")
