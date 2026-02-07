"""Release management tasks."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import semver
from datasets import Dataset, load_dataset
from datasets.exceptions import DatasetGenerationError
from huggingface_hub import HfApi, hf_hub_download, upload_folder
from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError, RevisionNotFoundError
from invoke import task
from invoke.exceptions import UnexpectedExit
from jinja2 import Environment, FileSystemLoader, StrictUndefined

if TYPE_CHECKING:
    from invoke.context import Context

from dev import hf_dataset_utils
from dev.utils import logging_utils

HF_BUILD_DIR = Path("output/build/hf_dataset")
HF_TEMPLATE_PATH = Path("assets/hf_dataset/README.md.jinja2")
DATASET_SRC = Path("assets/dataset/webarena-verified.json")
HARD_SUBSET_PATH = Path("assets/dataset/subsets/webarena-verified-hard.json")
EXPECTED_FULL_ROWS = 812
EXPECTED_HARD_ROWS = 258


def _write_json(path: Path, payload: dict[str, str]) -> None:
    """Write JSON payload with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def _render_hf_readme(
    output_readme: Path,
    version: str,
    git_commit: str,
    generated_at: str,
    dataset_hash: str,
    full_count: int,
    hard_count: int,
    schema: list[tuple[str, str]],
) -> None:
    """Render dataset card from Jinja2 template."""
    if not HF_TEMPLATE_PATH.exists():
        raise RuntimeError(f"Template file not found: {HF_TEMPLATE_PATH}")

    env = Environment(
        loader=FileSystemLoader(str(HF_TEMPLATE_PATH.parent)),
        autoescape=False,
        lstrip_blocks=True,
        trim_blocks=True,
        undefined=StrictUndefined,
    )
    template = env.get_template(HF_TEMPLATE_PATH.name)
    rendered = template.render(
        version=version,
        git_commit=git_commit,
        generated_at=generated_at,
        dataset_hash=dataset_hash,
        full_count=full_count,
        hard_count=hard_count,
        schema=schema,
    )
    output_readme.write_text(f"{rendered.rstrip()}\n", encoding="utf-8")


def _build_hf_dataset_files(ctx: Context, output_dir: Path) -> tuple[int, int, list[tuple[str, str]]]:
    """Build full/hard JSON + parquet with strict validation."""
    full_json = output_dir / "full.json"
    hard_json = output_dir / "hard.json"
    full_parquet = output_dir / "full.parquet"
    hard_parquet = output_dir / "hard.parquet"

    shutil.copy2(DATASET_SRC, full_json)

    ctx.run(
        f"uv run webarena-verified subset-export --path {HARD_SUBSET_PATH} --output {hard_json}",
        hide=True,
    )

    full = _load_hf_json_dataset(full_json)
    hard = _load_hf_json_dataset(hard_json)

    full_count = len(full)
    hard_count = len(hard)
    full_ids = set(full["task_id"])
    hard_ids = set(hard["task_id"])

    if full_count != EXPECTED_FULL_ROWS:
        raise RuntimeError(
            f"Validation failed: full split expected {EXPECTED_FULL_ROWS}, got {full_count}"
        )
    if hard_count != EXPECTED_HARD_ROWS:
        raise RuntimeError(
            f"Validation failed: hard split expected {EXPECTED_HARD_ROWS}, got {hard_count}"
        )
    if not hard_ids.issubset(full_ids):
        raise RuntimeError("Validation failed: hard.task_id is not a subset of full.task_id")

    full.to_parquet(str(full_parquet))
    hard.to_parquet(str(hard_parquet))

    schema = [(name, str(feature)) for name, feature in full.features.items()]
    return full_count, hard_count, schema


def _load_hf_json_dataset(path: Path) -> Dataset:
    """Load a JSON split with a fallback for mixed nested types.

    The fallback keeps row order and normalizes nested dict/list values to JSON strings,
    which avoids Arrow schema inference failures on heterogeneous nested objects.
    """
    try:
        return load_dataset("json", data_files=str(path), split="train")
    except DatasetGenerationError:
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise RuntimeError(f"Expected JSON array in {path}") from None

        for row in rows:
            if not isinstance(row, dict):
                raise RuntimeError(f"Expected object rows in {path}") from None
            for key, value in list(row.items()):
                if isinstance(value, dict | list):
                    row[key] = json.dumps(value, sort_keys=True)

        return Dataset.from_list(rows)


def _generate_hf_release_artifacts(ctx: Context, resolved_version: str, build_dir: Path) -> None:
    """Generate all HF release artifacts into build_dir."""
    build_dir.mkdir(parents=True, exist_ok=True)
    full_count, hard_count, schema = _build_hf_dataset_files(ctx, build_dir)
    git_commit = hf_dataset_utils.run_capture(["git", "rev-parse", "HEAD"])
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    dataset_hash = hf_dataset_utils.compute_dataset_hash([DATASET_SRC, HARD_SUBSET_PATH])

    _write_json(
        build_dir / "version.json",
        {
            "version": resolved_version,
            "git_commit": git_commit,
            "generated_at": generated_at,
            "dataset_hash": dataset_hash,
        },
    )

    _render_hf_readme(
        output_readme=build_dir / "README.md",
        version=resolved_version,
        git_commit=git_commit,
        generated_at=generated_at,
        dataset_hash=dataset_hash,
        full_count=full_count,
        hard_count=hard_count,
        schema=schema,
    )


def _missing_release_files(folder: Path, required: list[str]) -> list[str]:
    """Return missing required files in folder."""
    return [name for name in required if not (folder / name).exists()]


def _assert_hf_release_files_exist(folder: Path, required: list[str]) -> None:
    """Ensure required release files are present before upload."""
    missing = _missing_release_files(folder, required)
    if missing:
        msg = f"Missing required files in {folder}: {', '.join(missing)}"
        raise RuntimeError(msg)


def _ensure_hf_tag(
    repo_id: str,
    version: str,
    revision: str,
    token: str | None = None,
) -> None:
    """Create or verify matching HF dataset tag."""
    api = HfApi(token=token)
    expected_revision = revision
    expected_commit: str | None = None
    branch_refs = api.list_repo_refs(repo_id=repo_id, repo_type="dataset").branches
    for branch in branch_refs:
        if branch.name == revision:
            expected_commit = branch.target_commit
            break
    if expected_commit is None and re.fullmatch(r"[0-9a-f]{7,40}", revision):
        expected_commit = revision

    api.create_tag(
        repo_id=repo_id,
        repo_type="dataset",
        tag=version,
        revision=expected_revision,
        exist_ok=True,
    )

    refs = api.list_repo_refs(repo_id=repo_id, repo_type="dataset")
    tag_ref = next((tag for tag in refs.tags if tag.name == version), None)
    if tag_ref is None:
        raise RuntimeError(f"HF tag verification failed: tag '{version}' not found on {repo_id}")
    if expected_commit is not None and tag_ref.target_commit != expected_commit:
        raise RuntimeError(
            f"HF tag verification failed: tag '{version}' points to {tag_ref.target_commit}, "
            f"expected {expected_commit}"
        )


def _get_remote_dataset_hash(repo_id: str, token: str | None = None) -> str | None:
    """Fetch dataset_hash from HF main branch version.json, if present."""
    try:
        version_path = hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            filename="version.json",
            revision="main",
            token=token,
        )
    except (EntryNotFoundError, RepositoryNotFoundError, RevisionNotFoundError):
        return None

    payload = json.loads(Path(version_path).read_text(encoding="utf-8"))
    dataset_hash = payload.get("dataset_hash")
    if dataset_hash is None:
        return None
    if not isinstance(dataset_hash, str):
        raise RuntimeError("HF version.json contains non-string dataset_hash")
    return dataset_hash


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
def build_hf_dataset(ctx: Context, version: str | None = None, output_dir: str = str(HF_BUILD_DIR)) -> None:
    """Build HF dataset release artifacts under output/build/hf_dataset.

    Args:
        version: Release version tag (e.g. v1.2.3). If omitted, auto-detect from HEAD tag.
        output_dir: Output directory for generated artifacts.
    """
    try:
        resolved_version = hf_dataset_utils.resolve_release_version(version)
        build_dir = Path(output_dir)
        _generate_hf_release_artifacts(ctx, resolved_version, build_dir)
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
    folder_path: str = str(HF_BUILD_DIR),
    token: str | None = None,
    create_pr: bool = False,
    dry_run: bool = False,
    skip_tag_check: bool = False,
) -> None:
    """Upload HF dataset release artifacts and enforce matching HF tag.

    Args:
        version: Release version tag (e.g. v1.2.3). If omitted, auto-detect from HEAD tag.
        repo_id: HF dataset repository id.
        folder_path: Folder containing release artifacts.
        token: Optional HF token. If omitted, uses cached login/session.
        create_pr: Whether to open a PR instead of direct commit upload.
        dry_run: Validate and compute upload mode, but skip HF write operations.
        skip_tag_check: Skip git tag-on-HEAD verification (only allowed with dry_run).
    """
    try:
        _ = ctx
        if skip_tag_check and not dry_run:
            raise RuntimeError("--skip-tag-check can only be used with --dry-run")
        if create_pr and not dry_run:
            raise RuntimeError("--create-pr is not compatible with tagging; upload after merge without --create-pr")

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
            missing = _missing_release_files(folder, required_preflight)
            if missing:
                logging_utils.print_info(
                    "Dry run detected missing artifacts; building locally before validation..."
                )
                _generate_hf_release_artifacts(ctx, resolved_version, folder)

        _assert_hf_release_files_exist(folder, ["version.json", "README.md"])

        version_payload = json.loads((folder / "version.json").read_text(encoding="utf-8"))
        stamped_version = version_payload.get("version")
        if stamped_version != resolved_version:
            msg = (
                "Version mismatch: version.json has "
                f"'{stamped_version}', expected '{resolved_version}'"
            )
            raise RuntimeError(msg)

        local_hash = version_payload.get("dataset_hash")
        if not isinstance(local_hash, str) or not local_hash:
            raise RuntimeError("version.json must include a non-empty 'dataset_hash' field")

        remote_hash = _get_remote_dataset_hash(repo_id=repo_id, token=token)
        data_changed = remote_hash != local_hash
        allow_patterns = (
            ["full.parquet", "hard.parquet", "version.json", "README.md"]
            if data_changed
            else ["version.json", "README.md"]
        )
        upload_mode = "full" if data_changed else "metadata-only"

        if data_changed:
            _assert_hf_release_files_exist(folder, ["full.parquet", "hard.parquet"])

        if dry_run:
            logging_utils.print_success(
                "Dry run passed; HF upload skipped",
                version=resolved_version,
                repo_id=repo_id,
                folder_path=str(folder),
                create_pr=create_pr,
                upload_mode=upload_mode,
                dataset_hash=local_hash,
                remote_dataset_hash=remote_hash or "none",
            )
            return

        commit_info = upload_folder(
            folder_path=str(folder),
            repo_id=repo_id,
            repo_type="dataset",
            allow_patterns=allow_patterns,
            commit_message=f"dataset: {resolved_version}",
            create_pr=create_pr,
            token=token,
        )

        _ensure_hf_tag(
            repo_id=repo_id,
            version=resolved_version,
            revision=commit_info.oid,
            token=token,
        )

        logging_utils.print_success(
            "HF dataset upload completed",
            version=resolved_version,
            repo_id=repo_id,
            folder_path=str(folder),
            create_pr=create_pr,
            upload_mode=upload_mode,
            dataset_hash=local_hash,
        )
    except (RuntimeError, subprocess.CalledProcessError, UnexpectedExit) as exc:
        logging_utils.print_error(str(exc))
        sys.exit(1)
