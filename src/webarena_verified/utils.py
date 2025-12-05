"""Utility functions for WebArena-Verified."""

from pathlib import Path
from typing import Literal


def find_project_root(start_path: Path | None = None) -> Path:
    """Find project root by looking for .webarena_verified_root marker file.

    Args:
        start_path: Starting path for search. If None, starts from this file's directory.

    Returns:
        Path to project root directory.
    """
    if start_path is None:
        start_path = Path(__file__).parent

    current = start_path.resolve()

    # Walk up the directory tree
    for parent in [current, *current.parents]:
        if (parent / ".webarena_verified_root").exists():
            return parent

    # Fallback to cwd if no marker found
    return Path.cwd()


def get_package_assets_path() -> Path:
    """Get the path to the assets directory.

    Works in both:
    - Installed package: assets are at site-packages/webarena_verified/assets/
    - Development mode: assets are at project_root/assets/

    Returns:
        Path to the assets directory.
    """
    # First try: installed package location (relative to this file)
    package_assets = Path(__file__).parent / "assets"
    if package_assets.exists():
        return package_assets

    # Second try: development mode (project root)
    project_assets = find_project_root() / "assets"
    if project_assets.exists():
        return project_assets

    # Fallback to installed location (even if it doesn't exist yet)
    return package_assets


def get_agent_response_file_path(
    task_dir: Path,
    task_id: int,
    *,
    name: str = "agent_response.json",
    ensure: bool = False,
) -> Path:
    """Get path to agent response file for a task.

    Args:
        task_dir: Directory containing task outputs
        task_id: Task identifier (reserved for future use)
        name: Filename for the agent response file
        ensure: If True, validate that the file exists and is not empty

    Returns:
        Path to agent_response.json file

    Raises:
        FileNotFoundError: If ensure=True and file doesn't exist
        ValueError: If ensure=True and file is empty
    """
    path = task_dir / name
    if ensure and not path.exists():
        raise FileNotFoundError(f"Agent response file not found: {path}")
    return path


def get_trace_file_path(
    task_dir: Path,
    task_id: int,
    *,
    name: str = "network.har",
    ensure: bool = False,
    trace_format: Literal["zip", "har"] = "zip",
) -> Path:
    """Get path to trace file for a task.

    Args:
        task_dir: Directory containing task outputs
        task_id: Task identifier (reserved for future use)
        name: Filename for the trace file
        ensure: If True, validate that the file exists
        trace_format: Trace format - "zip" for Playwright, "har" for HAR (default: "zip")
                     Used only if name doesn't include extension

    Returns:
        Path to trace file

    Raises:
        FileNotFoundError: If ensure=True and file doesn't exist
    """
    filename = name

    # If name doesn't have an extension, add one based on trace_format
    if "." not in filename:
        extension = "zip" if trace_format == "zip" else "json"
        filename = f"{filename}.{extension}"

    path = task_dir / filename
    if ensure and not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")
    return path


def get_eval_result_file_path(
    task_dir: Path,
    task_id: int,
    *,
    name: str = "eval_result.json",
) -> Path:
    """Get path to evaluation result file for a task.

    Args:
        task_dir: Directory containing task outputs
        task_id: Task identifier (reserved for future use)
        name: Filename for the evaluation result file

    Returns:
        Path to eval_result.json file
    """
    return task_dir / name
