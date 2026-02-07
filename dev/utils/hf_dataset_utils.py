"""Helpers for HF dataset release tasks."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import semver
from datasets import Dataset, List, Value
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
SITE_CLASS_NAMES = ["gitlab", "map", "reddit", "shopping_admin", "shopping", "wikipedia", "homepage"]
SITES_FEATURE = List(Value("string"))


def _json_stringify(value: Any) -> str:
    """Serialize value deterministically as JSON text."""
    return json.dumps(value, sort_keys=True)


def _compute_instantiation_stringify_keys(rows: list[dict[str, Any]], path: Path) -> set[str]:
    """Find instantiation_dict keys that must be stringified for Arrow schema stability."""
    scalar_types_by_key: dict[str, set[type[Any]]] = {}
    keys_with_nested_values: set[str] = set()

    for row in rows:
        instantiation_dict = row.get("instantiation_dict")
        if not isinstance(instantiation_dict, dict):
            raise RuntimeError(f"Expected 'instantiation_dict' to be an object in {path}") from None

        for key, raw in instantiation_dict.items():
            if isinstance(raw, dict | list):
                keys_with_nested_values.add(key)
                continue

            scalar_types_by_key.setdefault(key, set()).add(type(raw))

    stringify_keys = set(keys_with_nested_values)
    for key, scalar_types in scalar_types_by_key.items():
        non_none_scalar_types = {value_type for value_type in scalar_types if value_type is not type(None)}
        if len(non_none_scalar_types) > 1:
            stringify_keys.add(key)

    return stringify_keys


def _normalize_instantiation_dict(
    value: Any,
    path: Path,
    stringify_scalar_keys: set[str],
) -> dict[str, Any]:
    """Normalize instantiation_dict while preserving scalar types and JSON semantics."""
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected 'instantiation_dict' to be an object in {path}") from None

    normalized: dict[str, Any] = {}
    for key, raw in value.items():
        if isinstance(raw, dict | list):
            normalized[key] = _json_stringify(raw)
        elif key in stringify_scalar_keys and raw is not None:
            normalized[key] = str(raw)
        else:
            normalized[key] = raw
    return normalized


def _normalize_post_data(post_data: dict[str, Any]) -> dict[str, str | None]:
    """Normalize expected.post_data to a stable map<string, string|null>."""
    normalized_post_data: dict[str, str | None] = {}
    for key, value in post_data.items():
        if value is None:
            normalized_post_data[key] = None
        elif isinstance(value, dict | list):
            normalized_post_data[key] = _json_stringify(value)
        else:
            normalized_post_data[key] = str(value)
    return normalized_post_data


def _normalize_expected(expected: dict[str, Any]) -> dict[str, Any]:
    """Normalize evaluator expected block for Arrow-compat nested typing."""
    normalized_expected = dict(expected)

    if "url" in normalized_expected and not isinstance(normalized_expected["url"], list):
        normalized_expected["url"] = [normalized_expected["url"]]

    headers = normalized_expected.get("headers")
    if isinstance(headers, dict) and "referer" in headers and not isinstance(headers["referer"], list):
        headers = dict(headers)
        headers["referer"] = [headers["referer"]]
        normalized_expected["headers"] = headers

    if normalized_expected.get("retrieved_data") is None:
        normalized_expected["retrieved_data"] = []
    if isinstance(normalized_expected.get("retrieved_data"), list):
        normalized_expected["retrieved_data"] = [
            value if isinstance(value, str) else _json_stringify(value)
            for value in normalized_expected["retrieved_data"]
        ]

    post_data = normalized_expected.get("post_data")
    if isinstance(post_data, dict):
        normalized_expected["post_data"] = _normalize_post_data(post_data)

    return normalized_expected


def _normalize_schema_fields(normalized: dict[str, Any]) -> None:
    """Stringify highly-dynamic schema dictionaries."""
    for key in ("results_schema", "query_params_schema", "post_data_schema"):
        value = normalized.get(key)
        if isinstance(value, dict | list):
            normalized[key] = _json_stringify(value)


def _normalize_ignored_param_fields(normalized: dict[str, Any]) -> None:
    """Ensure ignored-params fields are lists of strings."""
    for key in ("ignored_query_params", "ignored_query_params_patterns", "ignored_post_data_params_patterns"):
        value = normalized.get(key)
        if value is not None:
            normalized[key] = [str(item) for item in value]


def _normalize_eval_item(item: Any, path: Path) -> dict[str, Any]:
    """Normalize one evaluator config for Arrow-compat nested typing."""
    if not isinstance(item, dict):
        raise RuntimeError(f"Expected eval items to be objects in {path}") from None

    normalized = dict(item)
    expected = normalized.get("expected")
    if isinstance(expected, dict):
        normalized["expected"] = _normalize_expected(expected)

    _normalize_schema_fields(normalized)
    _normalize_ignored_param_fields(normalized)

    return normalized


def _normalize_eval(value: Any, path: Path) -> list[dict[str, Any]]:
    """Normalize eval column to a stable nested representation."""
    if not isinstance(value, list):
        raise RuntimeError(f"Expected 'eval' to be an array in {path}") from None
    return [_normalize_eval_item(item, path) for item in value]


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
    for path in sorted(paths, key=lambda path: path.as_posix()):
        raw_bytes = path.read_bytes()
        hasher.update(path.as_posix().encode("utf-8"))
        hasher.update(b"\0")
        canonical_bytes: bytes
        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            canonical_bytes = raw_bytes
        else:
            canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )

        hasher.update(canonical_bytes)
        hasher.update(b"\0")
    return hasher.hexdigest()


def write_json(path: Path, payload: dict[str, str]) -> None:
    """Write JSON payload with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)}\n", encoding="utf-8")


def render_hf_readme(
    output_readme: Path,
    version: str,
    git_commit: str,
    generated_at: str,
    dataset_hash: str,
    full_count: int,
    hard_count: int,
    full_site_task_counts: list[tuple[str, int]],
    hard_site_task_counts: list[tuple[str, int]],
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
        full_site_task_counts=full_site_task_counts,
        hard_site_task_counts=hard_site_task_counts,
        schema=schema,
    )
    output_readme.write_text(f"{rendered.rstrip()}\n", encoding="utf-8")


def load_hf_json_dataset(path: Path) -> Dataset:
    """Load a JSON split with an explicit HF schema.

    - `sites` is encoded as multi-label categorical values.
    - `instantiation_dict` and `eval` are stored as JSON strings for stable cross-split schemas.
    """
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise RuntimeError(f"Expected JSON array in {path}") from None

    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError(f"Expected object rows in {path}") from None

        instantiation_dict = row.get("instantiation_dict")
        if not isinstance(instantiation_dict, dict):
            raise RuntimeError(f"Expected 'instantiation_dict' to be an object in {path}") from None
        row["instantiation_dict"] = _json_stringify(instantiation_dict)

        eval_value = row.get("eval")
        if not isinstance(eval_value, list):
            raise RuntimeError(f"Expected 'eval' to be an array in {path}") from None
        row["eval"] = _json_stringify(eval_value)

    dataset = Dataset.from_list(rows)
    return dataset.cast_column("sites", SITES_FEATURE)


def compute_site_task_counts(rows: list[dict[str, object]]) -> list[tuple[str, int]]:
    """Count tasks per site, placing multi-site tasks in a dedicated bucket."""
    counts = dict.fromkeys(SITE_CLASS_NAMES, 0)
    extra_sites: dict[str, int] = {}
    multi_category_count = 0

    for row in rows:
        sites = row.get("sites")
        if not isinstance(sites, list):
            raise RuntimeError("Validation failed: task row has non-list `sites`")

        site_names: list[str] = []
        for site in sites:
            if not isinstance(site, str):
                raise RuntimeError("Validation failed: `sites` entries must be strings")
            site_names.append(site)

        if len(site_names) > 1:
            multi_category_count += 1
            continue

        if len(site_names) == 1:
            site_name = site_names[0]
            if site_name in counts:
                counts[site_name] += 1
            else:
                extra_sites[site_name] = extra_sites.get(site_name, 0) + 1

    ordered_counts = [(site, counts[site]) for site in SITE_CLASS_NAMES]
    ordered_counts.extend((site, extra_sites[site]) for site in sorted(extra_sites))
    ordered_counts.append(("multi-category", multi_category_count))
    return ordered_counts


def build_hf_dataset_files(
    ctx: Context, output_dir: Path
) -> tuple[int, int, list[tuple[str, int]], list[tuple[str, int]], list[tuple[str, str]]]:
    """Build full/hard JSON + parquet with strict validation."""
    full_json = output_dir / "full.json"
    hard_json = output_dir / "hard.json"
    full_parquet = output_dir / "full.parquet"
    hard_parquet = output_dir / "hard.parquet"

    shutil.copy2(DATASET_SRC, full_json)

    ctx.run(
        " ".join(
            [
                "uv",
                "run",
                "webarena-verified",
                "subset-export",
                "--path",
                shlex.quote(str(HARD_SUBSET_PATH)),
                "--output",
                shlex.quote(str(hard_json)),
            ]
        ),
        hide=True,
    )

    full = load_hf_json_dataset(full_json)
    hard = load_hf_json_dataset(hard_json)
    full_rows = json.loads(full_json.read_text(encoding="utf-8"))
    hard_rows = json.loads(hard_json.read_text(encoding="utf-8"))

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
    full_json.unlink(missing_ok=True)
    hard_json.unlink(missing_ok=True)

    schema = [(name, str(feature)) for name, feature in full.features.items()]
    full_site_task_counts = compute_site_task_counts(full_rows)
    hard_site_task_counts = compute_site_task_counts(hard_rows)
    return full_count, hard_count, full_site_task_counts, hard_site_task_counts, schema


def generate_hf_release_artifacts(ctx: Context, resolved_version: str, build_dir: Path) -> None:
    """Generate all HF release artifacts into build_dir."""
    build_dir.mkdir(parents=True, exist_ok=True)
    full_count, hard_count, full_site_task_counts, hard_site_task_counts, schema = build_hf_dataset_files(
        ctx, build_dir
    )
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
        full_site_task_counts=full_site_task_counts,
        hard_site_task_counts=hard_site_task_counts,
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
