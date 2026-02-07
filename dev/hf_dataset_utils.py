"""Helpers for HF dataset release tasks."""

from __future__ import annotations

import hashlib
import subprocess
from typing import TYPE_CHECKING

import semver

if TYPE_CHECKING:
    from pathlib import Path

RELEASE_VERSION_PREFIX = "v"


def run_capture(cmd: list[str]) -> str:
    """Run a subprocess command and return stdout text."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def validate_release_version(version: str) -> None:
    """Validate version against release tag format."""
    if not version.startswith(RELEASE_VERSION_PREFIX):
        raise RuntimeError(f"Invalid version '{version}'. Expected format like v1.2.3 or v1.2.3-rc.1")

    normalized = version.removeprefix(RELEASE_VERSION_PREFIX)
    try:
        semver.Version.parse(normalized)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid version '{version}'. Expected format like v1.2.3 or v1.2.3-rc.1"
        ) from exc


def get_release_tags_on_head() -> list[str]:
    """Return valid semver release tags that point to HEAD."""
    tags_output = run_capture(["git", "tag", "--points-at", "HEAD"])
    if not tags_output:
        return []

    valid_tags: list[str] = []
    for tag in tags_output.splitlines():
        try:
            validate_release_version(tag)
        except RuntimeError:
            continue
        valid_tags.append(tag)
    return valid_tags


def resolve_release_version(version: str | None) -> str:
    """Resolve and validate the release version.

    Rules:
    - If version is provided, it must be valid and point to HEAD.
    - If version is omitted, exactly one valid release tag must point to HEAD.
    """
    head_tags = get_release_tags_on_head()

    if version:
        validate_release_version(version)
        if version not in head_tags:
            msg = (
                f"Provided version '{version}' does not match a tag on HEAD. "
                f"Tags on HEAD: {head_tags or 'none'}"
            )
            raise RuntimeError(msg)
        return version

    if len(head_tags) != 1:
        msg = (
            "Auto-detect requires exactly one release tag on HEAD. "
            f"Found: {head_tags or 'none'}"
        )
        raise RuntimeError(msg)

    return head_tags[0]


def compute_dataset_hash(paths: list[Path]) -> str:
    """Compute a stable hash over dataset-defining JSON sources only."""
    hasher = hashlib.sha256()
    for path in paths:
        data = path.read_bytes()
        hasher.update(path.as_posix().encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(data)
        hasher.update(b"\0")
    return hasher.hexdigest()
