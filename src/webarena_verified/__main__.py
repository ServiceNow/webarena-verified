"""Main CLI entry point for webarena-verified package."""

import argparse
import contextlib
import datetime
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

from webarena_verified.api.internal.subsets_manager import SubsetsManager
from webarena_verified.api.webarena_verified import WebArenaVerified
from webarena_verified.core.utils import logger
from webarena_verified.core.utils.checksum import compute_data_file_checksum
from webarena_verified.core.utils.immutable_obj_helper import serialize_to_json
from webarena_verified.core.utils.logging import (
    file_logging_context,
    logging_helper,
    setup_webarena_verified_logging,
)
from webarena_verified.core.utils.trim_network_logs import trim_har_file
from webarena_verified.types.agent_response import MainObjectiveType
from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.eval import EvalStatus, TaskEvalResult, TasksEvalResults, TransformedAgentResponse
from webarena_verified.types.task import WebArenaSite
from webarena_verified.utils import (
    get_agent_response_file_path,
    get_eval_result_file_path,
    get_trace_file_path,
)


def create_parser():
    """Create the argument parser for the CLI"""
    parser = argparse.ArgumentParser(
        prog="webarena-verified",
        description="WebArena Verified CLI for running and evaluating tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # eval-tasks subcommand (batch evaluation with filtering)
    eval_tasks_parser = subparsers.add_parser(
        "eval-tasks",
        help="Evaluate multiple tasks with optional filtering",
        description="Evaluate multiple tasks from output directory with optional filtering",
        epilog=textwrap.dedent("""
            examples:
              # Evaluate specific tasks
              webarena-verified eval-tasks --task-ids 1,2,3 --output-dir output

              # Evaluate all completed tasks
              webarena-verified eval-tasks --output-dir output

              # Filter by site
              webarena-verified eval-tasks --sites shopping --output-dir output

              # Filter by task type/operation
              webarena-verified eval-tasks --task-type mutate --output-dir output

              # Filter by template ID
              webarena-verified eval-tasks --template-id 5 --output-dir output

              # Combine filters (shopping tasks with mutate task type)
              webarena-verified eval-tasks --sites shopping --task-type mutate --output-dir output

              # Dry run to see what would be evaluated
              webarena-verified eval-tasks --sites reddit --dry-run --output-dir output

              # Transform agent responses before evaluation
              webarena-verified eval-tasks --output-dir output --agent-response-transform examples/evaluation/extract_agent_response.py

            transform script contract:
              The transform script receives the agent response file path as the first argument
              and must output the transformed JSON to stdout. Exit code 0 indicates success.
              The script will be called once per task during batch evaluation.

              See examples/evaluation/extract_agent_response.py for a complete example script.
            """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    eval_tasks_parser.add_argument(
        "--output-dir", type=str, required=True, help="Output directory containing task run logs"
    )
    eval_tasks_parser.add_argument("--config", type=str, default=None, help="Path to config file")
    eval_tasks_parser.add_argument("--task-ids", type=str, help="Comma-separated task IDs to evaluate")
    eval_tasks_parser.add_argument(
        "--sites", type=str, help="Comma-separated site names to filter tasks (shopping, reddit, gitlab, etc.)"
    )
    eval_tasks_parser.add_argument(
        "--task-type", type=str, help="Task type/operation to filter tasks (retrieve, mutate, navigate)"
    )
    eval_tasks_parser.add_argument("--template-id", type=int, help="Template ID to filter tasks")
    eval_tasks_parser.add_argument(
        "--dry-run", action="store_true", help="Show which tasks would be evaluated without running evaluation"
    )
    eval_tasks_parser.add_argument(
        "--agent-response-transform",
        type=str,
        default=None,
        help="Path to executable script that transforms agent response (receives file path, outputs JSON to stdout)",
    )

    # subset-export subcommand
    subset_export_parser = subparsers.add_parser(
        "subset-export",
        help="Export subset tasks to JSON file",
        description="Export tasks from a subset to a JSON file",
        epilog=textwrap.dedent("""
            examples:
              # Export subset by name
              webarena-verified subset-export --name shopping_tasks --output shopping.json

              # Export subset by path
              webarena-verified subset-export --path /custom/subset.json --output custom.json
            """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subset_export_parser.add_argument("--name", type=str, help="Name of the subset (filename without .json)")
    subset_export_parser.add_argument("--path", type=str, help="Path to subset file")
    subset_export_parser.add_argument("--output", type=str, required=True, help="Output file path")
    subset_export_parser.add_argument("--config", type=str, default=None, help="Path to config file")

    # subsets-ls subcommand
    subparsers.add_parser(
        "subsets-ls",
        help="List available subsets",
        description="List all available subsets in the subsets directory",
        epilog=textwrap.dedent("""
            examples:
              # List all subsets
              webarena-verified subsets-ls
            """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # subset-recompute-checksum subcommand
    subset_recompute_parser = subparsers.add_parser(
        "subset-recompute-checksum",
        help="Recompute and update checksum for a subset",
        description="Recompute checksum for a subset and update the file",
        epilog=textwrap.dedent("""
            examples:
              # Recompute checksum for subset by name
              webarena-verified subset-recompute-checksum --name shopping_tasks

              # Recompute checksum for subset by path
              webarena-verified subset-recompute-checksum --path /custom/subset.json
            """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subset_recompute_parser.add_argument("--name", type=str, help="Name of the subset (filename without .json)")
    subset_recompute_parser.add_argument("--path", type=str, help="Path to subset file")

    # subsets-create subcommand
    subsets_create_parser = subparsers.add_parser(
        "subsets-create",
        help="Create new subset from source file",
        description="Create a new subset from a source JSON file",
        epilog=textwrap.dedent("""
            examples:
              # Create subset from full dataset
              webarena-verified subsets-create --src assets/dataset/webarena-verified.json --name full_dataset --desc "Complete dataset"

              # Create subset from custom tasks file
              webarena-verified subsets-create --src custom_tasks.json --name custom
            """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subsets_create_parser.add_argument("--src", type=str, required=True, help="Source JSON file path")
    subsets_create_parser.add_argument("--name", type=str, required=True, help="Name for the new subset")
    subsets_create_parser.add_argument("--desc", type=str, help="Optional description for the subset")

    # dataset-get subcommand
    dataset_get_parser = subparsers.add_parser(
        "dataset-get",
        help="Get tasks from dataset with optional filtering",
        description="Retrieve tasks from the dataset with optional filtering and field selection",
        epilog=textwrap.dedent("""
            examples:
              # Get all tasks
              webarena-verified dataset-get

              # Get specific tasks by ID
              webarena-verified dataset-get --task-ids 1,2,3

              # Filter by single site (exact match)
              webarena-verified dataset-get --sites shopping

              # Filter by multi-site (exact match on tasks with both sites)
              webarena-verified dataset-get --sites shopping,gitlab

              # Filter by task type
              webarena-verified dataset-get --task-type RETRIEVE

              # Filter by template ID
              webarena-verified dataset-get --template-id 5

              # Select specific output fields
              webarena-verified dataset-get --fields task_id,intent,sites

              # Write to file
              webarena-verified dataset-get --sites shopping --output tasks.json
            """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    dataset_get_parser.add_argument("--task-ids", type=str, help="Comma-separated task IDs to retrieve")
    dataset_get_parser.add_argument(
        "--sites",
        type=str,
        help="Site filter (e.g., 'shopping' for single site, 'shopping,gitlab' for multi-site exact match)",
    )
    dataset_get_parser.add_argument("--task-type", type=str, help="Task type filter (RETRIEVE, MUTATE, NAVIGATE)")
    dataset_get_parser.add_argument("--template-id", type=int, help="Template ID to filter tasks")
    dataset_get_parser.add_argument("--fields", type=str, help="Comma-separated field names to include in output")
    dataset_get_parser.add_argument("--output", type=str, help="Output JSON file path (defaults to stdout)")

    # agent-input-get subcommand
    agent_input_get_parser = subparsers.add_parser(
        "agent-input-get",
        help="Get agent input data from tasks",
        description="Export agent input fields (task_id, intent_template_id, sites, start_urls, intent)",
        epilog=textwrap.dedent("""
            examples:
              # Get all tasks (template URLs)
              webarena-verified agent-input-get

              # Get specific tasks with rendered URLs
              webarena-verified agent-input-get --task-ids 1,2,3 --config config.json

              # Filter by site with rendered URLs
              webarena-verified agent-input-get --sites shopping --config config.json

              # Filter by task type
              webarena-verified agent-input-get --task-type RETRIEVE

              # Write to file
              webarena-verified agent-input-get --sites shopping --output agent_inputs.json
            """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    agent_input_get_parser.add_argument("--task-ids", type=str, help="Comma-separated task IDs")
    agent_input_get_parser.add_argument("--sites", type=str, help="Site filter")
    agent_input_get_parser.add_argument("--task-type", type=str, help="Task type filter")
    agent_input_get_parser.add_argument("--template-id", type=int, help="Template ID filter")
    agent_input_get_parser.add_argument("--config", type=str, help="Config file for URL rendering")
    agent_input_get_parser.add_argument("--output", type=str, help="Output JSON file path")

    # create-submission-pkg subcommand
    submission_tar_parser = subparsers.add_parser(
        "create-submission-pkg",
        help="Create submission package from task outputs",
        description="Package agent responses and trimmed network traces into a tar archive or folder",
        epilog=textwrap.dedent("""
            examples:
              # Create submission from single directory
              webarena-verified create-submission-pkg --run-output-dir ./output --output ./submissions

              # Use glob pattern to match multiple directories
              webarena-verified create-submission-pkg --run-output-dir "./runs/run_*" --output ./submissions

              # Mix explicit paths and glob patterns
              webarena-verified create-submission-pkg --run-output-dir ./special "./runs/run_*" --output ./submissions

              # Output as folder instead of tar
              webarena-verified create-submission-pkg --run-output-dir ./output --output ./submissions --no-tar

              # Use custom name instead of auto-generated timestamp
              webarena-verified create-submission-pkg --run-output-dir ./output --output ./submissions --name experiment-001

            Output naming:
              - Default (auto-generated): webarena-verified-submission-YYYYMMDD_HHMMSS.tar.gz
              - Custom name: {custom-name}.tar.gz (or {custom-name}/ for folder mode)
            """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    submission_tar_parser.add_argument(
        "--run-output-dir",
        type=str,
        nargs="+",
        required=True,
        help="One or more run output directories (supports glob patterns like './runs/run_*')",
    )
    submission_tar_parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output root directory (submission created inside with timestamp)",
    )
    submission_tar_parser.add_argument(
        "--no-tar",
        action="store_true",
        help="Skip tar creation, output as folder instead",
    )
    submission_tar_parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Custom name for submission package (if not provided, auto-generates timestamp-based name)",
    )

    # trim-network-logs subcommand
    trim_logs_parser = subparsers.add_parser(
        "trim-network-logs",
        help="Trim network log files by removing skipped resource types",
        description="Reduce HAR file sizes by removing entries for static resources (CSS, JS, images, fonts)",
        epilog=textwrap.dedent("""
            examples:
              # Trim a single HAR file
              webarena-verified trim-network-logs --input logs/task_123.har --output logs/task_123_trimmed.har

              # Trim in place (overwrites original)
              webarena-verified trim-network-logs --input logs/task_123.har --output logs/task_123.har
            """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    trim_logs_parser.add_argument("--input", type=str, required=True, help="Input HAR file path")
    trim_logs_parser.add_argument("--output", type=str, required=True, help="Output HAR file path")

    return parser


def _discover_completed_tasks(output_dir: Path, config) -> tuple[list[int], list[int]]:
    """Discover all completed tasks in output directory.

    Args:
        output_dir: Directory containing task subdirectories
        config: WebArenaVerifiedConfig instance with file names

    Returns:
        Tuple of (completed_task_ids, skipped_task_ids)
    """
    logger.info(f"Discovering completed tasks in {output_dir}")

    if not output_dir.exists():
        logger.warning(f"Output directory does not exist: {output_dir}")
        return [], []

    task_ids = []
    skipped_task_ids = []
    for task_dir in output_dir.iterdir():
        if task_dir.is_dir() and task_dir.name.isdigit():
            task_id = int(task_dir.name)
            try:
                # Check if required output files exist
                get_agent_response_file_path(task_dir, task_id, name=config.agent_response_file_name, ensure=True)
                get_trace_file_path(task_dir, task_id, name=config.trace_file_name, ensure=True)

                task_ids.append(task_id)
            except Exception as e:
                logger.warning(f"Skipping invalid task directory {task_dir}: {e}")
                skipped_task_ids.append(task_id)
    logger.info(
        f"Discovered {len(task_ids)} completed tasks: {task_ids}. Skipped {len(skipped_task_ids)} invalid tasks: {skipped_task_ids}"
    )
    return task_ids, skipped_task_ids


def _filter_tasks_by_metadata(
    task_ids: list[int],
    wa: WebArenaVerified,
    sites: list[str] | None = None,
    task_type: str | None = None,
    template_id: int | None = None,
) -> list[int]:
    """Filter task IDs by metadata criteria.

    Args:
        task_ids: List of task IDs to filter
        wa: WebArenaVerified instance
        sites: List of site names to filter by
        task_type: Task type to filter by (retrieve, mutate, navigate)
        template_id: Template ID to filter by

    Returns:
        List of task IDs matching all filter criteria
    """
    # If no filters provided, return all task IDs
    if not any([sites, task_type, template_id is not None]):
        return task_ids

    # Parse filters
    site_filters = None
    if sites:
        try:
            site_filters = [WebArenaSite(s.strip().lower()) for s in sites]
        except ValueError as e:
            valid_sites = ", ".join(s.value for s in WebArenaSite)
            raise ValueError(f"Invalid site name: {e}. Valid sites: {valid_sites}") from e

    action_filter = None
    if task_type:
        try:
            action_filter = MainObjectiveType(task_type.strip().upper())
        except ValueError as e:
            valid_task_types = ", ".join(a.value for a in MainObjectiveType)
            raise ValueError(f"Invalid task type: {e}. Valid task types: {valid_task_types}") from e

    # Use public API
    filtered_tasks = wa.get_tasks(
        sites=site_filters,
        template_id=template_id,
        action=action_filter,
    )

    # Get task IDs that match filters AND are in the provided task_ids list
    filtered_task_ids = [task.task_id for task in filtered_tasks if task.task_id in task_ids]

    logger.info(f"Filtered {len(task_ids)} tasks to {len(filtered_task_ids)} tasks based on criteria")
    return filtered_task_ids


def _resolve_config(
    config_arg: Path | str | None,
    output_dir: Path,
    task_id: int | None = None,
) -> WebArenaVerifiedConfig:
    """Resolve config with fallback chain.

    Priority order:
    1. Explicit --config argument (if provided)
    2. task_dir/run_config.json (if task_id is provided and file exists)
    3. Default config

    Args:
        config_arg: Config path from --config CLI argument
        output_dir: Base output directory
        task_id: Optional task ID to look for run_config.json

    Returns:
        WebArenaVerifiedConfig instance
    """
    # Priority 1: Explicit --config argument
    if config_arg is not None:
        config_path = Path(config_arg)
        logger.info(f"Using config from --config: {config_path}")
        return WebArenaVerifiedConfig.from_file(config_path)

    # Priority 2: task_dir/run_config.json (if task_id provided)
    if task_id is not None:
        run_config_path = output_dir / str(task_id) / "run_config.json"
        if run_config_path.exists():
            logger.info(f"Using config from task directory: {run_config_path}")
            return WebArenaVerifiedConfig.from_file(run_config_path)

    # Priority 3: Default config
    logger.info("No config provided, using default config")
    return WebArenaVerifiedConfig()


def _create_evaluator(config: WebArenaVerifiedConfig):
    """Create WebArenaVerified instance."""
    return WebArenaVerified(config=config)


def _timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.datetime.now(datetime.UTC).isoformat()


def _load_task_log_files(task_id: int, output_dir: Path, config: WebArenaVerifiedConfig) -> tuple[Path, Path]:
    """Get agent response and trace file paths for a task.

    Args:
        task_id: Task ID
        output_dir: Base output directory
        config: Config with file names

    Returns:
        Tuple of (agent_response_file_path, trace_file_path)

    Raises:
        FileNotFoundError: If required files don't exist
    """
    task_log_dir = output_dir / str(task_id)

    if not task_log_dir.exists():
        raise FileNotFoundError(f"Task directory does not exist: {task_log_dir}")

    agent_response_file = get_agent_response_file_path(
        task_log_dir,
        task_id,
        name=config.agent_response_file_name,
        ensure=True,
    )
    trace_file = get_trace_file_path(
        task_log_dir,
        task_id,
        name=config.trace_file_name,
        ensure=True,
    )

    return agent_response_file, trace_file


def _save_eval_result(result: TaskEvalResult, task_id: int, output_dir: Path, config: WebArenaVerifiedConfig) -> Path:
    """Save evaluation result to JSON file.

    Args:
        result: TaskEvalResult to save
        task_id: Task ID
        output_dir: Base output directory
        config: Config with file names

    Returns:
        Path to saved result file
    """
    task_log_dir = output_dir / str(task_id)
    eval_result_file = get_eval_result_file_path(
        task_log_dir,
        task_id,
        name=config.eval_result_file_name,
    )
    eval_result_file.write_text(serialize_to_json(result.model_dump(mode="json", exclude_none=True), indent=2))
    logger.info(f"Saved evaluation result to {eval_result_file}")
    return eval_result_file


def _print_task_header(task_id: int, task_log_dir: Path):
    """Print header for single task evaluation."""
    header_info = {
        "Command": "Single Task Evaluation",
        "Task ID": task_id,
        "Task Directory": str(task_log_dir),
    }
    logging_helper.print_panel("Evaluating Task", header_info)


def _print_task_footer(result, log_file: Path, result_file: Path):
    """Print footer for single task evaluation."""

    footer_info = {
        "Status": result.status.value,
        "Score": f"{result.score:.2f}",
        "Log File": str(log_file),
        "Result File": str(result_file),
    }
    logging_helper.print_panel("Evaluation Complete", footer_info)


def _print_batch_header(task_ids: list[int]):
    """Print header for batch evaluation."""
    header_info = {
        "Command": "Batch Task Evaluation",
        "Total Tasks": len(task_ids),
    }
    if len(task_ids) < 10:
        header_info["Task IDs"] = ", ".join(str(tid) for tid in sorted(task_ids))

    logging_helper.print_panel("Evaluating Tasks", header_info)


def _print_batch_footer(results_file: Path):
    """Print footer for batch evaluation."""
    footer_info = {
        "Results File": str(results_file),
    }
    logging_helper.print_panel("Evaluation Complete", footer_info)


def _print_error_tasks(error_task_ids: list[int]):
    """Print error tasks summary."""
    if not error_task_ids:
        return

    error_info = {
        "Task IDs": ", ".join(str(tid) for tid in sorted(error_task_ids)),
        "Total": len(error_task_ids),
    }
    logging_helper.print_panel("Tasks with Errors", error_info)


def _print_permission_error_tasks(permission_error_task_ids: list[int]):
    """Print permission error tasks summary."""
    if not permission_error_task_ids:
        return

    permission_error_info = {
        "Message": "Potential test env issue (failed login)",
        "Task IDs": ", ".join(str(tid) for tid in sorted(permission_error_task_ids)),
        "Total": len(permission_error_task_ids),
    }
    logging_helper.print_panel("Permission Denied Tasks", permission_error_info)


def _print_skipped_tasks(skipped_task_ids: list[int]):
    """Print skipped tasks summary."""
    if not skipped_task_ids:
        return

    skipped_info = {
        "Message": "Missing required files (agent_response or trace)",
        "Task IDs": ", ".join(str(tid) for tid in sorted(skipped_task_ids)),
        "Total": len(skipped_task_ids),
    }
    logging_helper.print_panel("Skipped Task Directories", skipped_info)


def _print_transformed_tasks(transformed_task_ids: list[int]):
    """Print transformed tasks summary."""
    if not transformed_task_ids:
        return

    transformed_info = {
        "Message": "Agent response was transformed (original content differs from extracted JSON)",
        "Task IDs": ", ".join(str(tid) for tid in sorted(transformed_task_ids)),
        "Total": len(transformed_task_ids),
    }
    logging_helper.print_panel("Transformed Tasks", transformed_info)


def _check_permission_error(agent_response: Any) -> bool:
    """Check if agent response has PERMISSION_DENIED_ERROR status.

    Args:
        agent_response_file: Path to agent response JSON file

    Returns:
        True if agent response status is PERMISSION_DENIED_ERROR, False otherwise
    """
    if not agent_response or (isinstance(agent_response, Path) and not agent_response.exists()):
        return False

    # Handle the case where the response is is not valid JSON and valid one (best effort)
    # This information is just used for debugging potential test environment issues
    with contextlib.suppress(Exception):
        _content = agent_response.read_text() if isinstance(agent_response, Path) else agent_response
        values = [
            "permission_denied",
            "permission denied",
            "access denied",
            "permission_denied_error",
            "permission denied error",
        ]
        if any(v in _content.lower() for v in values):
            return True

    return False


def _transform_agent_response(script_path: Path, agent_response_file: Path) -> TransformedAgentResponse | None:
    """Transform agent response using external script.

    The script receives the agent response file path as an argument and must output
    the transformed JSON to stdout. Exit code 0 indicates success.

    See examples/evaluation/extract_agent_response.py for a complete example script
    that extracts JSON from agent responses containing markdown formatting or extra text.

    Args:
        script_path: Path to transform script (must be executable)
        agent_response_file: Path to agent response JSON file

    Returns:
        Transformed JSON string from script's stdout

    Raises:
        subprocess.CalledProcessError: If script fails or returns non-zero exit code
    """
    logger.info(f"Transforming agent response using script: {script_path}")

    # Validate script before execution
    if not script_path.exists():
        raise FileNotFoundError(f"Transform script not found: {script_path}")

    if not os.access(script_path, os.X_OK):
        raise PermissionError(f"Transform script is not executable: {script_path}")

    # Read original content
    original_content_raw = agent_response_file.read_text()
    original_content = original_content_raw

    # Normalize original content for comparison
    with contextlib.suppress(json.JSONDecodeError):
        parsed = json.loads(original_content_raw)
        original_content = json.dumps(parsed, sort_keys=True)

    if not original_content_raw.strip():
        logger.warning("Original agent response is empty. Skipping transform.")
        return None

    try:
        result = subprocess.run(
            [str(script_path), str(agent_response_file)],
            capture_output=True,
            text=True,
            check=True,
        )
        transformed_content = result.stdout

        if not transformed_content.strip():
            logger.warning("Transform script produced empty output. Using original agent response as is.")
            return None

        # Compare original and transformed content
        transformed_content_dict = None
        with contextlib.suppress(json.JSONDecodeError):
            transformed_content_dict = json.loads(transformed_content)
            transformed_content = json.dumps(transformed_content_dict, sort_keys=True)

        if not isinstance(transformed_content_dict, dict):
            logger.warning("Transformed content is not a valid JSON object. Using original agent response as is.")
            return None

        if transformed_content != original_content:
            return TransformedAgentResponse.create(
                original_response=original_content_raw, transformed_response=transformed_content_dict
            )

    except Exception as e:
        logger.error(f"Transform script execution failed. Using original agent response as is: {e}")

    return None


def _resolve_task_ids(
    args, output_dir: Path, config: WebArenaVerifiedConfig, wa: WebArenaVerified
) -> tuple[list[int], list[int]]:
    """Resolve which task IDs to evaluate based on args.

    Combines task ID specification, discovery, and filtering.

    Args:
        args: Parsed command line arguments
        output_dir: Output directory
        config: Config instance
        wa: WebArenaVerified instance

    Returns:
        Tuple of (task_ids_to_evaluate, skipped_task_ids)
    """
    # Determine initial task IDs
    skipped_task_ids = []
    if args.task_ids:
        task_ids = [int(tid.strip()) for tid in args.task_ids.split(",")]
        logger.info(f"Specified tasks: {task_ids}")
    else:
        task_ids, skipped_task_ids = _discover_completed_tasks(output_dir, config)

    # Apply metadata filters if provided
    sites_list = [s.strip() for s in args.sites.split(",")] if args.sites else None
    filtered_task_ids = _filter_tasks_by_metadata(
        task_ids=task_ids,
        wa=wa,
        sites=sites_list,
        task_type=args.task_type,
        template_id=args.template_id,
    )

    return filtered_task_ids, skipped_task_ids


def eval_tasks(args):
    """Execute eval-tasks command (batch evaluation)"""
    output_dir = Path(args.output_dir)

    # Resolve initial config for task discovery (without task_id)
    task_config = _resolve_config(args.config, output_dir)
    wa = _create_evaluator(task_config)

    # Resolve task IDs (discover + filter)
    task_ids, skipped_task_ids = _resolve_task_ids(args, output_dir, task_config, wa)

    # Handle dry-run mode
    if args.dry_run:
        logger.info("DRY RUN MODE - No evaluation will be performed")
        logger.info(f"Would evaluate {len(task_ids)} tasks: {sorted(task_ids)}")
        return 0

    # Print header and setup logging
    _print_batch_header(task_ids)
    log_file = output_dir / "eval_log.txt"

    # Evaluate each task
    results = []
    error_task_ids = []
    permission_error_task_ids = []
    transformed_task_ids = []
    with file_logging_context("WebArena-Verified", log_file):
        for idx, task_id in enumerate(task_ids, 1):
            try:
                # Resolve config for this specific task (may load run_config.json)
                # Note: Task logs can come from different runs that have different URLs,
                # so we resolve config per-task to match the run that produced the logs
                task_config = _resolve_config(args.config, output_dir, task_id)
                task_wa = _create_evaluator(task_config)

                # Load files
                original_agent_response_file, trace_file = _load_task_log_files(task_id, output_dir, task_config)

                # Transform agent response if script provided
                agent_response = original_agent_response_file

                # Check for permission errors
                if _check_permission_error(agent_response):
                    permission_error_task_ids.append(task_id)
                if args.agent_response_transform and (
                    transformed_agent_response := _transform_agent_response(
                        Path(args.agent_response_transform), original_agent_response_file
                    )
                ):
                    agent_response = transformed_agent_response
                    transformed_task_ids.append(task_id)

                # Evaluate
                result = task_wa.evaluate_task(
                    task_id=task_id,
                    agent_response=agent_response,
                    network_trace=trace_file,
                )

                _save_eval_result(result, task_id, output_dir, task_config)
                results.append(result)

                # Track tasks with ERROR status
                if result.status == EvalStatus.ERROR:
                    error_task_ids.append(task_id)

                print(f"\n{'─' * 60}")
                logging_helper.print_progress(idx, len(task_ids), f"Task {task_id}")
                print()

            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}", exc_info=True)
                error_task_ids.append(task_id)
                # Continue with next task

    # Create TasksEvalResults and save to file
    data_checksum = compute_data_file_checksum(task_config.test_data_file)
    tasks_eval_results = TasksEvalResults.create(task_results=results, data_checksum=data_checksum)

    # Save results to file (skip when task-ids is specified since it's a partial evaluation)
    if args.task_ids:
        logger.warning("Skipping eval_results.json (partial evaluation with --task-ids)")
        results_file = None
    else:
        results_file = output_dir / "eval_results.json"
        results_file.write_text(
            serialize_to_json(
                tasks_eval_results.model_dump(mode="json", exclude_none=True, exclude={"task_results"}), indent=2
            )
        )

    # Print summary banner and output JSON to stdout (exclude detailed task_results)
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60 + "\n")
    print(
        serialize_to_json(
            tasks_eval_results.model_dump(mode="json", exclude_none=True, exclude={"task_results"}), indent=2
        )
    )

    # Print error tasks if any
    _print_error_tasks(error_task_ids)

    # Print permission error tasks if any
    _print_permission_error_tasks(permission_error_task_ids)

    # Print skipped tasks if any
    _print_skipped_tasks(skipped_task_ids)

    # Print transformed tasks if any (only when transform script was used)
    if args.agent_response_transform:
        _print_transformed_tasks(transformed_task_ids)

    # Print footer
    if results_file:
        _print_batch_footer(results_file)

    return 0


def subset_export(args):
    """Execute subset-export command"""
    try:
        # For subset export, we don't have task-specific configs
        # Use a dummy output dir since we're just loading a general config
        config = _resolve_config(args.config, Path("."), task_id=None)
        manager = SubsetsManager(config)
        subset_path = manager.get_subset_path(name=args.name, path=args.path)

        logger.info(f"Loading subset from: {subset_path}")
        task_count = manager.export_subset(subset_path, Path(args.output))
        logger.info(f"Exported {task_count} tasks to {args.output}")

        return 0
    except Exception as e:
        logger.error(f"Failed to export subset: {e}")
        return 1


def subsets_ls(args):
    """Execute subsets-ls command"""
    try:
        manager = SubsetsManager()
        subsets = manager.list_subsets()

        if not subsets:
            logger.info("No subsets found")
            return 0

        logger.info(f"Found {len(subsets)} subset(s):\n")

        for subset_info in subsets:
            logger.info(f"  {subset_info['name']}")
            if subset_info["error"]:
                logger.warning(f"    Error: {subset_info['error']}")
            else:
                logger.info(f"    Description: {subset_info['description']}")
                logger.info(f"    Tasks: {subset_info['task_count']}")
                logger.info(f"    Path: {subset_info['path']}")
            logger.info("")

        return 0
    except Exception as e:
        logger.error(f"Failed to list subsets: {e}")
        return 1


def subset_recompute_checksum(args):
    """Execute subset-recompute-checksum command"""
    try:
        manager = SubsetsManager()
        subset_path = manager.get_subset_path(name=args.name, path=args.path)

        logger.info(f"Loading subset from: {subset_path}")
        info = manager.recompute_checksum(subset_path)

        if info["had_uncommitted_changes"]:
            logger.warning(f"Warning: {subset_path} has uncommitted changes")

        logger.info("Checksum updated:")
        logger.info(f"  Old: {info['old_checksum']}")
        logger.info(f"  New: {info['new_checksum']}")
        logger.info(f"  File: {info['file_path']}")

        return 0
    except Exception as e:
        logger.error(f"Failed to recompute checksum: {e}")
        return 1


def subsets_create(args):
    """Execute subsets-create command"""
    try:
        manager = SubsetsManager()

        logger.info(f"Loading tasks from: {args.src}")
        info = manager.create_subset(Path(args.src), args.name, args.desc)

        logger.info(f"Created subset '{info['name']}':")
        logger.info(f"  Tasks: {info['task_count']}")
        logger.info(f"  Description: {info['description'] or '(none)'}")
        logger.info(f"  File: {info['file_path']}")

        return 0
    except Exception as e:
        logger.error(f"Failed to create subset: {e}")
        return 1


def _get_filtered_tasks(
    task_ids: str | None = None,
    sites: str | None = None,
    task_type: str | None = None,
    template_id: int | None = None,
    fields: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Get tasks with optional filtering and field selection.

    Args:
        task_ids: Comma-separated task IDs to retrieve
        sites: Comma-separated site names
        task_type: Task type filter (RETRIEVE, MUTATE, NAVIGATE)
        template_id: Template ID filter
        fields: Set of field names to include in output (if None, include all fields)

    Returns:
        List of task dicts with selected fields

    Raises:
        ValueError: If invalid task IDs, sites, or task types are provided
    """
    wa = WebArenaVerified()
    tasks = []

    # Get tasks by ID if specified
    if task_ids:
        try:
            task_id_list = [int(tid.strip()) for tid in task_ids.split(",")]
        except ValueError as e:
            raise ValueError(f"Invalid task ID(s) in --task-ids: {task_ids}. All task IDs must be integers.") from e

        for task_id in task_id_list:
            tasks.append(wa.get_task(task_id))
    else:
        # Parse sites filter
        sites_filter: list[WebArenaSite] | None = None
        if sites:
            try:
                sites_filter = [WebArenaSite(s.strip()) for s in sites.split(",")]
            except ValueError as e:
                raise ValueError(f"Invalid site value in --sites: {e}") from e

        # Parse task type filter
        task_type_filter: MainObjectiveType | None = None
        if task_type:
            try:
                task_type_filter = MainObjectiveType(task_type.strip().upper())
            except ValueError as e:
                valid_types = ", ".join([t.name for t in MainObjectiveType])
                raise ValueError(f"Invalid task type '{task_type}'. Valid options: {valid_types}") from e

        # Use API filtering
        tasks = wa.get_tasks(
            sites=sites_filter,
            template_id=template_id,
            action=task_type_filter,
        )

    # Check if any tasks matched
    if not tasks:
        raise ValueError("No tasks found matching the specified filters")

    # Serialize tasks with optional field filtering
    if fields:
        output_data = [task.model_dump(mode="json", include=fields) for task in tasks]
    else:
        output_data = [task.model_dump(mode="json") for task in tasks]

    return output_data


def dataset_get(args):
    """Execute dataset-get command"""
    # Prepare field set (always include core fields)
    include_fields = None
    if args.fields:
        include_fields = {field.strip() for field in args.fields.split(",")}
        include_fields.update({"task_id", "intent_template_id", "sites"})

    # Get filtered tasks with field selection
    try:
        output_data = _get_filtered_tasks(
            task_ids=args.task_ids,
            sites=args.sites,
            task_type=args.task_type,
            template_id=args.template_id,
            fields=include_fields,
        )
    except ValueError as e:
        logger.error(str(e))
        return 1

    # Serialize and output
    json_output = serialize_to_json(output_data, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_output)
        logger.info(f"Wrote {len(output_data)} tasks to {output_path}")
    else:
        print(json_output)

    return 0


def agent_input_get(args):
    """Execute agent-input-get command"""

    # Load config if provided (for URL rendering)
    config = None
    if args.config:
        try:
            config = WebArenaVerifiedConfig.from_file(Path(args.config))
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            return 1

    # Define agent input fields
    agent_fields = {"task_id", "intent_template_id", "sites", "start_urls", "intent"}

    # Get filtered tasks using shared helper with field selection
    try:
        output_data = _get_filtered_tasks(
            task_ids=args.task_ids,
            sites=args.sites,
            task_type=args.task_type,
            template_id=args.template_id,
            fields=agent_fields,
        )
    except ValueError as e:
        logger.error(str(e))
        return 1

    # Render URLs if config provided
    if config and config.environments:
        for task_dict in output_data:
            sites_enum = [WebArenaSite(s) for s in task_dict["sites"]]
            try:
                # Use strict=False to avoid failures when some URLs don't match templates
                rendered_urls = [config.render_url(url, sites_enum, strict=False) for url in task_dict["start_urls"]]
                task_dict["start_urls"] = rendered_urls
            except ValueError as e:
                logger.warning(f"Failed to render URLs for task {task_dict['task_id']}: {e}. Using template URLs.")

    # Serialize to JSON
    json_output = serialize_to_json(output_data, indent=2)

    # Write to file or stdout
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_output)
        logger.info(f"Wrote {len(output_data)} agent inputs to {output_path}")
    else:
        print(json_output)

    return 0


def trim_network_logs(args):
    """Execute trim-network-logs command"""
    try:
        input_path = Path(args.input)
        output_path = Path(args.output)

        logger.info(f"Trimming network log file: {input_path}")

        # Trim the HAR file
        stats = trim_har_file(input_path, output_path)

        # Log results
        logger.info("Trimming completed successfully:")
        logger.info(f"  Original entries: {stats['original_entries']}")
        logger.info(f"  Trimmed entries: {stats['trimmed_entries']}")
        logger.info(f"  Removed entries: {stats['removed_entries']}")
        logger.info(f"  Original size: {stats['original_size']:,} bytes ({stats['original_size'] / 1024:.1f} KB)")
        logger.info(f"  Trimmed size: {stats['trimmed_size']:,} bytes ({stats['trimmed_size'] / 1024:.1f} KB)")
        logger.info(f"  Size reduction: {stats['reduction_percent']:.1f}%")
        logger.info(f"  Output file: {output_path}")

        return 0
    except Exception as e:
        logger.error(f"Failed to trim network logs: {e}")
        return 1


def create_submission_pkg(args):
    """Execute create-submission-pkg command"""
    import glob

    # Display command info
    command_info = {
        "Command": "create-submission-pkg",
        "Output Root": args.output,
        "Format": "Folder" if args.no_tar else "Tar Archive",
        "Run Output Directories": "\n" + "\n".join(f"  • {path}" for path in args.run_output_dir),
    }
    logging_helper.print_panel("Submission Package Creation", command_info)

    # Expand glob patterns in run_output_dir arguments
    output_dirs: list[Path] = []
    for pattern in args.run_output_dir:
        if any(c in pattern for c in ["*", "?", "["]):
            matches = glob.glob(pattern)
            if not matches:
                logger.warning(f"No directories matched pattern: {pattern}")
            output_dirs.extend(Path(m) for m in sorted(matches) if Path(m).is_dir())
        else:
            output_dirs.append(Path(pattern))

    output_root = Path(args.output)

    wa = WebArenaVerified()

    # Define progress callback
    def show_progress(current: int, total: int, task_id: int) -> None:
        logging_helper.print_progress(current, total, f"Processing task ID {task_id}")

    logger.info("Processing run logs (copying agent response files and trimmed network logs)")

    try:
        result = wa.create_submission(
            output_dirs=output_dirs,
            output_root=output_root,
            no_tar=args.no_tar,
            custom_name=args.name,
            progress_callback=show_progress,
        )
    except ValueError as e:
        logger.error(str(e))
        return 1
    except FileExistsError as e:
        logger.error(str(e))
        return 1

    # Print final newline after progress
    print()
    logger.info("Processing complete")

    # Calculate total valid tasks from all categories
    total_found = (
        len(result.tasks_packaged)
        + len(result.missing_agent_response)
        + len(result.missing_network_har)
        + len(result.missing_both_files)
        + len(result.invalid_har_files)
    )
    total_expected = total_found + len(result.missing_task_ids)

    # Create summary dict with counts only (no lists)
    summary_info = {
        "Output Path": result.output_path,
        "Type": "Tar Archive" if result.is_tar else "Folder",
        "Tasks Packaged": f"{len(result.tasks_packaged)}/{total_expected}",
        "Missing Agent Response": len(result.missing_agent_response),
        "Missing Network HAR": len(result.missing_network_har),
        "Missing Both Files": len(result.missing_both_files),
        "Invalid HAR Files": len(result.invalid_har_files),
        "Empty Agent Response": len(result.empty_agent_response),
        "Duplicate Tasks": len(result.duplicate_task_ids),
        "Unknown Tasks": len(result.unknown_task_ids),
        "Missing from Output": len(result.missing_task_ids),
    }

    if result.archive_size:
        summary_info["Archive Size"] = f"{result.archive_size:,} bytes"

    summary_info["Summary File"] = result.summary_file

    # Display results in a panel
    logging_helper.print_panel("Submission Package Created", summary_info)

    if len(result.tasks_packaged) == 0:
        logger.error("No valid tasks were packaged")
        return 1

    return 0


def main():
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()

    setup_webarena_verified_logging()

    # Route to appropriate command handler
    if args.command == "eval-tasks":
        sys.exit(eval_tasks(args))
    elif args.command == "subset-export":
        sys.exit(subset_export(args))
    elif args.command == "subsets-ls":
        sys.exit(subsets_ls(args))
    elif args.command == "subset-recompute-checksum":
        sys.exit(subset_recompute_checksum(args))
    elif args.command == "subsets-create":
        sys.exit(subsets_create(args))
    elif args.command == "create-submission-pkg":
        sys.exit(create_submission_pkg(args))
    elif args.command == "trim-network-logs":
        sys.exit(trim_network_logs(args))
    elif args.command == "dataset-get":
        sys.exit(dataset_get(args))
    elif args.command == "agent-input-get":
        sys.exit(agent_input_get(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
