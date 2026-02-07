"""Release management tasks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import semver
from datasets import load_dataset
from huggingface_hub import upload_folder
from invoke import task
from invoke.exceptions import UnexpectedExit

if TYPE_CHECKING:
    from invoke.context import Context

from dev.utils import hf_dataset_utils, logging_utils


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


@task(name="build-hf-dataset")
@logging_utils.with_banner()
def build_hf_dataset(
    ctx: Context, version: str | None = None, output_dir: str = str(hf_dataset_utils.HF_BUILD_DIR)
) -> None:
    """Build HF dataset release artifacts under output/build/hf_dataset.

    Args:
        version: Release version tag (e.g. v1.2.3). If omitted, auto-detect from HEAD tag.
        output_dir: Output directory for generated artifacts.
    """
    try:
        resolved_version = hf_dataset_utils.resolve_release_version(version)
        build_dir = Path(output_dir)
        hf_dataset_utils.generate_hf_release_artifacts(ctx, resolved_version, build_dir)
        full = load_dataset("parquet", data_files=str(build_dir / "full.parquet"), split="train")
        hard = load_dataset("parquet", data_files=str(build_dir / "hard.parquet"), split="train")

        logging_utils.print_success(
            "HF dataset artifacts generated",
            version=resolved_version,
            output=str(build_dir),
            full=len(full),
            hard=len(hard),
        )
    except (RuntimeError, subprocess.CalledProcessError, UnexpectedExit) as exc:
        logging_utils.print_error(str(exc))
        sys.exit(1)


@task(name="upload-hf-dataset")
@logging_utils.with_banner(exclude={"token"})
def upload_hf_dataset(
    ctx: Context,
    version: str | None = None,
    repo_id: str = "AmineHA/WebArena-Verified",
    folder_path: str = str(hf_dataset_utils.HF_BUILD_DIR),
    token: str | None = None,
    dry_run: bool = False,
    skip_tag_check: bool = False,
) -> None:
    """Upload HF dataset release artifacts and enforce matching HF tag.

    Args:
        version: Release version tag (e.g. v1.2.3). If omitted, auto-detect from HEAD tag.
        repo_id: HF dataset repository id.
        folder_path: Folder containing release artifacts.
        token: Optional HF token. If omitted, uses cached login/session.
        dry_run: Validate and compute upload mode, but skip HF write operations.
        skip_tag_check: Skip git tag-on-HEAD verification (only allowed with dry_run).
    """
    try:
        _ = ctx
        if skip_tag_check and not dry_run:
            raise RuntimeError("--skip-tag-check can only be used with --dry-run")

        if skip_tag_check:
            if version is None:
                raise RuntimeError("--skip-tag-check requires --version")
            hf_dataset_utils.validate_release_version(version)
            resolved_version = version
        else:
            resolved_version = hf_dataset_utils.resolve_release_version(version)

        folder = Path(folder_path)
        required_preflight = ["version.json", "README.md", "full.parquet", "hard.parquet"]
        if dry_run:
            missing = hf_dataset_utils.missing_release_files(folder, required_preflight)
            if missing:
                logging_utils.print_info("Dry run detected missing artifacts; building locally before validation...")
                hf_dataset_utils.generate_hf_release_artifacts(ctx, resolved_version, folder)

        hf_dataset_utils.assert_hf_release_files_exist(folder, ["version.json", "README.md"])

        version_payload = json.loads((folder / "version.json").read_text(encoding="utf-8"))
        stamped_version = version_payload.get("version")
        if stamped_version != resolved_version:
            msg = f"Version mismatch: version.json has '{stamped_version}', expected '{resolved_version}'"
            raise RuntimeError(msg)

        local_hash = version_payload.get("dataset_hash")
        if not isinstance(local_hash, str) or not local_hash:
            raise RuntimeError("version.json must include a non-empty 'dataset_hash' field")

        remote_hash = hf_dataset_utils.get_remote_dataset_hash(repo_id=repo_id, token=token)
        data_changed = remote_hash != local_hash
        allow_patterns = (
            ["full.parquet", "hard.parquet", "version.json", "README.md"]
            if data_changed
            else ["version.json", "README.md"]
        )
        upload_mode = "full" if data_changed else "metadata-only"

        if data_changed:
            hf_dataset_utils.assert_hf_release_files_exist(folder, ["full.parquet", "hard.parquet"])

        if dry_run:
            logging_utils.print_success(
                "Dry run passed; HF upload skipped",
                version=resolved_version,
                repo_id=repo_id,
                folder_path=str(folder),
                upload_mode=upload_mode,
                dataset_hash=local_hash,
                remote_dataset_hash=remote_hash or "none",
            )
            return

        upload_folder(
            folder_path=str(folder),
            repo_id=repo_id,
            repo_type="dataset",
            allow_patterns=allow_patterns,
            commit_message=f"dataset: {resolved_version}",
            token=token,
        )

        logging_utils.print_success(
            "HF dataset upload completed",
            version=resolved_version,
            repo_id=repo_id,
            folder_path=str(folder),
            upload_mode=upload_mode,
            dataset_hash=local_hash,
            tag_created=False,
        )
    except (RuntimeError, subprocess.CalledProcessError, UnexpectedExit) as exc:
        logging_utils.print_error(str(exc))
        sys.exit(1)
