"""HF dataset smoke tests for WebArena-Verified."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from datasets import load_dataset

EXPECTED_FULL_ROWS = 812
EXPECTED_HARD_ROWS = 258


@pytest.fixture
def dataset_ref(request: pytest.FixtureRequest) -> str:
    """Dataset reference from CLI (HF repo id or local path)."""
    return str(request.config.getoption("--hf-dataset-ref"))


@pytest.fixture
def cache_dir() -> Path:
    """Temporary cache directory for a fresh dataset download/build."""
    with tempfile.TemporaryDirectory(prefix="hf_dataset_cache_") as tmp:
        yield Path(tmp)


@pytest.fixture
def _load_split(dataset_ref: str, cache_dir: Path):
    """Fixture returning a split loader bound to dataset_ref and cache_dir."""

    def _loader(split: str):
        return load_dataset(
            dataset_ref,
            split=split,
            cache_dir=str(cache_dir),
            download_mode="force_redownload",
        )

    return _loader


@pytest.fixture
def loaded_splits(_load_split):
    """Load full and hard once for test reuse."""
    return _load_split("full"), _load_split("hard")


def test_hf_dataset_splits_and_integrity(loaded_splits) -> None:
    """Validate split presence, counts, sample intents, and hard subset relation."""
    full, hard = loaded_splits

    assert len(full) == EXPECTED_FULL_ROWS
    assert len(hard) == EXPECTED_HARD_ROWS

    full_intent = full[0]["intent"]
    hard_intent = hard[0]["intent"]
    assert isinstance(full_intent, str)
    assert isinstance(hard_intent, str)
    assert full_intent.strip()
    assert hard_intent.strip()

    full_task_ids = set(full["task_id"])
    hard_task_ids = set(hard["task_id"])
    assert hard_task_ids.issubset(full_task_ids)
