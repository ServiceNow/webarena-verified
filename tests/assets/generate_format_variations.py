#!/usr/bin/env python
"""Generate consolidated test data file with minimized footprint.

This script generates a single JSON file containing all test variations
in a minimized format (just values, no redundant metadata).

OPTIMIZATION: Uses round-robin distribution to spread format variations across tasks
instead of testing ALL variations for EVERY task. This reduces test count from
N variations × T tasks to max(N, T) while maintaining full variation coverage.

Output: tests/assets/e2e_test_retrieved_data.json

Structure:
{
  "task_id": {
    "exact_match": value,
    "valid": {variation_name: value, ...},  # Only ONE format variation per task
    "invalid": {variation_name: value, ...}
  }
}

Usage:
    uv run python tests/assets/generate_format_variations.py
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add src to path to import utilities
sys.path.insert(0, "src")

from webarena_verified.core.utils import is_regexp

# Add tests to path to import utilities
sys.path.insert(0, "tests")

from api.format_variations_utils import (
    ADDRESS_VARIATIONS,
    BOOLEAN_VARIATIONS,
    COORDINATES_VARIATIONS,
    CURRENCY_VARIATIONS,
    DATE_VARIATIONS,
    DISTANCE_OUT_OF_TOLERANCE_VARIATIONS,
    DISTANCE_TOLERANCE_VARIATIONS,
    DISTANCE_VARIATIONS,
    DURATION_OUT_OF_TOLERANCE_VARIATIONS,
    DURATION_TOLERANCE_VARIATIONS,
    DURATION_VARIATIONS,
    LOCATION_NAME_VARIATIONS,
    NUMBER_VARIATIONS,
    STRING_VARIATIONS,
    distribute_variations_round_robin,
    get_coverage_stats,
)

# Map format types to variation lists
# Note: "boolean", "number", "string" are schema item types, not "format" field values
# We need to handle them based on the item type, not the format field
FORMAT_VARIATIONS_MAP = {
    "currency": CURRENCY_VARIATIONS,
    "date": DATE_VARIATIONS,
    "duration": DURATION_VARIATIONS,
    "distance": DISTANCE_VARIATIONS,
    "coordinates": COORDINATES_VARIATIONS,
    "full-address": ADDRESS_VARIATIONS,
    "location-name": LOCATION_NAME_VARIATIONS,
}

# Map schema types (not formats) to variation lists
TYPE_VARIATIONS_MAP = {
    "boolean": BOOLEAN_VARIATIONS,
    "number": NUMBER_VARIATIONS,
    "integer": NUMBER_VARIATIONS,
    "string": STRING_VARIATIONS,
}

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def load_dataset(dataset_path: Path) -> list[dict]:
    """Load and return the main dataset."""
    return json.loads(dataset_path.read_text())


def get_schema_format(task: dict) -> str | None:
    """Extract format type from task's results schema.

    Args:
        task: The task dict from the dataset

    Returns:
        The format type (e.g., "currency", "date") or None if no format
    """
    for eval_config in task.get("eval", []):
        if eval_config["evaluator"] == "AgentResponseEvaluator":
            schema = eval_config.get("results_schema", {})
            # Check if schema has format field (usually in items for arrays)
            if schema.get("type") == "array":
                items = schema.get("items", {})
                return items.get("format")
            # Could also be direct format on schema
            return schema.get("format")
    return None


def get_schema_item_type(task: dict) -> str | None:
    """Extract item type from task's results schema.

    Args:
        task: The task dict from the dataset

    Returns:
        The item type (e.g., "boolean", "number", "string") or None
    """
    for eval_config in task.get("eval", []):
        if eval_config["evaluator"] == "AgentResponseEvaluator":
            schema = eval_config.get("results_schema", {})
            if schema.get("type") == "array":
                items = schema.get("items", {})
                return items.get("type")
            return schema.get("type")
    return None


def get_variations_for_task(task: dict) -> tuple[str | None, list[tuple[str, Any]]]:
    """Get the appropriate variations list for a task based on its schema.

    Checks format field first, then falls back to item type.

    Args:
        task: The task dict from the dataset

    Returns:
        Tuple of (variation_key, variations_list) or (None, []) if no variations apply
    """
    # First check format field
    schema_format = get_schema_format(task)
    if schema_format and schema_format in FORMAT_VARIATIONS_MAP:
        return (schema_format, FORMAT_VARIATIONS_MAP[schema_format])

    # Fall back to item type
    item_type = get_schema_item_type(task)
    if item_type and item_type in TYPE_VARIATIONS_MAP:
        return (item_type, TYPE_VARIATIONS_MAP[item_type])

    return (None, [])


def get_expected_data(task: dict) -> dict | None:
    """Extract expected agent response from task.

    Args:
        task: The task dict from the dataset

    Returns:
        The expected agent response dict or None if not found
    """
    for eval_config in task.get("eval", []):
        if eval_config["evaluator"] == "AgentResponseEvaluator":
            expected = eval_config.get("expected", {})
            # Only return if it's a retrieval task with SUCCESS status
            if expected.get("task_type") == "retrieve" and expected.get("status") == "SUCCESS":
                return expected
    return None


def is_retrieval_task(task: dict) -> bool:
    """Check if task is a retrieval task with SUCCESS status.

    Args:
        task: The task dict from the dataset

    Returns:
        True if task is a retrieval task
    """
    return get_expected_data(task) is not None


def apply_variation_to_data(data: Any, variation_func) -> Any:
    """Apply a format variation function to retrieved_data.

    Recursively handles nested structures (lists, dicts).
    Skips regex patterns (they should not be transformed).

    Args:
        data: The retrieved_data to transform (list, dict, scalar, etc.)
        variation_func: The transformation function to apply

    Returns:
        Transformed data in same structure as input
    """
    if isinstance(data, dict):
        # Transform dict values recursively
        transformed_item = {}
        for key, value in data.items():
            transformed_item[key] = apply_variation_to_data(value, variation_func)
        return transformed_item
    elif isinstance(data, list):
        # Transform list items recursively
        transformed = []
        for item in data:
            transformed.append(apply_variation_to_data(item, variation_func))
        return transformed
    else:
        # Skip regex patterns - they should not be transformed
        if isinstance(data, str) and is_regexp(data):
            return data
        # Transform scalar value
        try:
            return variation_func(data)
        except Exception as e:
            # If transformation fails, keep original
            logger.debug(f"Transformation failed for {data}: {e}")
            return data


def generate_variations_for_task(
    task: dict,
    assigned_variations: list[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate minimized format variations for a task.

    Args:
        task: The task dict from the dataset
        assigned_variations: Optional list of (name, func) tuples to use.
                           If None, uses ALL variations (legacy behavior).
                           If provided, only generates those specific variations.

    Returns:
        Dict mapping variation_name to retrieved_data value (minimized)
    """
    var_key, all_variations = get_variations_for_task(task)
    if not var_key or not all_variations:
        return {}

    expected = get_expected_data(task)
    if not expected:
        return {}

    retrieved_data = expected.get("retrieved_data", [])
    if not retrieved_data:
        logger.debug(f"Task {task['task_id']}: Empty retrieved_data, skipping")
        return {}

    # Use assigned variations if provided, otherwise use all (for backward compat)
    variations_to_apply = assigned_variations if assigned_variations else all_variations

    # Generate minimized variations (just the transformed value, no metadata)
    variations = {}
    for var_name, var_func in variations_to_apply:
        transformed_data = apply_variation_to_data(retrieved_data, var_func)
        variations[f"fmt_{var_name}"] = transformed_data  # Just the value!

    return variations


def main():
    """Main function to generate consolidated format variations file."""
    project_root = Path(__file__).parent.parent.parent  # tests/assets/ -> tests/ -> project root
    dataset_path = project_root / "assets" / "dataset" / "webarena-verified.json"
    output_file = project_root / "tests" / "assets" / "e2e_test_retrieved_data.json"

    logger.info("Loading dataset...")
    tasks = load_dataset(dataset_path)
    logger.info(f"Loaded {len(tasks)} tasks")

    # Load existing consolidated file to preserve special cases
    existing_consolidated: dict[str, Any] = {}
    if output_file.exists():
        try:
            existing_consolidated = json.loads(output_file.read_text())
            logger.info(f"Loaded {len(existing_consolidated)} existing task entries for special case migration")
        except Exception as e:
            logger.warning(f"Failed to load existing consolidated file: {e}")

    # Combine all variation maps for grouping
    all_variations_map = {**FORMAT_VARIATIONS_MAP, **TYPE_VARIATIONS_MAP}

    # Build task lookup and group tasks by variation type for round-robin distribution
    {task["task_id"]: task for task in tasks}
    tasks_by_variation_type: dict[str, list[int]] = {key: [] for key in all_variations_map}

    for task in tasks:
        if not is_retrieval_task(task):
            continue
        var_key, _ = get_variations_for_task(task)
        if var_key and var_key in tasks_by_variation_type:
            tasks_by_variation_type[var_key].append(task["task_id"])

    # Compute round-robin distribution for each variation type
    variation_assignments: dict[int, list[tuple[str, Any]]] = {}
    for var_key, task_ids in tasks_by_variation_type.items():
        if task_ids:
            distribution = distribute_variations_round_robin(task_ids, all_variations_map[var_key])
            variation_assignments.update(distribution)

    # Log distribution statistics
    logger.info("\n" + "=" * 60)
    logger.info("Round-Robin Distribution Statistics:")
    logger.info("=" * 60)
    for var_key, task_ids in tasks_by_variation_type.items():
        if task_ids:
            variations = all_variations_map[var_key]
            stats = get_coverage_stats(task_ids, variations)
            logger.info(f"\n{var_key.upper()} ({len(task_ids)} tasks, {len(variations)} variations):")
            for var_name, count in stats.items():
                logger.info(f"  fmt_{var_name}: {count} tasks")
    logger.info("=" * 60)

    # Consolidated output structure
    consolidated = {}

    # Statistics
    total_tasks = 0
    total_format_variations = 0
    total_special_variations = 0
    total_invalid_variations = 0
    tasks_with_variations: dict[str, int] = dict.fromkeys(all_variations_map, 0)

    # Track old vs new test counts for comparison
    old_format_variations = 0

    logger.info("\nProcessing tasks...")

    for task in tasks:
        task_id = task["task_id"]

        # Skip non-retrieval tasks
        if not is_retrieval_task(task):
            continue

        # Get expected data for exact_match
        expected = get_expected_data(task)
        if not expected:
            continue

        retrieved_data = expected.get("retrieved_data", [])

        # Initialize task entry
        task_entry = {"exact_match": retrieved_data, "valid": {}, "invalid": {}}

        # Generate format variations using round-robin assigned variation
        assigned = variation_assignments.get(task_id)
        format_variations = generate_variations_for_task(task, assigned)
        if format_variations:
            task_entry["valid"].update(format_variations)
            total_format_variations += len(format_variations)

            # Track variation type
            var_key, all_vars = get_variations_for_task(task)
            if var_key and var_key in tasks_with_variations:
                tasks_with_variations[var_key] += 1
                # Calculate what old count would have been
                old_format_variations += len(all_vars)

        # Add tolerance variations for duration and distance formats
        var_key, _ = get_variations_for_task(task)
        if var_key == "duration":
            # Add duration tolerance variations (within tolerance - valid)
            for var_name, var_func in DURATION_TOLERANCE_VARIATIONS:
                transformed_data = apply_variation_to_data(retrieved_data, var_func)
                task_entry["valid"][f"tol_{var_name}"] = transformed_data
                total_format_variations += 1
            # Add duration out-of-tolerance variations (invalid)
            for var_name, var_func in DURATION_OUT_OF_TOLERANCE_VARIATIONS:
                transformed_data = apply_variation_to_data(retrieved_data, var_func)
                task_entry["invalid"][f"tol_{var_name}"] = transformed_data
                total_invalid_variations += 1
        elif var_key == "distance":
            # Add distance tolerance variations (within tolerance - valid)
            for var_name, var_func in DISTANCE_TOLERANCE_VARIATIONS:
                transformed_data = apply_variation_to_data(retrieved_data, var_func)
                task_entry["valid"][f"tol_{var_name}"] = transformed_data
                total_format_variations += 1
            # Add distance out-of-tolerance variations (invalid)
            for var_name, var_func in DISTANCE_OUT_OF_TOLERANCE_VARIATIONS:
                transformed_data = apply_variation_to_data(retrieved_data, var_func)
                task_entry["invalid"][f"tol_{var_name}"] = transformed_data
                total_invalid_variations += 1

        # Migrate special cases from existing consolidated file (if exists)
        # These are manually curated test cases that should be preserved
        if str(task_id) in existing_consolidated:
            existing = existing_consolidated[str(task_id)]

            # Migrate valid special cases (non-format variations)
            for var_name, var_value in existing.get("valid", {}).items():
                if not var_name.startswith("fmt_") and not var_name.startswith("tol_"):
                    task_entry["valid"][var_name] = var_value
                    total_special_variations += 1

            # Migrate invalid special cases
            for var_name, var_value in existing.get("invalid", {}).items():
                if not var_name.startswith("tol_"):
                    task_entry["invalid"][var_name] = var_value
                    total_invalid_variations += 1

        # Only add task if it has variations (beyond just exact_match)
        if task_entry["valid"] or task_entry["invalid"]:
            consolidated[str(task_id)] = task_entry
            total_tasks += 1

    # Write consolidated file
    output_file.write_text(json.dumps(consolidated, indent=2) + "\n")

    # Report results
    logger.info("\n" + "=" * 60)
    logger.info("Summary:")
    logger.info(f"  Consolidated file: {output_file.relative_to(project_root)}")
    logger.info(f"  Total tasks: {total_tasks}")
    logger.info("  Total variations:")
    logger.info(f"    - Format variations: {total_format_variations}")
    logger.info(f"    - Special cases (valid): {total_special_variations}")
    logger.info(f"    - Special cases (invalid): {total_invalid_variations}")
    logger.info(f"    - TOTAL: {total_format_variations + total_special_variations + total_invalid_variations}")

    logger.info("\nVariation optimization by type:")
    for var_key, count in tasks_with_variations.items():
        if count > 0:
            var_count = len(all_variations_map[var_key])
            old_tests = count * var_count
            new_tests = count  # One variation per task
            reduction = (1 - new_tests / old_tests) * 100 if old_tests > 0 else 0
            logger.info(f"  {var_key:15s}: {count:3d} tasks × 1 variation = {count:3d} tests")
            logger.info(
                f"                   (was: {count:3d} tasks × {var_count} variations = {old_tests:3d} tests, -{reduction:.0f}%)"
            )

    if old_format_variations > 0:
        total_reduction = (1 - total_format_variations / old_format_variations) * 100
        logger.info(
            f"\n  TOTAL VARIATION TESTS: {total_format_variations} (was {old_format_variations}, -{total_reduction:.0f}%)"
        )

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
