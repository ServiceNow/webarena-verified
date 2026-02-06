"""Fixtures for dataset integrity tests."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

ORIGINAL_DATASET_MD5 = "bcb0f3bd1dc7d1f0063fa1d42faad940"


@lru_cache(maxsize=1)
def _get_original_dataset(project_root_str: str) -> tuple[dict[str, Any], ...]:
    """Load and cache original dataset."""
    path = Path(project_root_str) / "assets" / "dataset" / "test.raw.json"
    content = path.read_text()

    # Verify checksum to ensure original dataset hasn't changed
    checksum = hashlib.md5(content.encode()).hexdigest()
    if checksum != ORIGINAL_DATASET_MD5:
        raise AssertionError(
            f"test.raw.json has changed! Expected MD5: {ORIGINAL_DATASET_MD5}, got: {checksum}. "
            f"This file is used as a reference and should not be modified."
        )

    result: list[dict[str, Any]] = json.loads(content)
    return tuple(result)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Generate test parameters dynamically from the original dataset."""
    if "intent_template_id" in metafunc.fixturenames:
        project_root = Path(metafunc.config.rootpath)
        original_dataset = _get_original_dataset(str(project_root))
        intent_template_ids = sorted({task["intent_template_id"] for task in original_dataset})
        metafunc.parametrize("intent_template_id", intent_template_ids)


@pytest.fixture(scope="module")
def dataset(project_root: Path) -> list[dict[str, Any]]:
    """Load current dataset."""
    path = project_root / "assets" / "dataset" / "webarena-verified.json"
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def original_dataset(project_root: Path) -> list[dict[str, Any]]:
    """Load original dataset for comparison."""
    return list(_get_original_dataset(str(project_root)))


@pytest.fixture(scope="module")
def dataset_by_task_id(dataset: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Index dataset by task_id."""
    return {task["task_id"]: task for task in dataset}


@pytest.fixture(scope="module")
def original_by_task_id(original_dataset: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Index original dataset by task_id."""
    return {task["task_id"]: task for task in original_dataset}


@pytest.fixture(scope="module")
def tasks_by_intent_template_id(dataset: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    """Group tasks by intent_template_id."""
    grouped: dict[int, list[dict[str, Any]]] = {}
    for task in dataset:
        template_id: int = task["intent_template_id"]
        if template_id not in grouped:
            grouped[template_id] = []
        grouped[template_id].append(task)
    return grouped
