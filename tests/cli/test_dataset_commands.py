"""Tests for dataset CLI commands (__main__.py).

This module tests the dataset-get CLI command.
"""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from webarena_verified.__main__ import dataset_get
from webarena_verified.types.agent_response import MainObjectiveType
from webarena_verified.types.task import WebArenaSite, WebArenaVerifiedTask


@pytest.fixture
def mock_task_for_dataset_get():
    """Create mock tasks for dataset-get tests."""

    def _create(
        task_id: int,
        sites: tuple[WebArenaSite, ...] = (WebArenaSite.SHOPPING,),
        intent_template_id: int = 100,
        task_type: MainObjectiveType = MainObjectiveType.RETRIEVE,
    ) -> MagicMock:
        mock_task = MagicMock(spec=WebArenaVerifiedTask)
        mock_task.task_id = task_id
        mock_task.sites = sites
        mock_task.intent_template_id = intent_template_id
        mock_task.expected_action = task_type
        mock_task.intent = f"Test intent for task {task_id}"
        mock_task.model_dump.return_value = {
            "task_id": task_id,
            "sites": [s.value for s in sites],
            "intent_template_id": intent_template_id,
            "intent": f"Test intent for task {task_id}",
        }
        return mock_task

    return _create


def test_dataset_get_by_task_ids(mock_task_for_dataset_get, capsys):
    """Test dataset-get with explicit task IDs."""
    mock_task_1 = mock_task_for_dataset_get(1)
    mock_task_2 = mock_task_for_dataset_get(2)

    mock_wa = MagicMock()
    mock_wa.get_task.side_effect = lambda task_id: {1: mock_task_1, 2: mock_task_2}[task_id]

    args = Mock(
        task_ids="1,2",
        sites=None,
        task_type=None,
        template_id=None,
        fields=None,
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert len(output) == 2
    assert output[0]["task_id"] == 1
    assert output[1]["task_id"] == 2


def test_dataset_get_all_tasks(mock_task_for_dataset_get, capsys):
    """Test dataset-get returning all tasks (no filters)."""
    mock_tasks = [mock_task_for_dataset_get(i) for i in range(1, 4)]

    mock_wa = MagicMock()
    mock_wa.get_tasks.return_value = mock_tasks

    args = Mock(
        task_ids=None,
        sites=None,
        task_type=None,
        template_id=None,
        fields=None,
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert len(output) == 3


def test_dataset_get_filter_by_site(mock_task_for_dataset_get, capsys):
    """Test dataset-get filtering by single site (delegates to wa.get_tasks)."""
    mock_task = mock_task_for_dataset_get(1, sites=(WebArenaSite.SHOPPING,))

    mock_wa = MagicMock()
    mock_wa.get_tasks.return_value = [mock_task]

    args = Mock(
        task_ids=None,
        sites="shopping",
        task_type=None,
        template_id=None,
        fields=None,
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 0
    # Verify get_tasks was called with correct site filter
    mock_wa.get_tasks.assert_called_once_with(
        sites=[WebArenaSite.SHOPPING],
        template_id=None,
        action=None,
    )
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert len(output) == 1
    assert output[0]["task_id"] == 1


def test_dataset_get_filter_by_multisite(mock_task_for_dataset_get, capsys):
    """Test dataset-get filtering by multi-site (delegates to wa.get_tasks)."""
    mock_task = mock_task_for_dataset_get(1, sites=(WebArenaSite.SHOPPING, WebArenaSite.GITLAB))

    mock_wa = MagicMock()
    mock_wa.get_tasks.return_value = [mock_task]

    args = Mock(
        task_ids=None,
        sites="shopping,gitlab",
        task_type=None,
        template_id=None,
        fields=None,
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 0
    # Verify get_tasks was called with multi-site filter
    mock_wa.get_tasks.assert_called_once_with(
        sites=[WebArenaSite.SHOPPING, WebArenaSite.GITLAB],
        template_id=None,
        action=None,
    )
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert len(output) == 1
    assert output[0]["task_id"] == 1


def test_dataset_get_filter_by_task_type(mock_task_for_dataset_get, capsys):
    """Test dataset-get filtering by task type (delegates to wa.get_tasks)."""
    mock_task = mock_task_for_dataset_get(1, task_type=MainObjectiveType.RETRIEVE)

    mock_wa = MagicMock()
    mock_wa.get_tasks.return_value = [mock_task]

    args = Mock(
        task_ids=None,
        sites=None,
        task_type="RETRIEVE",
        template_id=None,
        fields=None,
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 0
    # Verify get_tasks was called with correct task type filter
    mock_wa.get_tasks.assert_called_once_with(
        sites=None,
        template_id=None,
        action=MainObjectiveType.RETRIEVE,
    )
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert len(output) == 1
    assert output[0]["task_id"] == 1


def test_dataset_get_filter_by_template_id(mock_task_for_dataset_get, capsys):
    """Test dataset-get filtering by template ID (delegates to wa.get_tasks)."""
    mock_task = mock_task_for_dataset_get(1, intent_template_id=100)

    mock_wa = MagicMock()
    mock_wa.get_tasks.return_value = [mock_task]

    args = Mock(
        task_ids=None,
        sites=None,
        task_type=None,
        template_id=100,
        fields=None,
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 0
    # Verify get_tasks was called with correct template_id filter
    mock_wa.get_tasks.assert_called_once_with(
        sites=None,
        template_id=100,
        action=None,
    )
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert len(output) == 1
    assert output[0]["task_id"] == 1


def test_dataset_get_with_fields(mock_task_for_dataset_get, capsys):
    """Test dataset-get with field selection (task_id, intent_template_id, sites always included)."""
    mock_task = mock_task_for_dataset_get(1)
    # Override model_dump to respect include parameter
    mock_task.model_dump.side_effect = lambda mode, include=None: (
        {
            k: v
            for k, v in {
                "task_id": 1,
                "intent_template_id": 100,
                "sites": ["shopping"],
                "intent": "Test intent for task 1",
            }.items()
            if include is None or k in include
        }
    )

    mock_wa = MagicMock()
    mock_wa.get_tasks.return_value = [mock_task]

    args = Mock(
        task_ids=None,
        sites=None,
        task_type=None,
        template_id=None,
        fields="intent",  # Only request intent, but task_id, intent_template_id, sites should be added
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 0
    # Verify model_dump was called with include containing minimal fields plus intent
    call_kwargs = mock_task.model_dump.call_args.kwargs
    assert "task_id" in call_kwargs["include"]
    assert "intent_template_id" in call_kwargs["include"]
    assert "sites" in call_kwargs["include"]
    assert "intent" in call_kwargs["include"]


def test_dataset_get_output_to_file(mock_task_for_dataset_get, tmp_path):
    """Test dataset-get writing output to file."""
    mock_task = mock_task_for_dataset_get(1)

    mock_wa = MagicMock()
    mock_wa.get_tasks.return_value = [mock_task]

    output_file = tmp_path / "output.json"
    args = Mock(
        task_ids=None,
        sites=None,
        task_type=None,
        template_id=None,
        fields=None,
        output=str(output_file),
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 0
    assert output_file.exists()
    output = json.loads(output_file.read_text())
    assert len(output) == 1
    assert output[0]["task_id"] == 1


def test_dataset_get_no_matching_tasks():
    """Test dataset-get returns error when no tasks match filters."""
    mock_wa = MagicMock()
    mock_wa.get_tasks.return_value = []  # No tasks match

    args = Mock(
        task_ids=None,
        sites="reddit",
        task_type=None,
        template_id=None,
        fields=None,
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 1


def test_dataset_get_invalid_task_id():
    """Test dataset-get returns error for non-existent task ID."""
    mock_wa = MagicMock()
    mock_wa.get_task.side_effect = ValueError("Task not found")

    args = Mock(
        task_ids="9999",
        sites=None,
        task_type=None,
        template_id=None,
        fields=None,
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 1


def test_dataset_get_invalid_task_id_format():
    """Test dataset-get returns error for non-integer task ID."""
    mock_wa = MagicMock()

    args = Mock(
        task_ids="abc,123",  # Invalid format
        sites=None,
        task_type=None,
        template_id=None,
        fields=None,
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 1


def test_dataset_get_invalid_site():
    """Test dataset-get returns error for invalid site name."""
    mock_wa = MagicMock()

    args = Mock(
        task_ids=None,
        sites="invalid_site",
        task_type=None,
        template_id=None,
        fields=None,
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 1


def test_dataset_get_invalid_task_type():
    """Test dataset-get returns error for invalid task type."""
    mock_wa = MagicMock()

    args = Mock(
        task_ids=None,
        sites=None,
        task_type="INVALID",
        template_id=None,
        fields=None,
        output=None,
    )

    with patch("webarena_verified.__main__.WebArenaVerified", return_value=mock_wa):
        exit_code = dataset_get(args)

    assert exit_code == 1
