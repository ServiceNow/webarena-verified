"""Comprehensive unit tests for data_reader module."""

import json
from pathlib import Path
from types import MappingProxyType

import pytest

from webarena_verified.api.internal.data_reader import WebArenaVerifiedDataReader
from webarena_verified.types.agent_response import MainObjectiveType
from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.task import WebArenaSite


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def sample_dataset_path() -> Path:
    """Path to the actual dataset file."""
    return Path("assets/dataset/webarena-verified.json")


@pytest.fixture
def config(sample_dataset_path: Path) -> WebArenaVerifiedConfig:
    """WebArenaVerifiedConfig instance with actual dataset."""
    return WebArenaVerifiedConfig(test_data_file=sample_dataset_path)


@pytest.fixture
def data_reader(config: WebArenaVerifiedConfig) -> WebArenaVerifiedDataReader:
    """WebArenaVerifiedDataReader instance."""
    return WebArenaVerifiedDataReader(config)


@pytest.fixture
def temp_dataset_file(tmp_path: Path) -> Path:
    """Create a temporary dataset file with minimal test data."""
    dataset = [
        {
            "sites": ["shopping"],
            "task_id": 0,
            "intent_template_id": 100,
            "start_urls": ["__SHOPPING__"],
            "intent": "Test task 0",
            "intent_template": "Test task {{n}}",
            "instantiation_dict": {"n": 0},
            "eval": [
                {
                    "evaluator": "AgentResponseEvaluator",
                    "ordered": False,
                    "results_schema": {"type": "array", "items": {"type": "string"}},
                    "expected": {"task_type": "retrieve", "status": "SUCCESS", "retrieved_data": ["test"]},
                }
            ],
            "revision": 2,
        },
        {
            "sites": ["map"],
            "task_id": 1,
            "intent_template_id": 101,
            "start_urls": ["__MAP__"],
            "intent": "Test task 1",
            "intent_template": "Test task {{n}}",
            "instantiation_dict": {"n": 1},
            "eval": [
                {
                    "evaluator": "AgentResponseEvaluator",
                    "results_schema": {"type": "null"},
                    "expected": {"task_type": "navigate", "status": "SUCCESS", "retrieved_data": None},
                }
            ],
            "revision": 2,
        },
    ]

    # Create 810 more tasks to reach 812 total
    for i in range(2, 812):
        dataset.append(
            {
                "sites": ["gitlab"],
                "task_id": i,
                "intent_template_id": 200,
                "start_urls": ["__GITLAB__"],
                "intent": f"Test task {i}",
                "intent_template": "Test task {{n}}",
                "instantiation_dict": {"n": i},
                "eval": [
                    {
                        "evaluator": "AgentResponseEvaluator",
                        "results_schema": {"type": "null"},
                        "expected": {"task_type": "mutate", "status": "SUCCESS", "retrieved_data": None},
                    }
                ],
                "revision": 2,
            }
        )

    file_path = tmp_path / "test_dataset.json"
    file_path.write_text(json.dumps(dataset))
    return file_path


# ============================================================================
# Basic Loading Tests
# ============================================================================
def test_load_all_tasks(data_reader: WebArenaVerifiedDataReader):
    """Test that all 812 tasks load correctly from the actual dataset."""
    tasks = data_reader.tasks
    assert len(tasks) == 812
    assert all(hasattr(task, "task_id") for task in tasks)
    assert all(hasattr(task, "intent") for task in tasks)


def test_task_id_map_immutable(data_reader: WebArenaVerifiedDataReader):
    """Test that task_id_map returns an immutable MappingProxyType."""
    task_map = data_reader.task_id_map
    assert isinstance(task_map, MappingProxyType)

    # Verify we cannot modify it
    with pytest.raises(TypeError):
        task_map[9999] = None  # type: ignore


# ============================================================================
# Get Task by ID Tests
# ============================================================================
@pytest.mark.parametrize("task_id", [0, 7, 118, 811])
def test_get_task_by_id_success(data_reader: WebArenaVerifiedDataReader, task_id: int):
    """Test getting valid task IDs."""
    task = data_reader.get_task_by_id(task_id)
    assert task.task_id == task_id
    assert isinstance(task.intent, str)
    assert len(task.sites) > 0


def test_get_task_by_id_not_found(data_reader: WebArenaVerifiedDataReader):
    """Test that getting non-existent task ID raises ValueError."""
    with pytest.raises(ValueError, match="Task with id 9999 not found"):
        data_reader.get_task_by_id(9999)


# ============================================================================
# Filter Tests
# ============================================================================
@pytest.mark.parametrize(
    "site,expected_min_count",
    [
        (WebArenaSite.SHOPPING, 50),  # Shopping has many tasks
        (WebArenaSite.MAP, 20),  # Map has some tasks
        (WebArenaSite.GITLAB, 100),  # GitLab has many tasks
    ],
)
def test_filter_by_sites(data_reader: WebArenaVerifiedDataReader, site: WebArenaSite, expected_min_count: int):
    """Test filtering tasks by site."""
    filtered = data_reader.get_tasks_by_value_filter(sites=[site])

    assert len(filtered) >= expected_min_count
    # Verify all filtered tasks have the specified site
    for task in filtered:
        assert site in task.sites


def test_filter_by_template_id(data_reader: WebArenaVerifiedDataReader):
    """Test filtering tasks by template ID."""
    # Use template_id from task 0
    first_task = data_reader.get_task_by_id(0)
    template_id = first_task.intent_template_id

    filtered = data_reader.get_tasks_by_value_filter(template_id=template_id)

    assert len(filtered) > 0
    # Verify all filtered tasks have the same template_id
    for task in filtered:
        assert task.intent_template_id == template_id


@pytest.mark.parametrize(
    "action",
    [MainObjectiveType.RETRIEVE, MainObjectiveType.NAVIGATE, MainObjectiveType.MUTATE],
)
def test_filter_by_action(data_reader: WebArenaVerifiedDataReader, action: MainObjectiveType):
    """Test filtering tasks by action type."""
    filtered = data_reader.get_tasks_by_value_filter(action=action)

    assert len(filtered) > 0
    # Verify all filtered tasks have the expected action
    for task in filtered:
        assert task.expected_agent_response.task_type == action


def test_filter_combined(data_reader: WebArenaVerifiedDataReader):
    """Test filtering with multiple criteria at once."""
    # Get a task to use its properties
    sample_task = data_reader.get_task_by_id(0)

    filtered = data_reader.get_tasks_by_value_filter(
        sites=list(sample_task.sites),
        template_id=sample_task.intent_template_id,
        action=sample_task.expected_agent_response.task_type,
    )

    assert len(filtered) > 0
    # Verify all tasks match all criteria
    for task in filtered:
        assert sorted(task.sites) == sorted(sample_task.sites)
        assert task.intent_template_id == sample_task.intent_template_id
        assert task.expected_agent_response.task_type == sample_task.expected_agent_response.task_type


def test_filter_no_results(data_reader: WebArenaVerifiedDataReader):
    """Test filtering that returns no results."""
    # Use a template_id that doesn't exist with the specified site combination
    filtered = data_reader.get_tasks_by_value_filter(
        sites=[WebArenaSite.WIKIPEDIA],
        template_id=999999,  # Non-existent template_id
    )

    assert len(filtered) == 0


# ============================================================================
# Error Handling Tests
# ============================================================================
def test_duplicate_task_id_error(tmp_path: Path):
    """Test that duplicate task IDs raise an error."""
    # Create dataset with duplicate task_id
    dataset = [
        {
            "sites": ["shopping"],
            "task_id": 0,
            "intent_template_id": 100,
            "start_urls": ["__SHOPPING__"],
            "intent": "Test task",
            "intent_template": "Test task",
            "instantiation_dict": {},
            "eval": [
                {
                    "evaluator": "AgentResponseEvaluator",
                    "ordered": False,
                    "results_schema": {"type": "null"},
                    "expected": {"task_type": "retrieve", "status": "SUCCESS", "retrieved_data": None},
                }
            ],
            "revision": 2,
        },
        {
            "sites": ["map"],
            "task_id": 0,  # Duplicate!
            "intent_template_id": 101,
            "start_urls": ["__MAP__"],
            "intent": "Another test task",
            "intent_template": "Another test task",
            "instantiation_dict": {},
            "eval": [
                {
                    "evaluator": "AgentResponseEvaluator",
                    "results_schema": {"type": "null"},
                    "expected": {"task_type": "navigate", "status": "SUCCESS", "retrieved_data": None},
                }
            ],
            "revision": 2,
        },
    ]

    file_path = tmp_path / "duplicate_dataset.json"
    file_path.write_text(json.dumps(dataset))

    config = WebArenaVerifiedConfig(test_data_file=file_path)

    # Error now happens in __init__ instead of when accessing tasks (no lazy loading)
    with pytest.raises(ValueError, match="Duplicate task_id found: 0"):
        WebArenaVerifiedDataReader(config)


def test_wrong_task_count_error(tmp_path: Path):
    """Test that datasets with != 812 tasks raise an error."""
    # Create dataset with only 2 tasks (should be 812)
    dataset = [
        {
            "sites": ["shopping"],
            "task_id": 0,
            "intent_template_id": 100,
            "start_urls": ["__SHOPPING__"],
            "intent": "Test task",
            "intent_template": "Test task",
            "instantiation_dict": {},
            "eval": [
                {
                    "evaluator": "AgentResponseEvaluator",
                    "ordered": False,
                    "results_schema": {"type": "null"},
                    "expected": {"task_type": "retrieve", "status": "SUCCESS", "retrieved_data": None},
                }
            ],
            "revision": 2,
        }
    ]

    file_path = tmp_path / "wrong_count_dataset.json"
    file_path.write_text(json.dumps(dataset))

    config = WebArenaVerifiedConfig(test_data_file=file_path)

    # Error now happens in __init__ instead of when accessing tasks (no lazy loading)
    with pytest.raises(ValueError, match="Expected 812 tasks, but found 1"):
        WebArenaVerifiedDataReader(config)


def test_invalid_task_data_error(tmp_path: Path):
    """Test that malformed task data raises an error."""
    # Create dataset with invalid task (missing required field)
    dataset = [
        {
            "sites": ["shopping"],
            "task_id": 0,
            # Missing required fields like intent, eval, etc.
        }
    ]

    file_path = tmp_path / "invalid_dataset.json"
    file_path.write_text(json.dumps(dataset))

    config = WebArenaVerifiedConfig(test_data_file=file_path)

    # Error now happens in __init__ instead of when accessing tasks (no lazy loading)
    with pytest.raises(ValueError, match="Failed to parse task with id 0"):
        WebArenaVerifiedDataReader(config)


# ============================================================================
# Integration Tests with temp_dataset_file
# ============================================================================
def test_with_temp_dataset(temp_dataset_file: Path):
    """Test using the temporary dataset fixture."""
    config = WebArenaVerifiedConfig(test_data_file=temp_dataset_file)
    reader = WebArenaVerifiedDataReader(config)

    tasks = reader.tasks
    assert len(tasks) == 812

    # Verify first task
    task_0 = reader.get_task_by_id(0)
    assert task_0.sites == (WebArenaSite.SHOPPING,)
    assert task_0.expected_agent_response.task_type == MainObjectiveType.RETRIEVE

    # Verify second task
    task_1 = reader.get_task_by_id(1)
    assert task_1.sites == (WebArenaSite.MAP,)
    assert task_1.expected_agent_response.task_type == MainObjectiveType.NAVIGATE

    # Verify filter by site works
    shopping_tasks = reader.get_tasks_by_value_filter(sites=[WebArenaSite.SHOPPING])
    assert len(shopping_tasks) == 1
    assert shopping_tasks[0].task_id == 0


# ============================================================================
# Task Subset Tests
# ============================================================================
def test_no_lazy_loading(config: WebArenaVerifiedConfig):
    """Test that tasks are loaded immediately (no lazy loading)."""
    reader = WebArenaVerifiedDataReader(config)
    # Tasks should be loaded in __init__, not lazily
    assert reader._task_id_map is not None
    assert len(reader._task_id_map) == 812


def test_subset_with_valid_task_ids(temp_dataset_file: Path, tmp_path: Path):
    """Test loading a subset with all valid task IDs."""
    from webarena_verified.types.data import TaskSubset

    # Create a subset with valid task IDs
    subset = TaskSubset(
        description="Test subset",
        task_ids=[0, 1, 2],
        checksum=TaskSubset.compute_checksum([0, 1, 2]),
    )

    config = WebArenaVerifiedConfig(test_data_file=temp_dataset_file)
    reader = WebArenaVerifiedDataReader(config, subset=subset)

    # Should load only 3 tasks
    assert len(reader.tasks) == 3
    assert 0 in reader.task_id_map
    assert 1 in reader.task_id_map
    assert 2 in reader.task_id_map
    assert 3 not in reader.task_id_map


def test_subset_with_invalid_task_ids(temp_dataset_file: Path):
    """Test that subset with invalid task IDs fails fast."""
    from webarena_verified.types.data import TaskSubset

    # Create a subset with some invalid task IDs
    subset = TaskSubset(
        description="Invalid subset",
        task_ids=[0, 1, 9999],  # 9999 doesn't exist
        checksum=TaskSubset.compute_checksum([0, 1, 9999]),
    )

    config = WebArenaVerifiedConfig(test_data_file=temp_dataset_file)

    # Should fail fast during __init__
    with pytest.raises(ValueError, match="Subset contains task IDs that don't exist in dataset"):
        WebArenaVerifiedDataReader(config, subset=subset)


def test_subset_skips_812_task_validation(tmp_path: Path):
    """Test that subset loading skips the 812-task count validation."""
    from webarena_verified.types.data import TaskSubset

    # Create a dataset with only 5 tasks (would normally fail)
    dataset = []
    for i in range(5):
        dataset.append(
            {
                "sites": ["shopping"],
                "task_id": i,
                "intent_template_id": 100,
                "start_urls": ["__SHOPPING__"],
                "intent": f"Test task {i}",
                "intent_template": "Test task {{n}}",
                "instantiation_dict": {"n": i},
                "eval": [
                    {
                        "evaluator": "AgentResponseEvaluator",
                        "results_schema": {"type": "null"},
                        "expected": {"task_type": "retrieve", "status": "SUCCESS", "retrieved_data": None},
                    }
                ],
                "revision": 2,
            }
        )

    file_path = tmp_path / "small_dataset.json"
    file_path.write_text(json.dumps(dataset))

    # Without subset: should fail
    config = WebArenaVerifiedConfig(test_data_file=file_path)
    with pytest.raises(ValueError, match="Expected 812 tasks, but found 5"):
        WebArenaVerifiedDataReader(config)

    # With subset: should succeed
    subset = TaskSubset(
        description="Small subset",
        task_ids=[0, 1, 2],
        checksum=TaskSubset.compute_checksum([0, 1, 2]),
    )
    reader = WebArenaVerifiedDataReader(config, subset=subset)
    assert len(reader.tasks) == 3


def test_subset_checksum_validation(tmp_path: Path):
    """Test that corrupted checksum is detected."""
    from webarena_verified.types.data import TaskSubset

    # Try to create a subset with incorrect checksum
    with pytest.raises(ValueError, match="Checksum mismatch"):
        TaskSubset(
            description="Bad subset",
            task_ids=[0, 1, 2],
            checksum="incorrect_checksum_value",
        )


def test_subset_name_property(temp_dataset_file: Path):
    """Test subset_name property."""
    from webarena_verified.types.data import TaskSubset

    config = WebArenaVerifiedConfig(test_data_file=temp_dataset_file)

    # Without subset
    reader = WebArenaVerifiedDataReader(config)
    assert reader.subset_name is None

    # With subset (name is derived from filename, not stored in subset)
    subset = TaskSubset(
        description="Test subset",
        task_ids=[0, 1],
        checksum=TaskSubset.compute_checksum([0, 1]),
    )
    reader_with_subset = WebArenaVerifiedDataReader(config, subset=subset)
    assert reader_with_subset.subset_name is None  # Name not stored in subset object


# ============================================================================
# WebArenaVerified Public API Tests (merged from test_webarena_verified.py)
# ============================================================================


def test_webarenaverfied_initialization_default():
    """Test WebArenaVerified can be initialized with default config."""
    from webarena_verified.api import WebArenaVerified

    wa = WebArenaVerified()
    assert wa.config is not None
    assert isinstance(wa.config, WebArenaVerifiedConfig)


def test_webarenaverfied_initialization_with_config():
    """Test WebArenaVerified can be initialized with a config object."""
    from webarena_verified.api import WebArenaVerified

    config = WebArenaVerifiedConfig()
    wa = WebArenaVerified(config=config)
    assert wa.config is config


def test_webarenaverfied_get_task():
    """Test WebArenaVerified.get_task() retrieves a task."""
    from webarena_verified.api import WebArenaVerified

    wa = WebArenaVerified()
    task = wa.get_task(0)
    assert task.task_id == 0


def test_webarenaverfied_get_tasks():
    """Test WebArenaVerified.get_tasks() retrieves all tasks."""
    from webarena_verified.api import WebArenaVerified

    wa = WebArenaVerified()
    tasks = wa.get_tasks()
    assert len(tasks) == 812
    assert all(task.task_id is not None for task in tasks)


# ============================================================================
# WebArenaVerified Filtering Tests (merged from test_webarena_verified_api.py)
# ============================================================================


@pytest.fixture
def wa_api(main_config):
    """Create WebArenaVerified instance for testing."""
    from webarena_verified.api.webarena_verified import WebArenaVerified

    return WebArenaVerified(config=main_config)


def test_get_tasks_no_filters(wa_api):
    """Test get_tasks() with no filters returns all tasks."""
    all_tasks = wa_api.get_tasks()
    assert len(all_tasks) == 812
    assert all(hasattr(task, "task_id") for task in all_tasks)


def test_get_tasks_filter_by_site(wa_api):
    """Test get_tasks() with site filter."""
    shopping_tasks = wa_api.get_tasks(sites=[WebArenaSite.SHOPPING])
    assert len(shopping_tasks) > 0
    assert all(WebArenaSite.SHOPPING in task.sites for task in shopping_tasks)


def test_get_tasks_filter_by_action(wa_api):
    """Test get_tasks() with action filter."""
    retrieve_tasks = wa_api.get_tasks(action=MainObjectiveType.RETRIEVE)
    assert len(retrieve_tasks) > 0
    assert all(task.expected_agent_response.task_type == MainObjectiveType.RETRIEVE for task in retrieve_tasks)


def test_get_tasks_filter_by_template_id(wa_api):
    """Test get_tasks() with template_id filter."""
    template_5_tasks = wa_api.get_tasks(template_id=5)
    assert len(template_5_tasks) > 0
    assert all(task.intent_template_id == 5 for task in template_5_tasks)


def test_get_tasks_combined_filters(wa_api):
    """Test get_tasks() with multiple filters."""
    filtered_tasks = wa_api.get_tasks(
        sites=[WebArenaSite.SHOPPING],
        action=MainObjectiveType.RETRIEVE,
    )
    assert len(filtered_tasks) > 0
    assert all(WebArenaSite.SHOPPING in task.sites for task in filtered_tasks)
    assert all(task.expected_agent_response.task_type == MainObjectiveType.RETRIEVE for task in filtered_tasks)


def test_get_tasks_no_results(wa_api):
    """Test get_tasks() with filters that match no tasks."""
    # Use a very high template ID that doesn't exist
    no_tasks = wa_api.get_tasks(template_id=99999)
    assert len(no_tasks) == 0
