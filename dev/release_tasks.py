"""Release management tasks."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import semver
from datasets import load_dataset
from huggingface_hub import HfApi, hf_hub_download, upload_folder
from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError, RevisionNotFoundError
from invoke import task
from jinja2 import Environment, FileSystemLoader, StrictUndefined

if TYPE_CHECKING:
    from invoke.context import Context

from dev.utils import logging_utils

HF_BUILD_DIR = Path("output/build/hf_dataset")
HF_TEMPLATE_PATH = Path("assets/hf_dataset/README.md.jinja2")
DATASET_SRC = Path("assets/dataset/webarena-verified.json")
HARD_SUBSET_PATH = Path("assets/dataset/subsets/webarena-verified-hard.json")
RELEASE_VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+([-.].+)?$")
EXPECTED_FULL_ROWS = 812
EXPECTED_HARD_ROWS = 258


class ReleaseSpecError(RuntimeError):
    """Raised when HF release generation fails due to spec violations."""


def _run_capture(cmd: list[str]) -> str:
    """Run a subprocess command and return stdout text."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _validate_release_version(version: str) -> None:
    """Validate version against release tag format."""
    if not RELEASE_VERSION_RE.fullmatch(version):
        msg = f"Invalid version '{version}'. Expected format like v1.2.3 or v1.2.3-rc.1"
        raise ReleaseSpecError(msg)


def _get_release_tags_on_head() -> list[str]:
    """Return valid release tags that point to HEAD."""
    tags_output = _run_capture(["git", "tag", "--points-at", "HEAD"])
    if not tags_output:
        return []
    return [tag for tag in tags_output.splitlines() if RELEASE_VERSION_RE.fullmatch(tag)]


def _resolve_release_version(version: str | None) -> str:
    """Resolve and validate the release version.

    Rules:
    - If version is provided, it must be valid and point to HEAD.
    - If version is omitted, exactly one valid release tag must point to HEAD.
    """
    head_tags = _get_release_tags_on_head()

    if version:
        _validate_release_version(version)
        if version not in head_tags:
            msg = (
                f"Provided version '{version}' does not match a tag on HEAD. "
                f"Tags on HEAD: {head_tags or 'none'}"
            )
            raise ReleaseSpecError(msg)
        return version

    if len(head_tags) != 1:
        msg = (
            "Auto-detect requires exactly one release tag on HEAD. "
            f"Found: {head_tags or 'none'}"
        )
        raise ReleaseSpecError(msg)

    return head_tags[0]


def _write_json(path: Path, payload: dict[str, str]) -> None:
    """Write JSON payload with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def _compute_dataset_hash() -> str:
    """Compute a stable hash over dataset-defining JSON sources only."""
    hasher = hashlib.sha256()
    for path in [DATASET_SRC, HARD_SUBSET_PATH]:
        data = path.read_bytes()
        hasher.update(str(path).encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(data)
        hasher.update(b"\0")
    return hasher.hexdigest()


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
        raise ReleaseSpecError(f"Template file not found: {HF_TEMPLATE_PATH}")

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

    full = load_dataset("json", data_files=str(full_json), split="train")
    hard = load_dataset("json", data_files=str(hard_json), split="train")

    full_count = len(full)
    hard_count = len(hard)
    full_ids = set(full["task_id"])
    hard_ids = set(hard["task_id"])

    if full_count != EXPECTED_FULL_ROWS:
        raise ReleaseSpecError(
            f"Validation failed: full split expected {EXPECTED_FULL_ROWS}, got {full_count}"
        )
    if hard_count != EXPECTED_HARD_ROWS:
        raise ReleaseSpecError(
            f"Validation failed: hard split expected {EXPECTED_HARD_ROWS}, got {hard_count}"
        )
    if not hard_ids.issubset(full_ids):
        raise ReleaseSpecError("Validation failed: hard.task_id is not a subset of full.task_id")

    full.to_parquet(str(full_parquet))
    hard.to_parquet(str(hard_parquet))

    schema = [(name, str(feature)) for name, feature in full.features.items()]
    return full_count, hard_count, schema


def _assert_hf_release_files_exist(folder: Path, required: list[str]) -> None:
    """Ensure required release files are present before upload."""
    missing = [name for name in required if not (folder / name).exists()]
    if missing:
        msg = f"Missing required files in {folder}: {', '.join(missing)}"
        raise ReleaseSpecError(msg)


def _ensure_hf_tag(
    repo_id: str,
    version: str,
    revision: str,
    token: str | None = None,
) -> None:
    """Create or verify matching HF dataset tag."""
    api = HfApi(token=token)
    api.create_tag(
        repo_id=repo_id,
        repo_type="dataset",
        tag=version,
        revision=revision,
        exist_ok=True,
    )

    refs = api.list_repo_refs(repo_id=repo_id, repo_type="dataset")
    tags = {tag.name for tag in refs.tags}
    if version not in tags:
        raise ReleaseSpecError(f"HF tag verification failed: tag '{version}' not found on {repo_id}")


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
        raise ReleaseSpecError("HF version.json contains non-string dataset_hash")
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
        resolved_version = _resolve_release_version(version)
        build_dir = Path(output_dir)
        build_dir.mkdir(parents=True, exist_ok=True)

        full_count, hard_count, schema = _build_hf_dataset_files(ctx, build_dir)
        git_commit = _run_capture(["git", "rev-parse", "HEAD"])
        generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        dataset_hash = _compute_dataset_hash()

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

        logging_utils.print_success(
            "HF dataset artifacts generated",
            version=resolved_version,
            output=str(build_dir),
            full=full_count,
            hard=hard_count,
        )
    except (ReleaseSpecError, subprocess.CalledProcessError) as exc:
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
) -> None:
    """Upload HF dataset release artifacts and enforce matching HF tag.

    Args:
        version: Release version tag (e.g. v1.2.3). If omitted, auto-detect from HEAD tag.
        repo_id: HF dataset repository id.
        folder_path: Folder containing release artifacts.
        token: Optional HF token. If omitted, uses cached login/session.
        create_pr: Whether to open a PR instead of direct commit upload.
        dry_run: Validate and compute upload mode, but skip HF write operations.
    """
    try:
        _ = ctx
        resolved_version = _resolve_release_version(version)
        folder = Path(folder_path)
        _assert_hf_release_files_exist(folder, ["version.json", "README.md"])

        version_payload = json.loads((folder / "version.json").read_text(encoding="utf-8"))
        stamped_version = version_payload.get("version")
        if stamped_version != resolved_version:
            msg = (
                "Version mismatch: version.json has "
                f"'{stamped_version}', expected '{resolved_version}'"
            )
            raise ReleaseSpecError(msg)

        local_hash = version_payload.get("dataset_hash")
        if not isinstance(local_hash, str) or not local_hash:
            raise ReleaseSpecError("version.json must include a non-empty 'dataset_hash' field")

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

        upload_folder(
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
            revision="main",
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
    except (ReleaseSpecError, subprocess.CalledProcessError) as exc:
        logging_utils.print_error(str(exc))
        sys.exit(1)
