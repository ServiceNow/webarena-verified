"""Invoke tasks for WebArena-Verified development."""

import json
import subprocess
from pathlib import Path

from compact_json import EolStyle, Formatter
from invoke.tasks import task

# Paths to check/format
CODE_PATHS = "src tests"

# Dataset path
DATASET_FILE = Path("assets/dataset/webarena-verified.json")


@task
def docs_serve(c):
    """Serve the documentation locally with live reload."""
    c.run("uv run mkdocs serve")


@task
def docs_build(c):
    """Build the documentation site."""
    c.run("uv run mkdocs build")


@task
def docs_deploy(c):
    """Deploy documentation to GitHub Pages.

    Safety checks:
    - Ensures current branch is main
    - Ensures local main is up-to-date with remote main
    """
    # Check current branch
    result = c.run("git branch --show-current", hide=True)
    current_branch = result.stdout.strip()

    if current_branch != "main":
        print(f"ERROR: Cannot deploy docs from branch '{current_branch}'")
        print("You must be on the 'main' branch to deploy documentation.")
        raise SystemExit(1)

    # Fetch remote to get latest state
    print("Fetching remote updates...")
    c.run("git fetch origin main", hide=True)

    # Check if local main matches remote main
    local_commit = c.run("git rev-parse main", hide=True).stdout.strip()
    remote_commit = c.run("git rev-parse origin/main", hide=True).stdout.strip()

    if local_commit != remote_commit:
        print("ERROR: Local 'main' branch does not match remote 'origin/main'")
        print(f"  Local:  {local_commit}")
        print(f"  Remote: {remote_commit}")
        print("\nPlease either:")
        print("  - Pull latest changes: git pull origin main")
        print("  - Push your changes: git push origin main")
        raise SystemExit(1)

    print("✓ Safety checks passed: on main branch and in sync with remote")
    print("Deploying documentation to GitHub Pages...")
    c.run("uv run mkdocs gh-deploy")


@task
def data_format(c):
    """Format dataset JSON file."""
    data = load_json(DATASET_FILE)
    save_json(DATASET_FILE, data)


@task
def code_format_and_check(c):
    """Format code using ruff and run type checking."""
    c.run(f"uv run ruff check {CODE_PATHS} --fix --unsafe-fixes")
    c.run(f"uv run ruff format {CODE_PATHS}")
    c.run(f"uv run basedpyright {CODE_PATHS}")


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
