"""Git utilities for dev scripts."""

import subprocess


def get_short_sha() -> str:
    """Get the short git SHA of the current HEAD.

    Returns:
        Short git SHA (7 characters) or 'unknown' if not in a git repo.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
