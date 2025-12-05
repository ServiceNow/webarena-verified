"""Simple logging helper utilities."""

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class LoggingHelper:
    """Simple logging helper with reusable display primitives."""

    def print_panel(self, title: str, info: dict[str, Any] | None = None) -> None:
        """
        Print a panel with title and optional key-value information.

        Args:
            title: Panel title
            info: Optional dictionary of key-value pairs to display
        """
        print(f"\n{'=' * 60}")
        print(f"{title}")
        print(f"{'=' * 60}")
        if info:
            for key, value in info.items():
                print(f"{key}: {value}")
            print(f"{'=' * 60}")

    def print_table(self, rows: list[dict[str, Any]]) -> None:
        """
        Print a table from a list of dictionaries with the same keys.

        Args:
            rows: List of dictionaries with same keys
        """
        if not rows:
            print("No data to display")
            return

        # Get column names from first row
        columns = list(rows[0].keys())

        # Calculate column widths
        widths = {col: len(str(col)) for col in columns}
        for row in rows:
            for col in columns:
                widths[col] = max(widths[col], len(str(row.get(col, ""))))

        # Print header
        header = " | ".join(str(col).ljust(widths[col]) for col in columns)
        print(f"\n{header}")
        print("-" * len(header))

        # Print rows
        for row in rows:
            row_str = " | ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)
            print(row_str)
        print()

    def print_progress(self, current: int, total: int, message: str = "") -> None:
        """
        Print a simple progress update that updates in place.

        Args:
            current: Current progress count
            total: Total count
            message: Optional message to display
        """
        progress_str = f"Progress: {current}/{total}"
        if message:
            progress_str += f" - {message}"
        print(f"\r{progress_str}", end="", flush=True)
        # Print newline when complete
        if current >= total:
            print()


@contextmanager
def file_logging_context(logger_name: str, log_file_path: Path):
    """
    Context manager for temporary file logging.

    Args:
        logger_name: Name of the logger to add file handler to
        log_file_path: Path to write logs to

    Yields:
        The file handler instance
    """
    logger = logging.getLogger(logger_name)
    file_handler = logging.FileHandler(log_file_path, mode="w")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    try:
        yield file_handler
    finally:
        logger.removeHandler(file_handler)
        file_handler.close()
