"""CLI output formatting using Rich.

This module provides consistent, beautiful terminal output for Docker CLI commands.
It replaces plain logger.info() calls with Rich components for better UX.

Features:
    - Banners: Command headers with site context
    - Config tables: Display configuration in aligned tables
    - Step context: Command execution with spinner and status
    - Success/failure: Colored status messages
    - List printing: Indented list output

Requirements:
    Rich library (dev dependency): uv sync --group dev

Usage:
    from dev.utils.logging_utils import (
        console, print_banner, StepContext, print_success
    )

    print_banner("START CONTAINER", data={"Site": "shopping-admin"})
    print_table({"Image": "am1n3e/webarena:shopping_admin", "Port": 6680})
    with StepContext.create("docker rm -f shopping_admin", desc="Removing container"):
        ctx.run("docker rm -f shopping_admin", hide=True)
    print_success("Container started!", URL="http://localhost:6680")
"""

from .console import console
from .printers import (
    print_banner,
    print_error,
    print_failure,
    print_info,
    print_list,
    print_success,
    print_table,
    print_warning,
    with_banner,
)
from .step_context import StepContext

__all__ = [
    "StepContext",
    "console",
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
