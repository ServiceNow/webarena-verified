"""Code quality tasks (linting, formatting, type checking, testing)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

if TYPE_CHECKING:
    from invoke.context import Context

from dev.utils import logging_utils


@task(name="lint")
@logging_utils.with_banner()
def lint(ctx: Context) -> None:
    """Run linting and type checking (no fixes) - for CI."""
    logging_utils.print_info("Running ruff check...")
    ctx.run("uv run ruff check")

    logging_utils.print_info("Running ruff format check...")
    ctx.run("uv run ruff format --check")

    logging_utils.print_info("Running ty check...")
    ctx.run("uv run ty check src dev tests")

    logging_utils.print_info("Running actionlint...")
    ctx.run("uv run actionlint")

    logging_utils.print_success("All checks passed")


@task(name="format")
def format_and_check(c: Context) -> None:
    """Format code using ruff and run type checking - for local dev."""
    c.run("uv run ruff check src dev --fix --unsafe-fixes")
    c.run("uv run ruff format src dev")
    c.run("uv run ty check src dev")
    # Verify environment_control package is Python 3.9 compatible
    c.run("uv run vermin -t=3.9 --eval-annotations --no-tips packages/environment_control/environment_control/")


@task(name="test")
@logging_utils.with_banner()
def run_tests(ctx: Context, docker_img: str = "webarena-verified:test") -> None:
    """Run tests.

    Args:
        docker_img: Docker image to use for tests.
    """
    logging_utils.print_info("Building Docker image...")
    ctx.run(f"docker build -t {docker_img} .")

    logging_utils.print_info("Running tests...")
    ctx.run(
        f"uv run pytest --webarena-verified-docker-img {docker_img} "
        "--ignore=tests/integration/environment_control/ "
        "--ignore=tests/integration/environments/"
    )

    logging_utils.print_success("All tests passed")
