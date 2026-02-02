"""Step context manager for running commands with spinner and status."""

from __future__ import annotations

from typing import Any

from rich.markup import escape

from .console import console


class StepContext:
    """Context manager for running a step with spinner and status.

    Prints command at top, shows spinner with description while running,
    then checkmark or X with description on completion.

    Example:
        >>> with StepContext.create("docker build -t myimage .", desc="Building image") as step:
        ...     result = ctx.run("docker build -t myimage .", hide=True)
        ...     if result.failed:
        ...         step.mark_failed("Build failed")
        $ docker build -t myimage .
          <logs appear here>
        ✓ Success: Building image

        >>> with StepContext.create("docker push myimage", desc="Pushing") as step:
        ...     step.mark_failed("Authentication failed")
        $ docker push myimage
        ✗ Failed: Pushing
          Authentication failed

    Use plain=True to avoid Rich markup parsing (useful when command output
    contains paths like [/etc/gitlab] that Rich interprets as markup).
    """

    def __init__(self, cmd: str, desc: str | None = None, plain: bool = False) -> None:
        self.cmd = cmd
        self.desc = desc or cmd
        self.plain = plain
        self._failed = False
        self._error_msg: str | None = None
        self._status = None

    @classmethod
    def create(cls, cmd: str, desc: str | None = None, plain: bool = False) -> StepContext:
        """Create a step context for running commands with spinner and status.

        Args:
            cmd: The command being run (displayed to user).
            desc: Optional description shown next to spinner.
            plain: Use plain print instead of Rich (avoids markup parsing issues).

        Returns:
            StepContext that shows spinner while running, then ✓ or ✗ on exit.

        Example:
            >>> with StepContext.create("docker run -d nginx", desc="Starting container") as step:
            ...     result = ctx.run("docker run -d nginx", hide=True)
            ...     if not result.ok:
            ...         step.mark_failed("Container failed to start")
        """
        return cls(cmd, desc, plain)

    def mark_failed(self, msg: str | None = None) -> None:
        """Mark this step as failed with optional error message."""
        self._failed = True
        self._error_msg = msg

    def __enter__(self) -> StepContext:
        if self.plain:
            print(f"$ {self.cmd}")
            print()
        else:
            console.print(f"[dim]$[/] [green]{self.cmd}[/]")
            console.print()
            self._status = console.status(f"[dim]Running:[/] {self.desc}...", spinner="dots")
            self._status.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._status:
            self._status.stop()

        if exc_type is not None:
            self._failed = True
            if self._error_msg is None:
                self._error_msg = str(exc_val)

        if self.plain:
            if self._failed:
                print(f"✗ Failed: {self.desc}")
                if self._error_msg:
                    print(f"  {self._error_msg}")
            else:
                print(f"✓ Success: {self.desc}")
            print("-" * 40)
        else:
            if self._failed:
                console.print(f"[red]✗ Failed:[/] {self.desc}")
                if self._error_msg:
                    console.print(f"  [dim]{escape(self._error_msg)}[/]")
            else:
                console.print(f"[green]✓ Success:[/] {self.desc}")
            console.rule(style="dim")


__all__ = ["StepContext"]
