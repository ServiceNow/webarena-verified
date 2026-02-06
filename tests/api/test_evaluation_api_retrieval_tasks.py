"""Integration tests for the evaluation API focusing on retrieval tasks.

This module tests the end-to-end evaluation flow for RETRIEVE tasks using
preset test data from a consolidated variations file.

Test Structure:
- Loads test variations from tests/assets/e2e_test_retrieved_data.json
- Tests valid variations (expected to pass evaluation)
- Tests invalid variations (expected to fail evaluation)
- Programmatically generates additional test cases (case sensitivity, whitespace, etc.)

Test Data Format:
- All test variations are stored in a single consolidated JSON file with minimized format
- Structure: {task_id: {exact_match: value, valid: {var_name: value}, invalid: {var_name: value}}}
- Format variations (currency, date, duration, distance, boolean, number, string, etc.) are pre-generated
- Special case variations (e.g., URL variations, regex patterns) are also included

Test Optimization:
- Uses round-robin distribution to spread format variations across tasks
- Instead of testing ALL N variations for EVERY T tasks (N*T tests), each task tests only
  ONE variation, reducing test count to T tests while maintaining full variation coverage
- Example: 27 duration tasks x 3 variations = 81 tests -> 27 tests (67% reduction)
- Overall reduction: ~1400 tests -> ~260 tests (84% reduction in format variation tests)
- Regenerate with: uv run python tmp/generate_format_variations.py

Distribution Function:
- Uses distribute_variations_round_robin() from tests/api/format_variations_utils.py
- Each variation type is evenly distributed across tasks of that type
- Ensures all format variations are tested at least once
"""

import copy
import json
import logging
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from webarena_verified import WebArenaVerified
from webarena_verified.core.utils import is_regexp
from webarena_verified.types.eval import EvalStatus

logger = logging.getLogger(__name__)

UNSUPPORTED_RETRIEVAL_VARIATIONS = {
    "fmt_trim_whitespace",
    "fmt_extra_spaces",
    "fmt_with_quotes",
    "fmt_with_period",
    "fmt_tabs_to_spaces",
    "fmt_en_dash",
}


def _load_dataset(project_root: Path) -> MappingProxyType[int, MappingProxyType[str, Any]]:
    """Load the main dataset file as an immutable mapping indexed by task_id.

    Returns:
        Immutable mapping from task_id to task data
    """
    dataset_path = project_root / "assets" / "dataset" / "webarena-verified.json"
    tasks_list = json.loads(dataset_path.read_text())
    assert len(tasks_list) == 812

    # Create immutable mapping indexed by task_id
    tasks_dict = {task["task_id"]: MappingProxyType(task) for task in tasks_list}
    return MappingProxyType(tasks_dict)


def _get_retrieval_task_ids(dataset: MappingProxyType[int, MappingProxyType[str, Any]]) -> list[int]:
    """Extract task IDs for all retrieval tasks from the dataset.

    A task is considered a retrieval task if it has an AgentResponseEvaluator
    with expected.task_type == "retrieve".

    Args:
        dataset: The loaded dataset mapping

    Returns:
        Sorted list of task IDs for retrieval tasks
    """
    retrieval_ids = []
    for task_id, task in dataset.items():
        for eval_config in task["eval"]:
            if eval_config["evaluator"] == "AgentResponseEvaluator":
                expected = eval_config["expected"]
                if expected["task_type"] == "retrieve":
                    retrieval_ids.append(task_id)
                    break
    return sorted(retrieval_ids)


def _get_expected_from_dataset(
    task_id: int, dataset: MappingProxyType[int, MappingProxyType[str, Any]]
) -> dict[str, Any]:
    """Extract the expected agent response from the dataset for a given task ID.

    Args:
        task_id: The task ID to look up
        dataset: The loaded dataset mapping

    Returns:
        The expected agent response dict with task_type, status, and retrieved_data
    """
    if task_id not in dataset:
        raise ValueError(f"Task {task_id} not found in dataset")

    task = dataset[task_id]
    # Find the AgentResponseEvaluator config
    for eval_config in task["eval"]:
        if eval_config["evaluator"] == "AgentResponseEvaluator":
            return eval_config["expected"]

    raise ValueError(f"No AgentResponseEvaluator found for task {task_id}")


def _has_boolean_schema(task_id: int, dataset: MappingProxyType[int, MappingProxyType[str, Any]]) -> bool:
    """Check if a task's results schema is boolean type.

    Args:
        task_id: The task ID to check
        dataset: The loaded dataset mapping

    Returns:
        True if the task has a boolean schema
    """
    if task_id not in dataset:
        return False

    task = dataset[task_id]
    for eval_config in task["eval"]:
        if eval_config["evaluator"] == "AgentResponseEvaluator":
            schema = eval_config.get("results_schema", {})
            # Check if items are boolean type
            if schema.get("type") == "array":
                items = schema.get("items", {})
                if items.get("type") == "boolean":
                    return True
    return False


def _reconstruct_agent_response(retrieved_data: Any) -> dict[str, Any]:
    """Reconstruct full agent response from minimized data.

    The consolidated e2e_test_retrieved_data.json file stores just the retrieved_data
    value to minimize file size. This function reconstructs the full response.

    Args:
        retrieved_data: The minimized value (could be scalar, array, null, etc.)

    Returns:
        Full agent response dict with task_type, status, and retrieved_data
    """
    return {
        "task_type": "retrieve",
        "status": "SUCCESS",
        "retrieved_data": retrieved_data,
    }


def _generate_alternative_combinations(data: Any, path: str = "") -> list[tuple[str, Any]]:
    """Generate all alternative combinations from nested arrays.

    Nested arrays represent alternative acceptable values. This function generates
    all possible combinations by exploring each alternative path.

    Examples:
        [["a", "b"]] -> [("alt_0", ["a"]), ("alt_1", ["b"])]
        ["x", ["y", "z"]] -> [("alt_0", ["x", "y"]), ("alt_1", ["x", "z"])]

    Args:
        data: The data structure with nested alternatives
        path: Current path for naming (used recursively)

    Returns:
        List of (variation_name, flattened_data) tuples
    """
    if not isinstance(data, list):
        return [(path or "base", data)]

    # Check if any items are nested arrays (alternatives)
    has_alternatives = any(isinstance(item, list) for item in data)

    if not has_alternatives:
        return [(path or "base", data)]

    # Generate combinations
    combinations = []

    def generate_recursive(items: list[Any], index: int, current: list[Any], alt_indices: list[int]) -> None:
        if index >= len(items):
            # Create variation name from alternative indices
            if alt_indices:
                var_name = f"alt_{'_'.join(str(i) for i in alt_indices)}"
            else:
                var_name = "base"
            combinations.append((var_name, current[:]))
            return

        item = items[index]
        if isinstance(item, list):
            # This is an alternatives array, try each alternative
            for i, alternative in enumerate(item):
                current.append(alternative)
                generate_recursive(items, index + 1, current, [*alt_indices, i])
                current.pop()
        else:
            # Regular item
            current.append(item)
            generate_recursive(items, index + 1, current, alt_indices)
            current.pop()

    generate_recursive(data, 0, [], [])
    return combinations


def _apply_invalid_transformation(response: dict[str, Any], variation_type: str) -> dict[str, Any]:
    """Apply an invalid transformation to a valid agent response.

    Args:
        response: The valid agent response
        variation_type: The type of transformation to apply

    Returns:
        The transformed (invalid) response
    """
    invalid_response = copy.deepcopy(response)

    if variation_type == "wrong_status":
        # Flip SUCCESS <-> FAILURE
        invalid_response["status"] = "FAILURE" if response["status"] == "SUCCESS" else "SUCCESS"
    elif variation_type == "null_data":
        invalid_response["retrieved_data"] = None
    elif variation_type == "empty_array":
        invalid_response["retrieved_data"] = []
    elif variation_type == "wrong_type_string":
        invalid_response["retrieved_data"] = "not an array"
    elif variation_type == "wrong_type_number":
        invalid_response["retrieved_data"] = 42
    elif variation_type == "wrong_type_object":
        invalid_response["retrieved_data"] = {"invalid": "structure"}
    elif variation_type == "missing_field":
        del invalid_response["retrieved_data"]
    elif variation_type == "extra_field":
        invalid_response["unexpected_field"] = "should not be here"
    elif variation_type == "wrong_task_type":
        invalid_response["task_type"] = "INVALID_TYPE"
    elif variation_type == "extra_items":
        # Add extra items to the retrieved_data array
        if isinstance(invalid_response.get("retrieved_data"), list):
            invalid_response["retrieved_data"] = [*invalid_response["retrieved_data"], "extra_item", "another_extra"]
    else:
        raise ValueError(f"Unknown variation type: {variation_type}")

    return invalid_response


def _get_schema_format(task_id: int, dataset: MappingProxyType[int, MappingProxyType[str, Any]]) -> str | None:
    """Get the format type from a task's results schema.

    Args:
        task_id: The task ID to check
        dataset: The loaded dataset mapping

    Returns:
        The format type (e.g., "currency", "date", "duration") or None if no format
    """
    if task_id not in dataset:
        return None

    task = dataset[task_id]
    for eval_config in task["eval"]:
        if eval_config["evaluator"] == "AgentResponseEvaluator":
            schema = eval_config.get("results_schema", {})
            # Check if schema has format field (usually in items for arrays)
            if schema.get("type") == "array":
                items = schema.get("items", {})
                return items.get("format")
            # Could also be direct format on schema
            return schema.get("format")
    return None


@pytest.fixture(scope="module")
def dataset(project_root: Path) -> MappingProxyType[int, MappingProxyType[str, Any]]:
    """Load the main dataset file as an immutable mapping indexed by task_id."""
    return _load_dataset(project_root)


@pytest.fixture(scope="module")
def test_data_dir(project_root: Path) -> Path:
    """Get the directory containing test reference data files."""
    return project_root / "tests" / "assets" / "e2e_test_expected"


@pytest.fixture(scope="module")
def test_variations_data(project_root: Path) -> MappingProxyType[int, MappingProxyType[str, Any]]:
    """Load consolidated test variations file.

    Returns:
        Immutable mapping from task_id to test variations dict containing:
        - exact_match: The dataset expected value
        - valid: Dict of variation_name -> retrieved_data value
        - invalid: Dict of variation_name -> retrieved_data value
    """
    variations_file = project_root / "tests" / "assets" / "e2e_test_retrieved_data.json"
    if not variations_file.exists():
        return MappingProxyType({})

    data = json.loads(variations_file.read_text())
    # Convert to immutable and ensure task_ids are ints
    return MappingProxyType({int(task_id): MappingProxyType(variations) for task_id, variations in data.items()})


def _load_variations_from_file(project_root: Path, task_id: int, variation_type: str) -> list[tuple[int, str]]:
    """Load variations from the consolidated test file.

    Args:
        project_root: Project root path
        task_id: Task ID to load variations for
        variation_type: Either "valid" or "invalid"

    Returns:
        List of (task_id, variation_name) tuples
    """
    test_cases: list[tuple[int, str]] = []
    test_file = project_root / "tests" / "assets" / "e2e_test_retrieved_data.json"
    if not test_file.exists():
        return test_cases

    all_variations = json.loads(test_file.read_text())
    task_str = str(task_id)
    if task_str in all_variations:
        task_data = all_variations[task_str]
        special_variations = task_data.get(variation_type, {})
        for variation_name in special_variations:
            test_cases.append((task_id, variation_name))
    return test_cases


def _generate_valid_test_cases(
    task_id: int,
    expected: dict[str, Any],
    project_root: Path,
) -> list[tuple[int, str]]:
    """Generate valid test cases for a task.

    Args:
        task_id: Task ID
        expected: Expected response from dataset
        project_root: Project root path

    Returns:
        List of (task_id, variation_name) tuples
    """
    test_cases: list[tuple[int, str]] = []
    retrieved_data = expected.get("retrieved_data", [])

    # Generate all alternative combinations
    alternatives = _generate_alternative_combinations(retrieved_data)
    for alt_name, _ in alternatives:
        test_cases.append((task_id, alt_name))

    # Add variations from consolidated file
    test_cases.extend(_load_variations_from_file(project_root, task_id, "valid"))
    return test_cases


def _generate_invalid_test_cases(
    task_id: int,
    dataset: MappingProxyType[int, MappingProxyType[str, Any]],
    project_root: Path,
) -> list[tuple[int, str]]:
    """Generate invalid test cases for a task.

    Args:
        task_id: Task ID
        dataset: The loaded dataset
        project_root: Project root path

    Returns:
        List of (task_id, variation_name) tuples
    """
    test_cases: list[tuple[int, str]] = []
    invalid_variation_types = [
        "wrong_status",
        "null_data",
        "empty_array",
        "wrong_type_string",
        "wrong_type_number",
        "wrong_type_object",
        "missing_field",
        "wrong_task_type",
        "extra_items",
    ]

    is_boolean_schema = _has_boolean_schema(task_id, dataset)
    for variation_type in invalid_variation_types:
        if variation_type == "wrong_type_number" and is_boolean_schema:
            continue
        test_cases.append((task_id, f"default_{variation_type}"))

    # Add variations from consolidated file
    test_cases.extend(_load_variations_from_file(project_root, task_id, "invalid"))
    return test_cases


def _should_skip_task(
    task_id: int,
    dataset: MappingProxyType[int, MappingProxyType[str, Any]],
) -> bool:
    """Check if a task should be skipped for test generation.

    Args:
        task_id: Task ID
        dataset: The loaded dataset

    Returns:
        True if task should be skipped
    """
    expected = _get_expected_from_dataset(task_id, dataset)
    if expected.get("status") != "SUCCESS":
        return True

    task = dataset[task_id]
    return any(e["evaluator"] == "NetworkEventEvaluator" for e in task["eval"])


def pytest_generate_tests(metafunc):
    """Generate test cases for all retrieval tasks and variations."""
    if "task_id" not in metafunc.fixturenames or "variation_name" not in metafunc.fixturenames:
        return

    is_valid_test = "invalid" not in metafunc.function.__name__
    project_root = Path(metafunc.config.rootpath)
    dataset = _load_dataset(project_root)
    retrieval_task_ids = _get_retrieval_task_ids(dataset)

    test_cases: list[tuple[int, str]] = []
    for task_id in retrieval_task_ids:
        if _should_skip_task(task_id, dataset):
            continue

        if is_valid_test:
            expected = _get_expected_from_dataset(task_id, dataset)
            test_cases.extend(_generate_valid_test_cases(task_id, expected, project_root))
        else:
            test_cases.extend(_generate_invalid_test_cases(task_id, dataset, project_root))

    if test_cases:
        metafunc.parametrize(
            ("task_id", "variation_name"),
            test_cases,
            ids=lambda params: f"task_{params[0]}_{params[1]}" if isinstance(params, tuple) else str(params),
        )


def test_evaluate_retrieval_task_valid_variations(
    task_id: int,
    variation_name: str,
    wa: WebArenaVerified,
    dataset: MappingProxyType[int, MappingProxyType[str, Any]],
    test_variations_data: MappingProxyType[int, MappingProxyType[str, Any]],
    har_file_example: Path,
):
    if variation_name in UNSUPPORTED_RETRIEVAL_VARIATIONS:
        pytest.skip(f"Unsupported retrieval variation '{variation_name}' (see NEW_TESTS_ISSUES.md)")

    # Load the agent response based on variation name
    if variation_name.startswith("alt_") or variation_name == "base":
        # Load from dataset and select the appropriate alternative
        expected = _get_expected_from_dataset(task_id, dataset)
        retrieved_data = expected.get("retrieved_data", [])

        # Generate all alternatives and find the matching one
        alternatives = _generate_alternative_combinations(retrieved_data)
        matching_alt = next((alt_data for alt_name, alt_data in alternatives if alt_name == variation_name), None)

        if matching_alt is None:
            raise ValueError(f"Alternative {variation_name} not found for task {task_id}")

        agent_response = {
            **expected,
            "retrieved_data": matching_alt,
        }
    else:
        # Load from consolidated variations file (includes format variations and special cases)
        # Format variations are pre-generated via tmp/generate_format_variations.py
        if task_id in test_variations_data:
            task_variations = test_variations_data[task_id]
            if variation_name in task_variations.get("valid", {}):
                retrieved_data = task_variations["valid"][variation_name]
                agent_response = _reconstruct_agent_response(retrieved_data)
            else:
                raise ValueError(f"Variation {variation_name} not found for task {task_id}")
        else:
            raise ValueError(f"No test data for task {task_id}")

    # Generate all variations to test (case sensitivity, whitespace, format, etc.)
    all_variations = [json.dumps(dict(agent_response))]

    retrieved_data = agent_response.get("retrieved_data", [])
    assert isinstance(retrieved_data, list), "retrieved_data should be a list. (Invalid test data)"

    # Check if ALL items are strings (not lists/alternatives)
    all_items_are_strings = retrieved_data and all(isinstance(item, str) for item in retrieved_data)

    if all_items_are_strings:
        # Skip case/whitespace variations for regex patterns
        is_regex_data = any(is_regexp(item) for item in retrieved_data)

        if not is_regex_data:
            # Add case variations for string items
            all_variations.append(
                json.dumps(
                    {
                        **agent_response,
                        "retrieved_data": [item.upper() for item in retrieved_data],
                    }
                )
            )
            # Add whitespace variations for string items
            all_variations.append(
                json.dumps(
                    {
                        **agent_response,
                        "retrieved_data": [f"  {item}  " for item in retrieved_data],
                    }
                )
            )
        # Add json markdown format variations
        all_variations.append("```json\n" + json.dumps(dict(agent_response), indent=2) + "\n\n```")

    if retrieved_data and len(retrieved_data) == 1 and not isinstance(retrieved_data[0], list):
        # Add variation with single item (not in a list)
        # Skip if the single item is a list (alternatives) - unwrapping would change meaning
        all_variations.append(json.dumps({**agent_response, "retrieved_data": retrieved_data[0]}))

    for variation in all_variations:
        # Evaluate
        result = wa.evaluate_task(
            task_id=task_id,
            agent_response=variation,
            network_trace=har_file_example,
        )

        logger.debug(
            f"Evaluation result for task {task_id}, variation '{variation_name}': {result.model_dump_json(indent=2)}"
        )

        # Assert evaluation succeeds
        assert result.task_id == task_id, "Task ID mismatch"
        assert result.status == EvalStatus.SUCCESS, f"Expected SUCCESS, got {result.status}"
        assert result.score == 1.0, f"Expected score 1.0, got {result.score}"

        # Verify AgentResponseEvaluator passed
        for eval_result in result.evaluators_results:
            if eval_result.evaluator_name == "AgentResponseEvaluator":
                assert not eval_result.assertions, f"Unexpected assertions: {eval_result.assertions}"
                assert eval_result.error_msg is None, f"Unexpected error: {eval_result.error_msg}"
                assert eval_result.status == EvalStatus.SUCCESS
                assert eval_result.score == 1.0


def test_evaluate_retrieval_task_invalid_variations(
    task_id: int,
    variation_name: str,
    wa: WebArenaVerified,
    dataset: MappingProxyType[int, MappingProxyType[str, Any]],
    test_variations_data: MappingProxyType[int, MappingProxyType[str, Any]],
    har_file_example,
):
    # Load the agent response based on variation name
    if variation_name.startswith("default_"):
        # Load valid response from dataset and apply transformation
        valid_response = _get_expected_from_dataset(task_id, dataset)
        variation_type = variation_name.replace("default_", "")
        agent_response = _apply_invalid_transformation(valid_response, variation_type)
    else:
        # Load from consolidated variations file
        if task_id in test_variations_data:
            task_variations = test_variations_data[task_id]
            if variation_name in task_variations.get("invalid", {}):
                retrieved_data = task_variations["invalid"][variation_name]
                agent_response = _reconstruct_agent_response(retrieved_data)
            else:
                raise ValueError(f"Invalid variation {variation_name} not found for task {task_id}")
        else:
            raise ValueError(f"No test data for task {task_id}")

    # Evaluate
    result = wa.evaluate_task(
        task_id=task_id,
        agent_response=json.dumps(agent_response),
        network_trace=har_file_example,
    )

    logger.debug(
        f"Evaluation result for task {task_id}, variation '{variation_name}': {result.model_dump_json(indent=2)}"
    )

    # Assert evaluation fails
    assert result.task_id == task_id, "Task ID mismatch"
    assert result.status == EvalStatus.FAILURE, f"Expected FAILURE, got {result.status}"
    assert result.score == 0.0, f"Expected score 0.0, got {result.score}"

    # Verify AgentResponseEvaluator failed
    for eval_result in result.evaluators_results:
        if eval_result.evaluator_name == "AgentResponseEvaluator":
            assert eval_result.status == EvalStatus.FAILURE
            assert eval_result.score == 0.0


@pytest.mark.parametrize(
    ("agent_response", "expected_status", "expected_score"),
    [
        # Valid cases - correct status, should succeed
        ({"task_type": "retrieve", "status": "NOT_FOUND_ERROR"}, EvalStatus.SUCCESS, 1.0),
        ({"task_type": "retrieve", "status": "NOT_FOUND_ERROR", "retrieved_data": None}, EvalStatus.SUCCESS, 1.0),
        ({"task_type": "retrieve", "status": "NOT_FOUND_ERROR", "retrieved_data": []}, EvalStatus.SUCCESS, 1.0),
        # Invalid cases - wrong status, should be FAILURE (not ERROR)
        ({"task_type": "retrieve", "status": "SUCCESS"}, EvalStatus.FAILURE, 0.0),
        ({"task_type": "retrieve", "status": "SUCCESS", "retrieved_data": None}, EvalStatus.FAILURE, 0.0),
        ({"task_type": "retrieve", "status": "SUCCESS", "retrieved_data": []}, EvalStatus.FAILURE, 0.0),
    ],
    ids=[
        "valid_missing_key",
        "valid_null",
        "valid_empty_list",
        "invalid_missing_key",
        "invalid_null",
        "invalid_empty_list",
    ],
)
def test_null_retrieved_data(
    agent_response: dict,
    expected_status: EvalStatus,
    expected_score: float,
    wa: WebArenaVerified,
    har_file_example: Path,
):
    """Test that null expected retrieved_data accepts null, [], or missing key.

    Task 22 has expected: {task_type: "retrieve", status: "NOT_FOUND_ERROR", retrieved_data: None}

    When expected retrieved_data is None, the evaluator should accept:
    - Missing retrieved_data key
    - retrieved_data: null
    - retrieved_data: []

    When status is wrong, it should return FAILURE (not ERROR).
    """
    task_id = 22

    result = wa.evaluate_task(
        task_id=task_id,
        agent_response=json.dumps(agent_response),
        network_trace=har_file_example,
    )

    assert result.status == expected_status
    assert result.score == expected_score
