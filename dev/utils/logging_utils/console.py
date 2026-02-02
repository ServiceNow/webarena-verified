"""Rich console setup and availability check."""

from __future__ import annotations

import sys

# Check for Rich library availability
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print(
        "ERROR: Rich library is required for CLI output formatting.\n"
        "Rich is a dev dependency. Install it with:\n\n"
        "    uv sync --group dev\n\n"
        "Or install rich directly:\n\n"
        "    uv pip install rich\n",
        file=sys.stderr,
    )
    raise

console = Console()

__all__ = ["Console", "Panel", "Table", "Text", "console"]
