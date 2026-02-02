"""Basic print utilities using Rich."""

from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from .console import Panel, Table, Text, console

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")
R = TypeVar("R")


def print_banner(title: str, data: dict[str, Any] | None = None) -> None:
    """Print command banner with title, separator, and key-value pairs.

    Args:
        title: Main title text (e.g., "START CONTAINER").
        data: Optional dict of key-value pairs to display below the title.

    Examples:
        >>> print_banner("CREATE SLIM IMAGE")
        ╭──────────────────────────────────────────────────────────╮
        │ CREATE SLIM IMAGE                                        │
        ╰──────────────────────────────────────────────────────────╯

        >>> print_banner("START CONTAINER", {"Site": "gitlab", "Mode": "slim"})
        ╭──────────────────────────────────────────────────────────╮
        │ START CONTAINER                                          │
        │ Site: gitlab                                             │
        │ Mode: slim                                               │
        ╰──────────────────────────────────────────────────────────╯
    """
    content = Text()
    if data:
        for i, (key, value) in enumerate(data.items()):
            if i > 0:
                content.append("\n")
            content.append(f"{key}: ", style="dim")
            content.append(str(value), style="cyan")
    console.print()
    console.print(Panel(content, style="blue", title=f"[bold]{title}[/]", title_align="center"))
    console.print()


def print_table(data: dict[str, Any]) -> None:
    """Print key-value data as an aligned table.

    Args:
        data: Dictionary of key-value pairs to display.

    Example:
        >>> print_table({"Image": "am1n3e/webarena:shopping", "Port": 6680})
          Image  am1n3e/webarena:shopping
          Port   6680
    """
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim")
    table.add_column("Value", style="cyan")
    for key, value in data.items():
        table.add_row(key, str(value))
    console.print(table)
    console.print()


def print_success(message: str = "SUCCESS", **details: Any) -> None:
    """Print success message with optional details.

    Args:
        message: Success message to display (default: "SUCCESS").
        **details: Key-value pairs to display below the message.

    Example:
        >>> print_success("Container started!", Container="shopping_admin", URL="http://localhost:6680")

        ✓ Container started!
          Container: shopping_admin
          URL: http://localhost:6680
    """
    console.print()
    console.print(f"[bold green]✓ {message}[/]")
    if details:
        for key, value in details.items():
            console.print(f"  [dim]{key}:[/] [cyan]{value}[/]")


def print_failure(message: str = "FAILED", error: str | None = None) -> None:
    """Print failure message with optional error details.

    Args:
        message: Failure message to display (default: "FAILED").
        error: Optional error details to show below the message.

    Example:
        >>> print_failure("Container failed to start", error="Port 6680 already in use")

        ✗ Container failed to start
          Port 6680 already in use
    """
    console.print()
    console.print(f"[bold red]✗ {message}[/]")
    if error:
        console.print(f"  [dim]{error}[/]")


def print_list(lines: list[str], indent_rest: int = 2) -> None:
    """Print a list with first line unindented and rest indented.

    Args:
        lines: List of strings to print.
        indent_rest: Number of spaces to indent lines after the first (default: 2).

    Example:
        >>> print_list(["Next steps:", "inv docker.shell", "inv docker.stop"])
        Next steps:
          inv docker.shell
          inv docker.stop
    """
    if not lines:
        return
    console.print(lines[0])
    prefix = " " * indent_rest
    for line in lines[1:]:
        console.print(f"{prefix}{line}")


def print_info(message: str) -> None:
    """Print an info message.

    Args:
        message: Message to display.

    Example:
        >>> print_info("Container shopping_admin removed.")
          Container shopping_admin removed.
    """
    console.print(f"  {message}")


def print_warning(message: str) -> None:
    """Print a warning message.

    Args:
        message: Warning message to display.

    Example:
        >>> print_warning("Port 6680 is already in use, using 6681 instead.")
          ⚠ Port 6680 is already in use, using 6681 instead.
    """
    console.print(f"  [yellow]⚠ {message}[/]")


def print_error(message: str) -> None:
    """Print an error message (without full failure banner).

    Args:
        message: Error message to display.

    Example:
        >>> print_error("Failed to connect to Docker daemon.")
          ✗ Failed to connect to Docker daemon.
    """
    console.print(f"  [red]✗ {message}[/]")


def with_banner(
    exclude: set[str] | None = None,
    include_false: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that prints a banner with function name and args before execution.

    Args:
        exclude: Additional parameter names to exclude from banner. "self" and "ctx"
            are always excluded automatically.
        include_false: If True, include parameters with False/None values (default: False).

    Example:
        @with_banner()
        def create_optimized_img(ctx, source=None, output=None, port=6680, skip_tests=False):
            ...

        # When called as: create_optimized_img(ctx, source="img:v1", port=8080)
        # Prints banner:
        # ╭─────────────────────────────────────────╮
        # │        CREATE OPTIMIZED IMG             │
        # │ Source: img:v1                          │
        # │ Port: 8080                              │
        # ╰─────────────────────────────────────────╯
    """
    # Always exclude self and ctx, plus any user-provided excludes
    base_exclude = {"self", "ctx"}
    effective_exclude = base_exclude | (exclude or set())

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Get function signature
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Build banner title from function name
            title = func.__name__.replace("_", " ").upper()  # type: ignore[attr-defined]

            # Build data dict from arguments
            data = {}
            for name, value in bound.arguments.items():
                if name in effective_exclude:
                    continue
                if not include_false and (value is None or value is False):
                    continue
                # Format the key nicely
                key = name.replace("_", " ").title()
                data[key] = value

            print_banner(title, data if data else None)
            return func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "print_banner",
    "print_error",
    "print_failure",
    "print_info",
    "print_list",
    "print_success",
    "print_table",
    "print_warning",
    "with_banner",
]
