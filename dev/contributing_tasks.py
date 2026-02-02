"""Invoke tasks for WebArena-Verified development."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from compact_json import EolStyle, Formatter
from invoke.tasks import task

if TYPE_CHECKING:
    from invoke.context import Context

from dev.utils import git_utils

# Dataset path
DATASET_FILE = Path("assets/dataset/webarena-verified.json")


@task
def env_init(c: Context) -> None:
    """Initialize development environment: sync all dependencies and install pre-commit hooks."""
    c.run("uv sync --all-extras")
    c.run("uv run pre-commit install")


@task
def docs_serve(c: Context) -> None:
    """Serve the documentation locally with live reload."""
    c.run("uv run mkdocs serve")


@task
def docs_build(c: Context) -> None:
    """Build the documentation site."""
    c.run("uv run mkdocs build")


@task
def docs_deploy(c: Context) -> None:
    """Deploy documentation to GitHub Pages.

    Safety checks:
    - Ensures current branch is main
    - Ensures local main is up-to-date with remote main
    """
    # Check current branch
    result = c.run("git branch --show-current", hide=True)
    assert result is not None
    current_branch = result.stdout.strip()

    if current_branch != "main":
        print(f"ERROR: Cannot deploy docs from branch '{current_branch}'")
        print("You must be on the 'main' branch to deploy documentation.")
        raise SystemExit(1)

    # Fetch remote to get latest state
    print("Fetching remote updates...")
    c.run("git fetch origin main", hide=True)

    # Check if local main matches remote main
    local_result = c.run("git rev-parse main", hide=True)
    remote_result = c.run("git rev-parse origin/main", hide=True)
    assert local_result is not None
    assert remote_result is not None
    local_commit = local_result.stdout.strip()
    remote_commit = remote_result.stdout.strip()

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
def data_format(c: Context) -> None:
    """Format dataset JSON file."""
    data = load_json(DATASET_FILE)
    save_json(DATASET_FILE, data)


@task
def code_format_and_check(c: Context) -> None:
    """Format code using ruff and run type checking."""
    c.run("uv run ruff check src dev --fix --unsafe-fixes")
    c.run("uv run ruff format src dev")
    c.run("uv run ty check src dev")
    # Verify environment_control package is Python 3.9 compatible
    c.run("uv run vermin -t=3.9 --eval-annotations --no-tips packages/environment_control/environment_control/")


@task
def docker_build(c: Context, tag: str | None = None, publish: bool = False) -> None:
    """Build the webarena-verified Docker image.

    Always tags with git short SHA. Optionally adds an additional tag.

    Args:
        tag: Optional additional tag (e.g., "latest", "v1.0.0")
        publish: Push image to Docker Hub after building
    """
    image = "am1n3e/webarena-verified"
    short_sha = git_utils.get_short_sha()

    image_tags = [f"{image}:{short_sha}"]
    if tag:
        image_tags.append(f"{image}:{tag}")

    tags_arg = " ".join(f"-t {t}" for t in image_tags)
    c.run(f"docker build {tags_arg} .")

    if publish:
        print(f"\nAbout to push: {', '.join(image_tags)}")
        confirm = input("Push to Docker Hub? [y/N]: ").strip().lower()
        if confirm == "y":
            for t in image_tags:
                c.run(f"docker push {t}")
            print("Done.")
        else:
            print("Push cancelled.")


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
