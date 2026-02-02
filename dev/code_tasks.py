"""Code quality tasks (linting, formatting, type checking)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

if TYPE_CHECKING:
    from invoke.context import Context


@task
def code_format_and_check(c: Context) -> None:
    """Format code using ruff and run type checking."""
    c.run("uv run ruff check src dev --fix --unsafe-fixes")
    c.run("uv run ruff format src dev")
    c.run("uv run ty check src dev")
    # Verify environment_control package is Python 3.9 compatible
    c.run("uv run vermin -t=3.9 --eval-annotations --no-tips packages/environment_control/environment_control/")
