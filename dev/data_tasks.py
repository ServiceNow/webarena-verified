"""Dataset formatting tasks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from compact_json import EolStyle, Formatter
from invoke.tasks import task

if TYPE_CHECKING:
    from invoke.context import Context

# Dataset path
DATASET_FILE = Path("assets/dataset/webarena-verified.json")


@task(name="format")
def format_json(c: Context) -> None:
    """Format dataset JSON file."""
    data = load_json(DATASET_FILE)
    save_json(DATASET_FILE, data)


def load_json(file_path: Path) -> list[dict]:
    """Load JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is invalid JSON
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {file_path}: {e}") from e

    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {file_path}, got {type(data).__name__}")

    return data


def check_git_status(file_path: Path) -> bool:
    """Check if the file has uncommitted changes in git.

    Args:
        file_path: Path to the file to check

    Returns:
        True if file is safe to modify (not tracked or no uncommitted changes)
        False if file has uncommitted changes
    """
    try:
        # Check if file is tracked by git
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        # If file is not tracked, it's safe to modify
        if result.returncode != 0:
            return True

        # File is tracked, check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain", str(file_path)],
            capture_output=True,
            text=True,
            check=True,
        )

        # If output is empty, no uncommitted changes
        return len(result.stdout.strip()) == 0

    except subprocess.CalledProcessError:
        # If git command fails, assume it's safe (not a git repo)
        return True


def save_json(file_path: Path, data: list[dict], skip_git_check: bool = False) -> None:
    """Save JSON data to file with consistent formatting and key ordering.

    Args:
        file_path: Path to output file
        data: List of task objects
        skip_git_check: Skip git status check

    Raises:
        ValueError: If file has uncommitted changes in git
    """
    # Check git status before modifying file
    if not skip_git_check and not check_git_status(file_path):
        raise ValueError(
            f"{file_path} has uncommitted changes. Please commit or stash them first before running transforms."
        )

    # Define the desired key order
    key_order = [
        "sites",
        "task_id",
        "intent_template_id",
        "start_url",
        "start_urls",
        "intent",
        "intent_template",
        "instantiation_dict",
        "retrieved_data_format_spec",
        "start_url_context",
        "eval",
        "revision",
    ]

    # Reorder keys in each task
    ordered_data = []
    for task_data in data:
        ordered_task = {}
        # Add keys in the specified order if they exist
        for key in key_order:
            if key in task_data:
                ordered_task[key] = task_data[key]
        # Add any remaining keys in alphabetical order
        remaining_keys = sorted(set(task_data.keys()) - set(key_order))
        for key in remaining_keys:
            ordered_task[key] = task_data[key]
        ordered_data.append(ordered_task)

    # Configure compact_json formatter
    formatter = Formatter()
    formatter.indent_spaces = 2
    formatter.max_inline_complexity = 10
    formatter.json_eol_style = EolStyle.LF
    formatter.omit_trailing_whitespace = True

    # Ensure directory exists and write formatted output
    file_path.parent.mkdir(parents=True, exist_ok=True)
    formatter.dump(ordered_data, output_file=str(file_path))
