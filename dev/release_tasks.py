"""Release management tasks."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import semver
from invoke import task

if TYPE_CHECKING:
    from invoke.context import Context

from dev.utils import logging_utils


def _tag_exists(ctx: Context, tag: str) -> bool:
    """Check if a git tag exists on remote."""
    result = ctx.run(f"git ls-remote --tags origin refs/tags/{tag}", hide=True, warn=True)
    if result is None:
        return False
    return bool(result.stdout.strip())


def _release_exists(ctx: Context, tag: str) -> bool:
    """Check if a GitHub release already exists for a tag."""
    result = ctx.run(f'gh release view "{tag}"', hide=True, warn=True)
    if result is None:
        return False
    return result.exited == 0


def _normalize_version(version: str) -> semver.Version:
    """Parse and normalize a release version."""
    normalized = version.removeprefix("v")
    try:
        return semver.Version.parse(normalized)
    except ValueError:
        logging_utils.print_error(
            f"Invalid version: {version}. Expected semver like 1.2.3 or 1.2.3-rc.1",
        )
        sys.exit(1)


@task(name="tag")
@logging_utils.with_banner()
def create_tag(ctx: Context, version: str) -> None:
    """Create and push a git tag for a specific version.

    Args:
        version: Version to tag (e.g. 1.2.3 or v1.2.3).
    """
    normalized_version = _normalize_version(version)
    tag = f"v{normalized_version}"

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
def create_release(ctx: Context, version: str) -> None:
    """Create a GitHub release for a specific version.

    Args:
        version: Version to release (e.g. 1.2.3 or v1.2.3).
    """
    normalized_version = _normalize_version(version)
    tag = f"v{normalized_version}"

    if _release_exists(ctx, tag):
        logging_utils.print_success(f"GitHub release {tag} already exists; skipping")
        return

    if not _tag_exists(ctx, tag):
        logging_utils.print_info(f"Tag {tag} does not exist; creating and pushing it first...")
        ctx.run(f'git tag -a "{tag}" -m "Release {tag}"')
        ctx.run(f'git push origin "{tag}"')

    logging_utils.print_info(f"Creating GitHub release {tag}...")
    ctx.run(f'gh release create "{tag}" --generate-notes --title "{tag}"')

    logging_utils.print_success(f"Created GitHub release {tag}")
