"""Helpers for HF dataset release tasks."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import semver
from datasets import Dataset, load_dataset
from datasets.exceptions import DatasetGenerationError
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError, RevisionNotFoundError
from jinja2 import Environment, FileSystemLoader, StrictUndefined

if TYPE_CHECKING:
    from invoke.context import Context

RELEASE_VERSION_PREFIX = "v"
HF_BUILD_DIR = Path("output/build/hf_dataset")
HF_TEMPLATE_PATH = Path("assets/hf_dataset/README.md.jinja2")
DATASET_SRC = Path("assets/dataset/webarena-verified.json")
HARD_SUBSET_PATH = Path("assets/dataset/subsets/webarena-verified-hard.json")
EXPECTED_FULL_ROWS = 812
EXPECTED_HARD_ROWS = 258


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
        raise RuntimeError(f"Invalid version '{version}'. Expected format like v1.2.3 or v1.2.3-rc.1") from exc


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
            msg = f"Provided version '{version}' does not match a tag on HEAD. Tags on HEAD: {head_tags or 'none'}"
            raise RuntimeError(msg)
        return version

    if len(head_tags) != 1:
        msg = f"Auto-detect requires exactly one release tag on HEAD. Found: {head_tags or 'none'}"
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


def write_json(path: Path, payload: dict[str, str]) -> None:
    """Write JSON payload with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def render_hf_readme(
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


def load_hf_json_dataset(path: Path) -> Dataset:
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


def build_hf_dataset_files(ctx: Context, output_dir: Path) -> tuple[int, int, list[tuple[str, str]]]:
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

    full = load_hf_json_dataset(full_json)
    hard = load_hf_json_dataset(hard_json)

    full_count = len(full)
    hard_count = len(hard)
    full_ids = set(full["task_id"])
    hard_ids = set(hard["task_id"])

    if full_count != EXPECTED_FULL_ROWS:
        raise RuntimeError(f"Validation failed: full split expected {EXPECTED_FULL_ROWS}, got {full_count}")
    if hard_count != EXPECTED_HARD_ROWS:
        raise RuntimeError(f"Validation failed: hard split expected {EXPECTED_HARD_ROWS}, got {hard_count}")
    if not hard_ids.issubset(full_ids):
        raise RuntimeError("Validation failed: hard.task_id is not a subset of full.task_id")

    full.to_parquet(str(full_parquet))
    hard.to_parquet(str(hard_parquet))

    schema = [(name, str(feature)) for name, feature in full.features.items()]
    return full_count, hard_count, schema


def generate_hf_release_artifacts(ctx: Context, resolved_version: str, build_dir: Path) -> None:
    """Generate all HF release artifacts into build_dir."""
    build_dir.mkdir(parents=True, exist_ok=True)
    full_count, hard_count, schema = build_hf_dataset_files(ctx, build_dir)
    git_commit = run_capture(["git", "rev-parse", "HEAD"])
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    dataset_hash = compute_dataset_hash([DATASET_SRC, HARD_SUBSET_PATH])

    write_json(
        build_dir / "version.json",
        {
            "version": resolved_version,
            "git_commit": git_commit,
            "generated_at": generated_at,
            "dataset_hash": dataset_hash,
        },
    )

    render_hf_readme(
        output_readme=build_dir / "README.md",
        version=resolved_version,
        git_commit=git_commit,
        generated_at=generated_at,
        dataset_hash=dataset_hash,
        full_count=full_count,
        hard_count=hard_count,
        schema=schema,
    )


def missing_release_files(folder: Path, required: list[str]) -> list[str]:
    """Return missing required files in folder."""
    return [name for name in required if not (folder / name).exists()]


def assert_hf_release_files_exist(folder: Path, required: list[str]) -> None:
    """Ensure required release files are present before upload."""
    missing = missing_release_files(folder, required)
    if missing:
        msg = f"Missing required files in {folder}: {', '.join(missing)}"
        raise RuntimeError(msg)


def ensure_hf_tag(
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
            f"HF tag verification failed: tag '{version}' points to {tag_ref.target_commit}, expected {expected_commit}"
        )


def get_remote_dataset_hash(repo_id: str, token: str | None = None) -> str | None:
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
