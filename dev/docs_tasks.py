"""Documentation tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

if TYPE_CHECKING:
    from invoke.context import Context


@task
def serve(c: Context) -> None:
    """Serve the documentation locally with live reload."""
    c.run("uv run mkdocs serve")


@task
def build(c: Context) -> None:
    """Build the documentation site."""
    c.run("uv run mkdocs build")


@task
def deploy(c: Context) -> None:
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
