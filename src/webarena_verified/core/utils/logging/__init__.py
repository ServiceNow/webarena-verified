"""Logging utilities for webarena_verified package."""

import logging
import sys

from .logging_helper import LoggingHelper, file_logging_context

# Create global logger and logging helper instances
logger = logging.getLogger("WebArena-Verified")
logging_helper = LoggingHelper()


def setup_webarena_verified_logging(level: int = logging.INFO) -> None:
    """
    Setup logging with a clean format for the webarena_verified package.

    Args:
        level: Logging level (default: INFO)
    """
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Use stdout stream handler to ensure logs are dumped to stdout
    logging_handler = logging.StreamHandler(sys.stdout)
    logging_formatter = logging.Formatter("[WebArena Verified] [%(levelname)s] %(message)s")

    logging_handler.setFormatter(logging_formatter)
    logger.addHandler(logging_handler)
    logger.setLevel(level)
    logger.propagate = False  # Don't propagate to root logger


__all__ = [
    "LoggingHelper",
    "file_logging_context",
    "logger",
    "logging_helper",
    "setup_webarena_verified_logging",
]
