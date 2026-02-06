"""Integration tests for create-submission-pkg CLI command.

Tests the full flow:
1. CLI argument parsing and validation
2. Output directory discovery and task file collection
3. HAR file trimming and copying
4. Submission package creation (tar.gz or folder)
5. Summary JSON generation
6. Error handling and edge cases
"""

import argparse
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from webarena_verified.__main__ import create_submission_pkg

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def create_task_output(har_file_example: Path):
    """Helper to create task output directories with required files.

    Returns callable that creates task directory with agent_response.json and network.har.
    """

    def _create(
        base_dir: Path,
        task_id: int,
        include_agent_response: bool = True,
        include_har: bool = True,
        invalid_har: bool = False,
        empty_agent_response: bool = False,
    ):
        """Create task output directory with files.

        Args:
            base_dir: Base directory to create task directory in
            task_id: Task ID (directory name)
            include_agent_response: Whether to create agent_response.json
            include_har: Whether to create network.har
            invalid_har: If True, create malformed HAR file
            empty_agent_response: If True, create empty agent response
        """
        task_dir = base_dir / str(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        # Create agent_response.json
        if include_agent_response:
            agent_response = {} if empty_agent_response else {"answer": f"test answer {task_id}"}
            task_dir.joinpath("agent_response.json").write_text(json.dumps(agent_response, indent=2))

        # Create network.har
        if include_har:
            if invalid_har:
                # Write invalid JSON
                task_dir.joinpath("network.har").write_text("invalid json {{{")
            else:
                # Copy from example HAR file
                shutil.copy2(har_file_example, task_dir / "network.har")

        return task_dir

    return _create


@pytest.fixture
def mock_args():
    """Helper to create mock argparse args for create_submission_pkg command."""

    def _create(run_output_dir, output, no_tar=False, name=None):
        """Create argparse.Namespace with command arguments.

        Args:
            run_output_dir: List of output directories or single directory
            output: Output root directory
            no_tar: If True, create folder instead of tar
            name: Custom name for submission
        """
        if isinstance(run_output_dir, (str, Path)):
            run_output_dir = [str(run_output_dir)]
        else:
            run_output_dir = [str(d) for d in run_output_dir]

        return argparse.Namespace(
            run_output_dir=run_output_dir,
            output=str(output),
            no_tar=no_tar,
            name=name,
        )

    return _create


# ============================================================================
# Tests: Basic Success Cases
# ============================================================================


def test_create_submission_tar_single_directory(tmp_path, create_task_output, mock_args):
    """Test creating tar submission from single directory with valid tasks."""
    # Setup: Create output directory with 3 valid tasks
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    create_task_output(output_dir, 1)
    create_task_output(output_dir, 2)
    create_task_output(output_dir, 3)

    submission_root = tmp_path / "submissions"
    submission_root.mkdir()

    args = mock_args(run_output_dir=output_dir, output=submission_root)

    # Execute
    exit_code = create_submission_pkg(args)

    # Verify
    assert exit_code == 0

    # Find created tar file (has timestamp in name)
    tar_files = list(submission_root.glob("webarena-verified-submission-*.tar.gz"))
    assert len(tar_files) == 1
    tar_path = tar_files[0]

    # Verify tar contents
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getnames()
        assert "summary.json" in members
        assert "1/agent_response.json" in members
        assert "1/network.har" in members
        assert "2/agent_response.json" in members
        assert "2/network.har" in members
        assert "3/agent_response.json" in members
        assert "3/network.har" in members

    # Verify summary file exists
    summary_files = list(submission_root.glob("webarena-verified-submission-*_summary.json"))
    assert len(summary_files) == 1


def test_create_submission_folder_output(tmp_path, create_task_output, mock_args):
    """Test creating folder submission (no tar) with valid tasks."""
    # Setup
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    create_task_output(output_dir, 1)
    create_task_output(output_dir, 2)

    submission_root = tmp_path / "submissions"
    submission_root.mkdir()

    args = mock_args(run_output_dir=output_dir, output=submission_root, no_tar=True)

    # Execute
    exit_code = create_submission_pkg(args)

    # Verify
    assert exit_code == 0

    # Find created folder (has timestamp in name)
    submission_dirs = list(submission_root.glob("webarena-verified-submission-*"))
    submission_dirs = [d for d in submission_dirs if d.is_dir()]
    assert len(submission_dirs) == 1
    submission_dir = submission_dirs[0]

    # Verify folder structure
    assert (submission_dir / "summary.json").exists()
    assert (submission_dir / "1" / "agent_response.json").exists()
    assert (submission_dir / "1" / "network.har").exists()
    assert (submission_dir / "2" / "agent_response.json").exists()
    assert (submission_dir / "2" / "network.har").exists()


def test_create_submission_custom_name(tmp_path, create_task_output, mock_args):
    """Test creating submission with custom name."""
    # Setup
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    create_task_output(output_dir, 1)

    submission_root = tmp_path / "submissions"
    submission_root.mkdir()

    args = mock_args(run_output_dir=output_dir, output=submission_root, name="my-submission")

    # Execute
    exit_code = create_submission_pkg(args)

    # Verify
    assert exit_code == 0

    # Verify custom name is used
    tar_path = submission_root / "my-submission.tar.gz"
    assert tar_path.exists()

    summary_path = submission_root / "my-submission.tar_summary.json"
    assert summary_path.exists()


# ============================================================================
# Tests: Multiple Directories
# ============================================================================


def test_create_submission_multiple_directories(tmp_path, create_task_output, mock_args):
    """Test creating submission from multiple output directories."""
    # Setup: Create two output directories with different tasks
    output_dir1 = tmp_path / "output1"
    output_dir1.mkdir()
    create_task_output(output_dir1, 1)
    create_task_output(output_dir1, 2)

    output_dir2 = tmp_path / "output2"
    output_dir2.mkdir()
    create_task_output(output_dir2, 3)
    create_task_output(output_dir2, 4)

    submission_root = tmp_path / "submissions"
    submission_root.mkdir()

    args = mock_args(run_output_dir=[output_dir1, output_dir2], output=submission_root)

    # Execute
    exit_code = create_submission_pkg(args)

    # Verify
    assert exit_code == 0

    # Verify all tasks are included
    tar_files = list(submission_root.glob("*.tar.gz"))
    assert len(tar_files) == 1

    with tarfile.open(tar_files[0], "r:gz") as tar:
        members = tar.getnames()
        assert "1/agent_response.json" in members
        assert "2/agent_response.json" in members
        assert "3/agent_response.json" in members
        assert "4/agent_response.json" in members


# ============================================================================
# Tests: Missing Files Handling
# ============================================================================


def test_create_submission_missing_agent_response(tmp_path, create_task_output, mock_args):
    """Test handling of tasks with missing agent_response.json."""
    # Setup
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Task 1: valid
    create_task_output(output_dir, 1)
    # Task 2: missing agent response
    create_task_output(output_dir, 2, include_agent_response=False)

    submission_root = tmp_path / "submissions"
    submission_root.mkdir()

    args = mock_args(run_output_dir=output_dir, output=submission_root, name="test-missing")

    # Execute
    exit_code = create_submission_pkg(args)

    # Verify
    assert exit_code == 0

    # Load summary
    summary_path = submission_root / "test-missing.tar_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text())

    # Verify task 2 is in missing_agent_response
    assert 1 in summary["packaged_tasks"]["task_ids"]
    assert 2 in summary["issues"]["missing_files"]["missing_agent_response_only"]["task_ids"]
    assert 2 not in summary["packaged_tasks"]["task_ids"]


def test_create_submission_missing_har(tmp_path, create_task_output, mock_args):
    """Test handling of tasks with missing network.har."""
    # Setup
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Task 1: valid
    create_task_output(output_dir, 1)
    # Task 2: missing HAR
    create_task_output(output_dir, 2, include_har=False)

    submission_root = tmp_path / "submissions"
    submission_root.mkdir()

    args = mock_args(run_output_dir=output_dir, output=submission_root, name="test-missing-har")

    # Execute
    exit_code = create_submission_pkg(args)

    # Verify
    assert exit_code == 0

    # Load summary
    summary_path = submission_root / "test-missing-har.tar_summary.json"
    summary = json.loads(summary_path.read_text())

    # Verify task 2 is in missing_network_har
    assert 1 in summary["packaged_tasks"]["task_ids"]
    assert 2 in summary["issues"]["missing_files"]["missing_network_har_only"]["task_ids"]
    assert 2 not in summary["packaged_tasks"]["task_ids"]


# ============================================================================
# Tests: Invalid HAR Handling
# ============================================================================


def test_create_submission_invalid_har_file(tmp_path, create_task_output, mock_args):
    """Test handling of tasks with invalid/malformed HAR files."""
    # Setup
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Task 1: valid
    create_task_output(output_dir, 1)
    # Task 2: invalid HAR
    create_task_output(output_dir, 2, invalid_har=True)

    submission_root = tmp_path / "submissions"
    submission_root.mkdir()

    args = mock_args(run_output_dir=output_dir, output=submission_root, name="test-invalid-har")

    # Execute
    exit_code = create_submission_pkg(args)

    # Verify
    assert exit_code == 0

    # Load summary
    summary_path = submission_root / "test-invalid-har.tar_summary.json"
    summary = json.loads(summary_path.read_text())

    # Verify task 2 is in invalid_har_files
    assert 1 in summary["packaged_tasks"]["task_ids"]
    assert 2 in summary["issues"]["missing_files"]["invalid_har_files"]["task_ids"]
    assert 2 not in summary["packaged_tasks"]["task_ids"]


# ============================================================================
# Tests: Error Cases
# ============================================================================


def test_create_submission_output_exists(tmp_path, create_task_output, mock_args):
    """Test error when output path already exists."""
    # Setup
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    create_task_output(output_dir, 1)

    submission_root = tmp_path / "submissions"
    submission_root.mkdir()

    # Create submission once
    args = mock_args(run_output_dir=output_dir, output=submission_root, name="duplicate-test")
    exit_code = create_submission_pkg(args)
    assert exit_code == 0

    # Try creating again with same name
    exit_code = create_submission_pkg(args)

    # Verify error
    assert exit_code == 1


def test_create_submission_no_valid_tasks(tmp_path, mock_args):
    """Test error when no valid tasks are found."""
    # Setup: Empty output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    submission_root = tmp_path / "submissions"
    submission_root.mkdir()

    args = mock_args(run_output_dir=output_dir, output=submission_root, name="no-tasks")

    # Execute
    exit_code = create_submission_pkg(args)

    # Verify error
    assert exit_code == 1


# ============================================================================
# Tests: Summary Validation
# ============================================================================


def test_create_submission_summary_structure(tmp_path, create_task_output, mock_args):
    """Test summary.json structure with mix of valid/invalid/missing tasks."""
    # Setup: Mix of scenarios
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Valid tasks
    create_task_output(output_dir, 1)
    create_task_output(output_dir, 2)

    # Missing agent response
    create_task_output(output_dir, 3, include_agent_response=False)

    # Missing HAR
    create_task_output(output_dir, 4, include_har=False)

    # Invalid HAR
    create_task_output(output_dir, 5, invalid_har=True)

    # Empty agent response
    create_task_output(output_dir, 6, empty_agent_response=True)

    submission_root = tmp_path / "submissions"
    submission_root.mkdir()

    args = mock_args(run_output_dir=output_dir, output=submission_root, name="summary-test")

    # Execute
    exit_code = create_submission_pkg(args)
    assert exit_code == 0

    # Load and validate summary
    summary_path = submission_root / "summary-test.tar_summary.json"
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text())

    # Verify required top-level fields exist
    assert "metadata" in summary
    assert "packaging_summary" in summary
    assert "packaged_tasks" in summary
    assert "issues" in summary

    # Verify packaging_summary fields
    assert "tasks_packaged" in summary["packaging_summary"]
    assert "tasks_with_issues" in summary["packaging_summary"]
    assert "duplicate_tasks" in summary["packaging_summary"]
    assert "unknown_tasks" in summary["packaging_summary"]
    assert "missing_from_output" in summary["packaging_summary"]

    # Verify issues structure exists
    assert "missing_files" in summary["issues"]
    assert "duplicate_tasks" in summary["issues"]
    assert "unknown_tasks" in summary["issues"]
    assert "missing_from_output" in summary["issues"]

    # Verify counts match expectations
    assert len(summary["packaged_tasks"]["task_ids"]) == 3  # Tasks 1, 2, and 6
    assert 1 in summary["packaged_tasks"]["task_ids"]
    assert 2 in summary["packaged_tasks"]["task_ids"]
    assert 6 in summary["packaged_tasks"]["task_ids"]

    assert 3 in summary["issues"]["missing_files"]["missing_agent_response_only"]["task_ids"]
    assert 4 in summary["issues"]["missing_files"]["missing_network_har_only"]["task_ids"]
    assert 5 in summary["issues"]["missing_files"]["invalid_har_files"]["task_ids"]
    # Note: Task 6 has empty agent response but is still packaged
