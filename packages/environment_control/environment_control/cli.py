"""Command-line interface for environment control."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional

from ._internal.logging import configure_logging
from .ops import Result, get_ops_class, list_ops
from .ops.types import OpsConfig
from .server.app import run_server

logger = logging.getLogger(__name__)


def _format_result(result: Result, verbose: bool = False) -> str:
    """Format a Result for display.

    Args:
        result: The Result object.
        verbose: If True, show full details as JSON.

    Returns:
        Formatted string for display.
    """
    if verbose:
        return json.dumps(result.to_dict(), indent=2)

    status = "OK" if result.success else "FAILED"
    # Get last error from exec_logs if failed
    error = ""
    if not result.success and result.exec_logs:
        last = result.exec_logs[-1]
        error = f": {last.output}"
    return f"[{status}]{error}"


def cmd_init(args: argparse.Namespace) -> int:
    """Handle the init command."""
    ops = get_ops_class(args.env_type)
    dry_run = getattr(args, "dry_run", False)
    base_url = getattr(args, "base_url", None)
    result = ops.init(base_url=base_url, dry_run=dry_run)
    print(_format_result(result, args.verbose))
    return 0 if result.success else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Handle the status command."""
    ops = get_ops_class(args.env_type)
    result = ops.get_health()
    print(_format_result(result, args.verbose))
    return 0 if result.success else 1


def cmd_start(args: argparse.Namespace) -> int:
    """Handle the start command."""
    ops = get_ops_class(args.env_type)

    if args.wait:
        print("Starting environment and waiting for ready state...")

    config = OpsConfig(timeout_sec=int(args.timeout))
    result = ops.start(wait=args.wait, config=config)
    print(_format_result(result, args.verbose))
    return 0 if result.success else 1


def cmd_stop(args: argparse.Namespace) -> int:
    """Handle the stop command."""
    ops = get_ops_class(args.env_type)
    result = ops.stop()
    print(_format_result(result, args.verbose))
    return 0 if result.success else 1


def cmd_serve(args: argparse.Namespace) -> int:
    """Handle the serve command."""
    run_server(env_type=args.env_type, port=args.port)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Handle the list command."""
    environments = list_ops()
    print("Available environment types:")
    for name in sorted(environments.keys()):
        print(f"  - {name}")
    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="env-ctrl",
        description="Environment control CLI for Docker containers",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show verbose output with full JSON details",
    )

    parser.add_argument(
        "-e",
        "--env-type",
        dest="env_type",
        default=None,
        help="Environment type (default: WA_ENV_CTRL_TYPE env var)",
    )

    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        required=True,
    )

    # init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize the environment",
    )
    init_parser.add_argument(
        "--base-url",
        help="Base URL for the environment",
    )
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )
    init_parser.set_defaults(func=cmd_init)

    # status command
    status_parser = subparsers.add_parser(
        "status",
        help="Get environment status",
    )
    status_parser.set_defaults(func=cmd_status)

    # start command
    start_parser = subparsers.add_parser(
        "start",
        help="Start the environment",
    )
    start_parser.add_argument(
        "-w",
        "--wait",
        action="store_true",
        help="Wait until environment is ready",
    )
    start_parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=60.0,
        help="Timeout for waiting (default: 60s)",
    )
    start_parser.set_defaults(func=cmd_start)

    # stop command
    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop the environment",
    )
    stop_parser.set_defaults(func=cmd_stop)

    # serve command
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the REST API server",
    )
    serve_parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=None,
        help="Port to listen on (default: WA_ENV_CTRL_PORT or 8080)",
    )
    serve_parser.set_defaults(func=cmd_serve)

    # list command
    list_parser = subparsers.add_parser(
        "list",
        help="List available environment types",
    )
    list_parser.set_defaults(func=cmd_list)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command-line arguments. Defaults to sys.argv[1:].

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    configure_logging()

    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        logger.debug("Executing command: %s", args.command)
        return args.func(args)
    except ValueError as e:
        logger.error("Error: %s", e)
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("\nInterrupted", file=sys.stderr)
        return 130
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
