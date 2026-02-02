"""Path utilities for dev scripts."""

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_repo_root() -> Path:
    """Get the repository root directory.

    Traverses up from this file to find the .git directory.

    Returns:
        Path to the repository root.

    Raises:
        FileNotFoundError: If the repository root cannot be found.
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError("Could not find repository root (no .git directory found)")
