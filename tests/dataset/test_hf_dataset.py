"""HF dataset parity tests for WebArena-Verified."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING, Any

import pytest
from datasets import load_dataset
from deepdiff import DeepDiff

if TYPE_CHECKING:
    from pathlib import Path

def _canonicalize(value: Any) -> Any:
    """Normalize nested structures for stable equality checks."""
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, tuple):
        return tuple(_canonicalize(item) for item in value)
    if isinstance(value, list):
        return tuple(_canonicalize(item) for item in value)
    if isinstance(value, str):
        # Fallback loader can stringify nested JSON fields; recover if possible.
        stripped = value.strip()
        if stripped and stripped[0] in "[{":
            try:
                decoded = json.loads(stripped)
            except (TypeError, json.JSONDecodeError):
                return value
            return _canonicalize(decoded)
    return value


def _assert_deep_equal(actual: Any, expected: Any) -> None:
    """Assert deep equality with a readable diff."""
    diff = DeepDiff(expected, actual, ignore_order=False)
    assert not diff, diff.pretty()


@pytest.fixture
def dataset_ref(request: pytest.FixtureRequest) -> str:
    """Dataset reference from CLI (HF repo id or local path)."""
    dataset = request.config.getoption("--hf-dataset-ref")
    if not dataset:
        pytest.skip("HF dataset parity tests require --hf-dataset-ref (repo id or local path)")
    return str(dataset)


@pytest.fixture(scope="session")
def hard_subset_data(project_root: Path, tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, Any], ...]:
    """Expected hard rows generated via subset-export."""
    subset_path = project_root / "assets" / "dataset" / "subsets" / "webarena-verified-hard.json"
    output_dir = tmp_path_factory.mktemp("hf_expected_hard")
    output_path = output_dir / "hard.json"
    subprocess.run(
        [
            "uv",
            "run",
            "webarena-verified",
            "subset-export",
            "--path",
            str(subset_path),
            "--output",
            str(output_path),
        ],
        check=True,
    )
    result: list[dict[str, Any]] = json.loads(output_path.read_text(encoding="utf-8"))
    return tuple(result)


@pytest.fixture(scope="module")
def benchmark_data(project_root: Path) -> tuple[dict[str, Any], ...]:
    """Canonical benchmark dataset rows from assets/dataset/webarena-verified.json."""
    path = project_root / "assets" / "dataset" / "webarena-verified.json"
    result: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return tuple(result)


@pytest.fixture(scope="session")
def hf_cache_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Shared cache directory for HF dataset downloads in this test session."""
    path = tmp_path_factory.mktemp("hf_dataset_cache")
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def hf_full_split_rows(dataset_ref: str, hf_cache_dir: Path) -> tuple[dict[str, Any], ...]:
    """HF `full` split rows loaded as Python dicts."""
    rows: list[dict[str, Any]] = load_dataset(
        dataset_ref,
        split="full",
        cache_dir=str(hf_cache_dir),
    ).to_list()
    return tuple(rows)


@pytest.fixture
def hf_hard_split_rows(dataset_ref: str, hf_cache_dir: Path) -> tuple[dict[str, Any], ...]:
    """HF `hard` split rows loaded as Python dicts."""
    rows: list[dict[str, Any]] = load_dataset(
        dataset_ref,
        split="hard",
        cache_dir=str(hf_cache_dir),
    ).to_list()
    return tuple(rows)


def test_hf_dataset_full_exact_content(
    benchmark_data: tuple[dict[str, Any], ...],
    hf_full_split_rows: tuple[dict[str, Any], ...],
) -> None:
    """Full split must match the source dataset exactly (row count + row content + order)."""
    assert len(hf_full_split_rows) == len(benchmark_data)
    _assert_deep_equal(_canonicalize(hf_full_split_rows), _canonicalize(benchmark_data))


def test_hf_dataset_hard_subset_exact_content(
    hard_subset_data: tuple[dict[str, Any], ...],
    hf_hard_split_rows: tuple[dict[str, Any], ...],
) -> None:
    """Hard split must match subset ids and exact content from subset-export."""
    hard_ids = {task["task_id"] for task in hf_hard_split_rows}
    expected_hard_ids = {task["task_id"] for task in hard_subset_data}

    assert len(hf_hard_split_rows) == len(hard_subset_data)
    assert hard_ids == expected_hard_ids
    _assert_deep_equal(_canonicalize(hf_hard_split_rows), _canonicalize(hard_subset_data))
