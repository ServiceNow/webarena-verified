"""Tests for eval CLI commands (__main__.py).

This module tests the CLI interface including:
- eval-tasks: Batch evaluation with filtering
- Helper functions for discovery and filtering
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from webarena_verified.__main__ import (
    _discover_completed_tasks,
    _filter_tasks_by_metadata,
    eval_tasks,
)
from webarena_verified.types.agent_response import FinalAgentResponse, MainObjectiveType
from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.eval import EvalStatus, TaskEvalResult
from webarena_verified.types.task import AgentResponseEvaluatorCfg, WebArenaSite, WebArenaVerifiedTask
from webarena_verified.types.tracing import NetworkTrace

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def mock_settings() -> WebArenaVerifiedConfig:
    """Create mock settings for testing."""
    from webarena_verified.types.config import EnvironmentConfig

    return WebArenaVerifiedConfig(
        agent_response_file_name="agent_response.json",
        trace_file_name="trace.json",
        eval_result_file_name="eval_result.json",
        environments={
            WebArenaSite.SHOPPING: EnvironmentConfig(urls=["http://localhost:7780"], active_url_idx=0),
            WebArenaSite.REDDIT: EnvironmentConfig(urls=["http://localhost:9999"], active_url_idx=0),
        },
    )


@pytest.fixture
def create_task_files(tmp_output_dir: Path):
    """Helper fixture to create task files in output directory.

    Returns:
        Callable that creates agent_response and trace files for a task ID
    """

    def _create_files(task_id: int, agent_response: dict | None = None, trace: list | None = None) -> Path:
        """Create files for a task.

        Args:
            task_id: Task ID
            agent_response: Agent response dict (default: {"answer": "test"})
            trace: Trace events list (default: [])

        Returns:
            Path to task directory
        """
        task_dir = tmp_output_dir / str(task_id)
        task_dir.mkdir(exist_ok=True)

        # Create agent response file
        response = agent_response if agent_response is not None else {"answer": "test"}
        response_file = task_dir / "agent_response.json"
        response_file.write_text(json.dumps(response))

        # Create trace file
        trace_data = trace if trace is not None else []
        trace_file = task_dir / "trace.json"
        trace_file.write_text(json.dumps(trace_data))

        return task_dir

    return _create_files


@pytest.fixture
def mock_task_result() -> TaskEvalResult:
    """Create a mock TaskEvalResult for testing."""
    return TaskEvalResult(
        task_id=1,
        intent_template_id=100,
        sites=(WebArenaSite.SHOPPING,),
        task_revision=1,
        status=EvalStatus.SUCCESS,
        score=1.0,
        evaluators_results=(),
        webarena_verified_data_checksum="test_checksum",
    )


@pytest.fixture
def create_minimal_task():
    """Helper fixture to create minimal valid WebArenaVerifiedTask objects.

    Returns:
        Callable that creates a minimal task with required fields
    """

    def _create(task_id: int) -> WebArenaVerifiedTask:
        """Create a minimal task for testing.

        Args:
            task_id: Task ID

        Returns:
            WebArenaVerifiedTask with minimal required fields
        """
        # Create minimal expected agent response
        expected_response = FinalAgentResponse.model_construct(
            task_type=MainObjectiveType.RETRIEVE,
            status="SUCCESS",
            retrieved_data=None,
        )

        # Create minimal evaluator config
        eval_config = AgentResponseEvaluatorCfg.model_construct(
            evaluator="AgentResponseEvaluator",
            expected=expected_response,
            ordered=False,
            results_schema={},
        )

        return WebArenaVerifiedTask.model_construct(
            task_id=task_id,
            intent_template_id=100,
            sites=(WebArenaSite.SHOPPING,),
            require_reset=False,
            require_login=False,
            eval=(eval_config,),
            intent="Test task",
            intent_template="Test template",
            instantiation_dict={},
            expected_agent_response=expected_response,
            revision=1,
        )

    return _create


@pytest.fixture
def create_minimal_trace():
    """Helper fixture to create minimal valid NetworkTrace objects.

    Returns:
        NetworkTrace instance with minimal valid content
    """
    minimal_trace_content = [
        {
            "type": "resource-snapshot",
            "snapshot": {
                "request": {
                    "url": "http://localhost:7780/",
                    "method": "GET",
                    "headers": {},
                },
                "response": {
                    "status": 200,
                    "headers": {},
                },
            },
        }
    ]
    return NetworkTrace.from_content(minimal_trace_content)


# ============================================================================
# Tests for eval-tasks command
# ============================================================================


def test_eval_tasks_explicit_ids(
    tmp_output_dir: Path,
    mock_settings: WebArenaVerifiedConfig,
    create_task_files,
    create_minimal_task,
    create_minimal_trace,
):
    """Test eval-tasks with explicit task IDs."""
    # Setup multiple tasks
    task_ids = [1, 2, 3]
    for task_id in task_ids:
        create_task_files(task_id)

    # Create valid NetworkTrace
    mock_trace = create_minimal_trace

    # Mock evaluator with reader that returns valid tasks
    mock_evaluator = MagicMock()

    def get_task_by_id(task_id: int):
        return create_minimal_task(task_id)

    mock_evaluator.reader.get_task_by_id.side_effect = get_task_by_id

    mock_result = TaskEvalResult(
        task_id=1,
        intent_template_id=100,
        sites=(WebArenaSite.SHOPPING,),
        task_revision=1,
        status=EvalStatus.SUCCESS,
        score=1.0,
        evaluators_results=(),
        webarena_verified_data_checksum="test",
    )
    mock_evaluator.evaluate_task.return_value = mock_result

    args = Mock(
        task_ids="1,2,3",
        output_dir=str(tmp_output_dir),
        config=None,
        sites=None,
        task_type=None,
        template_id=None,
        dry_run=False,
        agent_response_transform=None,
    )

    with (
        patch("webarena_verified.__main__._resolve_config", return_value=mock_settings),
        patch("webarena_verified.__main__._create_evaluator", return_value=mock_evaluator),
        patch("webarena_verified.types.tracing.NetworkTrace.from_content", return_value=mock_trace),
    ):
        exit_code = eval_tasks(args)

    assert exit_code == 0
    # Should be called 3 times (once per task)
    assert mock_evaluator.evaluate_task.call_count == 3


def test_eval_tasks_discover_all(
    tmp_output_dir: Path,
    mock_settings: WebArenaVerifiedConfig,
    create_task_files,
    create_minimal_task,
    create_minimal_trace,
):
    """Test eval-tasks auto-discovering all completed tasks."""
    # Create multiple tasks
    task_ids = [10, 20, 30]
    for task_id in task_ids:
        create_task_files(task_id)

    # Create valid NetworkTrace
    mock_trace = create_minimal_trace

    # Mock evaluator with reader that returns valid tasks
    mock_evaluator = MagicMock()

    def get_task_by_id(task_id: int):
        return create_minimal_task(task_id)

    mock_evaluator.reader.get_task_by_id.side_effect = get_task_by_id

    mock_result = TaskEvalResult(
        task_id=10,
        intent_template_id=100,
        sites=(WebArenaSite.SHOPPING,),
        task_revision=1,
        status=EvalStatus.SUCCESS,
        score=1.0,
        evaluators_results=(),
        webarena_verified_data_checksum="test",
    )
    mock_evaluator.evaluate_task.return_value = mock_result

    args = Mock(
        task_ids=None,  # No explicit task IDs - should discover all
        output_dir=str(tmp_output_dir),
        config=None,
        sites=None,
        task_type=None,
        template_id=None,
        dry_run=False,
        agent_response_transform=None,
    )

    with (
        patch("webarena_verified.__main__._resolve_config", return_value=mock_settings),
        patch("webarena_verified.__main__._create_evaluator", return_value=mock_evaluator),
        patch("webarena_verified.types.tracing.NetworkTrace.from_content", return_value=mock_trace),
    ):
        exit_code = eval_tasks(args)

    assert exit_code == 0
    # Should be called for all discovered tasks
    assert mock_evaluator.evaluate_task.call_count == 3


def test_eval_tasks_dry_run(tmp_output_dir: Path, mock_settings: WebArenaVerifiedConfig, create_task_files):
    """Test eval-tasks with dry-run flag."""
    # Create tasks
    create_task_files(1)
    create_task_files(2)

    # Mock evaluator (should NOT be called in dry-run)
    mock_evaluator = MagicMock()

    args = Mock(
        task_ids="1,2",
        output_dir=str(tmp_output_dir),
        config=None,
        sites=None,
        task_type=None,
        template_id=None,
        dry_run=True,  # Dry run mode
    )

    with (
        patch("webarena_verified.__main__._resolve_config", return_value=mock_settings),
        patch("webarena_verified.__main__._create_evaluator", return_value=mock_evaluator),
    ):
        exit_code = eval_tasks(args)

    assert exit_code == 0
    # Evaluator should NOT be called in dry-run mode
    mock_evaluator.evaluate_task.assert_not_called()


def test_eval_tasks_filter_by_site(tmp_output_dir: Path, mock_settings: WebArenaVerifiedConfig, create_task_files):
    """Test eval-tasks with site filter."""
    # Create tasks
    create_task_files(1)
    create_task_files(2)

    # Mock the evaluator's get_tasks to return filtered tasks
    mock_task_1 = MagicMock()
    mock_task_1.task_id = 1
    mock_task_2 = MagicMock()
    mock_task_2.task_id = 2

    # Mock evaluator
    mock_evaluator = MagicMock()
    mock_evaluator.get_tasks.return_value = [mock_task_1]  # Only task 1 matches
    mock_results = MagicMock()
    mock_results.model_dump_json.return_value = json.dumps({"summary": "test"})
    mock_evaluator.evaluate_tasks.return_value = mock_results

    args = Mock(
        task_ids=None,
        output_dir=str(tmp_output_dir),
        config=None,
        sites="shopping",  # Filter by shopping site
        task_type=None,
        template_id=None,
        dry_run=False,
    )

    with (
        patch("webarena_verified.__main__._resolve_config", return_value=mock_settings),
        patch("webarena_verified.__main__._create_evaluator", return_value=mock_evaluator),
    ):
        exit_code = eval_tasks(args)

    assert exit_code == 0
    # Verify filter was called with correct site
    mock_evaluator.get_tasks.assert_called_once()
    call_kwargs = mock_evaluator.get_tasks.call_args.kwargs
    assert call_kwargs["sites"] == [WebArenaSite.SHOPPING]


def test_eval_tasks_filter_by_task_type(tmp_output_dir: Path, mock_settings: WebArenaVerifiedConfig, create_task_files):
    """Test eval-tasks with task type filter."""
    create_task_files(1)

    mock_task = MagicMock()
    mock_task.task_id = 1

    mock_evaluator = MagicMock()
    mock_evaluator.get_tasks.return_value = [mock_task]
    mock_results = MagicMock()
    mock_results.model_dump_json.return_value = json.dumps({"summary": "test"})
    mock_evaluator.evaluate_tasks.return_value = mock_results

    args = Mock(
        task_ids=None,
        output_dir=str(tmp_output_dir),
        config=None,
        sites=None,
        task_type="retrieve",  # Filter by retrieve task type
        template_id=None,
        dry_run=False,
    )

    with (
        patch("webarena_verified.__main__._resolve_config", return_value=mock_settings),
        patch("webarena_verified.__main__._create_evaluator", return_value=mock_evaluator),
    ):
        exit_code = eval_tasks(args)

    assert exit_code == 0
    call_kwargs = mock_evaluator.get_tasks.call_args.kwargs
    assert call_kwargs["action"] == MainObjectiveType.RETRIEVE


def test_eval_tasks_combined_filters(tmp_output_dir: Path, mock_settings: WebArenaVerifiedConfig, create_task_files):
    """Test eval-tasks with multiple filters combined."""
    create_task_files(1)

    mock_task = MagicMock()
    mock_task.task_id = 1

    mock_evaluator = MagicMock()
    mock_evaluator.get_tasks.return_value = [mock_task]
    mock_results = MagicMock()
    mock_results.model_dump_json.return_value = json.dumps({"summary": "test"})
    mock_evaluator.evaluate_tasks.return_value = mock_results

    args = Mock(
        task_ids=None,
        output_dir=str(tmp_output_dir),
        config=None,
        sites="shopping,reddit",  # Multiple sites
        task_type="mutate",  # Task type filter
        template_id=100,  # Template ID filter
        dry_run=False,
    )

    with (
        patch("webarena_verified.__main__._resolve_config", return_value=mock_settings),
        patch("webarena_verified.__main__._create_evaluator", return_value=mock_evaluator),
    ):
        exit_code = eval_tasks(args)

    assert exit_code == 0
    call_kwargs = mock_evaluator.get_tasks.call_args.kwargs
    assert call_kwargs["sites"] == [WebArenaSite.SHOPPING, WebArenaSite.REDDIT]
    assert call_kwargs["action"] == MainObjectiveType.MUTATE
    assert call_kwargs["template_id"] == 100


def test_eval_tasks_empty_output_dir(tmp_path: Path, mock_settings: WebArenaVerifiedConfig):
    """Test eval-tasks with non-existent output directory."""
    fake_dir = tmp_path / "nonexistent"

    args = Mock(
        task_ids=None,
        output_dir=str(fake_dir),
        config=None,
        sites=None,
        task_type=None,
        template_id=None,
        dry_run=True,  # Use dry-run to avoid needing evaluator
    )

    with patch("webarena_verified.__main__._resolve_config", return_value=mock_settings):
        exit_code = eval_tasks(args)

    # Should succeed with 0 tasks found
    assert exit_code == 0


# ============================================================================
# Tests for helper functions
# ============================================================================


def test_discover_completed_tasks(tmp_output_dir: Path, mock_settings: WebArenaVerifiedConfig, create_task_files):
    """Test task discovery logic."""
    # Create valid tasks
    valid_task_ids = [1, 5, 10]
    for task_id in valid_task_ids:
        create_task_files(task_id)

    # Create invalid task directory (no files)
    invalid_dir = tmp_output_dir / "999"
    invalid_dir.mkdir()

    # Create non-numeric directory (should be ignored)
    other_dir = tmp_output_dir / "other"
    other_dir.mkdir()

    # Discover tasks
    discovered, skipped = _discover_completed_tasks(tmp_output_dir, mock_settings)

    # Should find only valid tasks
    assert set(discovered) == set(valid_task_ids)
    assert 999 not in discovered  # Invalid task not included
    assert 999 in skipped  # Invalid task in skipped list


def test_discover_completed_tasks_nonexistent_dir(tmp_path: Path, mock_settings: WebArenaVerifiedConfig):
    """Test discovery with non-existent directory."""
    fake_dir = tmp_path / "nonexistent"

    discovered, skipped = _discover_completed_tasks(fake_dir, mock_settings)

    assert discovered == []
    assert skipped == []


def test_filter_tasks_by_metadata_no_filters(mock_settings: WebArenaVerifiedConfig):
    """Test filtering with no filters (should return all tasks)."""
    task_ids = [1, 2, 3]

    # Create mock WebArenaVerified instance
    mock_wa = MagicMock()

    filtered = _filter_tasks_by_metadata(
        task_ids=task_ids,
        wa=mock_wa,
        sites=None,
        task_type=None,
        template_id=None,
    )

    assert filtered == task_ids
    # get_tasks should not be called when no filters are provided
    mock_wa.get_tasks.assert_not_called()


def test_filter_tasks_by_metadata_with_site(mock_settings: WebArenaVerifiedConfig):
    """Test filtering by site."""
    task_ids = [1, 2, 3]

    # Create mock WebArenaVerified instance
    mock_wa = MagicMock()
    mock_task_1 = MagicMock()
    mock_task_1.task_id = 1
    mock_task_2 = MagicMock()
    mock_task_2.task_id = 2
    mock_wa.get_tasks.return_value = [mock_task_1, mock_task_2]

    filtered = _filter_tasks_by_metadata(
        task_ids=task_ids,
        wa=mock_wa,
        sites=["shopping"],
        task_type=None,
        template_id=None,
    )

    # Should only return tasks that were in both lists
    assert set(filtered) == {1, 2}
    assert 3 not in filtered
    # Verify get_tasks was called with correct filter
    mock_wa.get_tasks.assert_called_once()
    call_kwargs = mock_wa.get_tasks.call_args.kwargs
    assert call_kwargs["sites"] == [WebArenaSite.SHOPPING]


def test_filter_tasks_by_metadata_invalid_site(mock_settings: WebArenaVerifiedConfig):
    """Test filtering with invalid site name."""
    task_ids = [1, 2, 3]

    # Create mock WebArenaVerified instance
    mock_wa = MagicMock()

    with pytest.raises(ValueError, match="Invalid site name"):
        _filter_tasks_by_metadata(
            task_ids=task_ids,
            wa=mock_wa,
            sites=["invalid_site"],
            task_type=None,
            template_id=None,
        )


def test_filter_tasks_by_metadata_invalid_task_type(mock_settings: WebArenaVerifiedConfig):
    """Test filtering with invalid task type."""
    task_ids = [1, 2, 3]

    # Create mock WebArenaVerified instance
    mock_wa = MagicMock()

    with pytest.raises(ValueError, match=r"Invalid task type:.*Valid task types:"):
        _filter_tasks_by_metadata(
            task_ids=task_ids,
            wa=mock_wa,
            sites=None,
            task_type="invalid_task_type",
            template_id=None,
        )
