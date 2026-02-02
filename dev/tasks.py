"""Invoke tasks for WebArena-Verified development."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from compact_json import EolStyle, Formatter
from invoke.tasks import task

from .utils.docker_utils import (
    DOCKER_IMAGE,
    GIT_REPO_URL,
    check_repo_clean_at_tag,
    confirm,
    get_version,
    validate_semver,
)

# Dataset path
DATASET_FILE = Path("assets/dataset/webarena-verified.json")


@task
def env_init(c):
    """Initialize development environment: sync all dependencies and install pre-commit hooks."""
    c.run("uv sync --all-groups --all-extras")
    c.run("uv run pre-commit install")


@task
def docs_serve(c):
    """Serve the documentation locally with live reload."""
    c.run("uv run mkdocs serve")


@task
def docs_build(c):
    """Build the documentation site."""
    c.run("uv run mkdocs build")


@task
def docker_build(c, push=False, dry_run=False, version=None):
    """Build Docker image with current version tag.

    Args:
        push: If True, push the image after building (with confirmation prompts)
        dry_run: If True, print commands without executing them
        version: Optional semver version to build (clones repo at tag in temp dir)
    """
    if version:
        _docker_build_from_tag(c, version, push, dry_run)
    else:
        _docker_build_local(c, push, dry_run)


def _docker_build_local(c, push: bool, dry_run: bool) -> None:
    """Build Docker image from local repo (must be clean and at tag)."""
    version = get_version()
    check_repo_clean_at_tag(version)
    _build_and_push(c, version, push, dry_run, build_dir=".")


def _docker_build_from_tag(c, version: str, push: bool, dry_run: bool) -> None:
    """Build Docker image by cloning repo at specific tag."""
    validate_semver(version)
    tag = f"v{version}"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        print(f"Using temporary directory: {tmpdir}")

        # Clone repo at the exact tag
        print(f"Cloning {GIT_REPO_URL} at tag {tag}...")
        c.run(f"git clone --depth 1 --branch {tag} {GIT_REPO_URL} {tmpdir}")

        # TODO: Remove once all releases have Dockerfile
        _copy_missing_files(tmppath)

        # Sync dependencies (no dev, no extras)
        print("Syncing dependencies...")
        with c.cd(tmpdir):
            c.run("uv sync --no-dev --no-group dev")
            c.run("uv lock")

            # TODO: Remove this check once all releases have tests
            tests_dir = tmppath / "tests"
            if tests_dir.exists() and any(tests_dir.glob("test_*.py")):
                print("Running tests...")
                c.run("uv run pytest")
            else:
                print("Skipping tests (no tests directory found)")

        _build_and_push(c, version, push, dry_run, build_dir=tmpdir)


def _copy_missing_files(target_dir: Path) -> None:
    """Copy Dockerfile from current dir if missing in target.

    TODO: Remove this function once all releases have Dockerfile.
    """
    target_dockerfile = target_dir / "Dockerfile"
    if not target_dockerfile.exists():
        source_dockerfile = Path("Dockerfile")
        if source_dockerfile.exists():
            print(f"Copying Dockerfile to {target_dockerfile}...")
            shutil.copy(source_dockerfile, target_dockerfile)


def _build_and_push(c, version: str, push: bool, dry_run: bool, build_dir: str) -> None:
    """Build and optionally push Docker image."""
    version_tag = f"{DOCKER_IMAGE}:{version}"
    latest_tag = f"{DOCKER_IMAGE}:latest"

    def run(cmd: str) -> None:
        if dry_run:
            print(f"[dry-run] {cmd}")
        else:
            c.run(cmd)

    # Build the image
    print(f"Building {version_tag}...")
    run(f"docker build -t {version_tag} {build_dir}")

    if not push:
        print(f"Image built: {version_tag}")
        print("Run with --push to push the image to the registry.")
        return

    # Ask before pushing version tag
    if not dry_run and not confirm(f"Push {version_tag}?"):
        print("Push cancelled.")
        return

    print(f"Pushing {version_tag}...")
    run(f"docker push {version_tag}")

    # Ask before tagging and pushing latest
    if dry_run or confirm(f"Also tag and push as {latest_tag}?"):
        run(f"docker tag {version_tag} {latest_tag}")
        print(f"Pushing {latest_tag}...")
        run(f"docker push {latest_tag}")


@task
def data_format(c):
    """Format dataset JSON file."""
    data = load_json(DATASET_FILE)
    save_json(DATASET_FILE, data)


@task
def code_format_and_check(c):
    """Format code using ruff and run type checking."""
    c.run("uv run ruff check src dev --fix --unsafe-fixes")
    c.run("uv run ruff format src dev")
    c.run("uv run ty check src dev")


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
