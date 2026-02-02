"""CLI entry point for running as a module.

Usage:
    python -m environment_control <command> [options]
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
