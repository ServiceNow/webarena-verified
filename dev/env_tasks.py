"""Development environment setup tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

if TYPE_CHECKING:
    from invoke.context import Context


@task
def init(c: Context) -> None:
    """Initialize development environment: sync all dependencies and install pre-commit hooks."""
    c.run("uv sync --all-extras")
    c.run("uv run pre-commit install")
