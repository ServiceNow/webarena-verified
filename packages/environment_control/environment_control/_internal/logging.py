"""Logging configuration for environment_control package."""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

DEFAULT_LOG_FILE = "/tmp/env-ctrl.log"
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

_configured = False


def configure_logging(
    log_file: Optional[str] = None,
    log_level: Optional[str] = None,
    force: bool = False,
) -> None:
    """Configure logging for the environment_control package.

    This function configures the 'environment_control' logger with file and
    console handlers. It should be called once at application startup.

    Args:
        log_file: Path to log file. Defaults to ENV_CTRL_LOG_FILE env var
                  or /tmp/env-ctrl.log.
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   Defaults to ENV_CTRL_LOG_LEVEL env var or INFO.
        force: If True, reconfigure even if already configured.
    """
    global _configured

    if _configured and not force:
        return

    if log_file is None:
        log_file = os.environ.get("ENV_CTRL_LOG_FILE", DEFAULT_LOG_FILE)

    if log_level is None:
        log_level = os.environ.get("ENV_CTRL_LOG_LEVEL", DEFAULT_LOG_LEVEL)

    # Get the package logger
    logger = logging.getLogger("environment_control")
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT)

    # File handler
    try:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        # Log to stderr if file creation fails
        print(f"Warning: Could not create log file {log_file}: {e}", file=sys.stderr)

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

    _configured = True


# Backwards compatibility aliases
def setup_logging(
    log_file: Optional[str] = None,
    log_level: Optional[str] = None,
) -> logging.Logger:
    """Set up logging configuration (backwards compatible).

    Args:
        log_file: Path to log file.
        log_level: Log level string.

    Returns:
        Configured logger instance.
    """
    configure_logging(log_file=log_file, log_level=log_level)
    return logging.getLogger("environment_control")


def get_logger() -> logging.Logger:
    """Get the package logger (backwards compatible).

    Returns:
        Logger instance.
    """
    return logging.getLogger("environment_control")
