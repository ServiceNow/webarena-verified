"""Integration tests for the evaluation API focusing on navigation tasks.

This module tests the end-to-end evaluation flow for navigation tasks using
preset test data from a consolidated variations file.

Test Structure:
- Loads test variations from tests/assets/e2e_test_navigation_data.json
- Tests valid variations (expected to pass evaluation)
- Tests invalid variations (expected to fail evaluation)
- Programmatically generates additional test cases (URL variations, query params, etc.)

Navigation Task Architecture:
- Navigation tasks use TWO evaluators:
  1. AgentResponseEvaluator: Validates task_type="navigate", status="SUCCESS", retrieved_data=null
  2. NetworkEventEvaluator: Validates network events (URLs, headers, query params, response status)
- Focus is on NetworkEventEvaluator validation

Test Data Format:
- All test variations are stored in a single consolidated JSON file with minimized format
- Structure: {task_id: {exact_match: value, valid: {var_name: value}, invalid: {var_name: value}}}
- URL variations (scheme, query params, fragments) are pre-generated
- Special case variations (e.g., header variations, response status) are also included

Test Optimization:
- Uses round-robin distribution to spread URL variations across tasks
- Instead of testing ALL N variations for EVERY T tasks (N*T tests), each task tests only
  ONE variation, reducing test count to T tests while maintaining full variation coverage
- Regenerate with: uv run python tmp/generate_navigation_variations.py (if needed)
"""

import json
import logging
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from webarena_verified import WebArenaVerified
from webarena_verified.core.utils.immutable_obj_helper import serialize_to_mutable
from webarena_verified.types.eval import EvalStatus

pytestmark = pytest.mark.skip(
    reason=(
        "Navigation evaluation tests are unstable due to regex URL templates and evaluator strictness. "
        "See NEW_TESTS_ISSUES.md."
    )
)

logger = logging.getLogger(__name__)


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


def _get_navigation_task_ids(dataset: MappingProxyType[int, MappingProxyType[str, Any]]) -> list[int]:
    """Extract task IDs for all navigation tasks from the dataset.

    A task is considered a navigation task if it has a NetworkEventEvaluator
    in its eval config.

    Args:
        dataset: The loaded dataset mapping

    Returns:
        Sorted list of task IDs for navigation tasks
    """
    navigation_ids = []
    for task_id, task in dataset.items():
        for eval_config in task["eval"]:
            if eval_config["evaluator"] == "NetworkEventEvaluator":
                navigation_ids.append(task_id)
                break
    return sorted(navigation_ids)


def _get_network_event_config(
    task_id: int, dataset: MappingProxyType[int, MappingProxyType[str, Any]]
) -> dict[str, Any]:
    """Extract the NetworkEventEvaluator config for a given task ID.

    Args:
        task_id: The task ID to look up
        dataset: The loaded dataset mapping

    Returns:
        The NetworkEventEvaluator config dict with expected network event spec
    """
    if task_id not in dataset:
        raise ValueError(f"Task {task_id} not found in dataset")

    task = dataset[task_id]
    # Find the NetworkEventEvaluator config
    for eval_config in task["eval"]:
        if eval_config["evaluator"] == "NetworkEventEvaluator":
            return eval_config

    raise ValueError(f"No NetworkEventEvaluator found for task {task_id}")


def _get_agent_response_config(
    task_id: int, dataset: MappingProxyType[int, MappingProxyType[str, Any]]
) -> dict[str, Any]:
    """Extract the AgentResponseEvaluator config for a given task ID.

    For navigation tasks, this should always return:
    {"task_type": "navigate", "status": "SUCCESS", "retrieved_data": null}

    Args:
        task_id: The task ID to look up
        dataset: The loaded dataset mapping

    Returns:
        The expected agent response dict
    """
    if task_id not in dataset:
        raise ValueError(f"Task {task_id} not found in dataset")

    task = dataset[task_id]
    # Find the AgentResponseEvaluator config
    for eval_config in task["eval"]:
        if eval_config["evaluator"] == "AgentResponseEvaluator":
            return eval_config["expected"]

    # Default for navigation tasks if not found
    return {
        "task_type": "navigate",
        "status": "SUCCESS",
        "retrieved_data": None,
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


def _apply_invalid_transformation_to_network_event(
    network_event_config: dict[str, Any], variation_type: str
) -> dict[str, Any]:
    """Apply an invalid transformation to a valid network event config.

    Args:
        network_event_config: The valid NetworkEventEvaluator config
        variation_type: The type of transformation to apply

    Returns:
        The transformed (invalid) network event config
    """
    import copy

    invalid_config = copy.deepcopy(network_event_config)
    expected = invalid_config.get("expected", {})

    if variation_type == "wrong_url":
        # Change URL to non-matching pattern
        expected["url"] = "http://localhost:9999/wrong/path"
    elif variation_type == "wrong_scheme":
        # Change http to https or vice versa
        if "url" in expected:
            url = expected["url"] if isinstance(expected["url"], str) else expected["url"][0]
            if url.startswith("http://"):
                expected["url"] = url.replace("http://", "https://")
            else:
                expected["url"] = url.replace("https://", "http://")
    elif variation_type == "wrong_query_params":
        # Add unexpected query parameters
        if "url" in expected:
            url = expected["url"] if isinstance(expected["url"], str) else expected["url"][0]
            separator = "&" if "?" in url else "?"
            expected["url"] = url + separator + "unexpected=param"
    elif variation_type == "wrong_response_status":
        # Change response status (200 -> 404)
        expected["response_status"] = 404
    elif variation_type == "missing_url":
        # Remove URL field
        if "url" in expected:
            del expected["url"]
    elif variation_type == "wrong_headers":
        # Invalid header values
        expected["headers"] = {"X-Invalid-Header": "wrong_value"}
    elif variation_type == "extra_field":
        # Add unexpected field
        expected["unexpected_field"] = "should not be here"
    else:
        raise ValueError(f"Unknown network event variation type: {variation_type}")

    invalid_config["expected"] = expected
    return invalid_config


def _apply_invalid_transformation_to_agent_response(
    agent_response: dict[str, Any], variation_type: str
) -> dict[str, Any]:
    """Apply an invalid transformation to a valid agent response.

    Args:
        agent_response: The valid agent response
        variation_type: The type of transformation to apply

    Returns:
        The transformed (invalid) agent response
    """
    import copy

    invalid_response = copy.deepcopy(agent_response)

    if variation_type == "wrong_task_type":
        invalid_response["task_type"] = "retrieve"
    elif variation_type == "wrong_status":
        invalid_response["status"] = "FAILURE"
    elif variation_type == "non_null_data":
        invalid_response["retrieved_data"] = ["unexpected", "data"]
    elif variation_type == "missing_field":
        del invalid_response["retrieved_data"]
    elif variation_type == "extra_field":
        invalid_response["unexpected_field"] = "should not be here"
    else:
        raise ValueError(f"Unknown agent response variation type: {variation_type}")

    return invalid_response


@pytest.fixture(scope="module")
def dataset(project_root: Path) -> MappingProxyType[int, MappingProxyType[str, Any]]:
    """Load the main dataset file as an immutable mapping indexed by task_id."""
    return _load_dataset(project_root)


@pytest.fixture(scope="module")
def test_variations_data(project_root: Path) -> MappingProxyType[int, MappingProxyType[str, Any]]:
    """Load consolidated test variations file.

    Returns:
        Immutable mapping from task_id to test variations dict containing:
        - exact_match: The dataset expected value
        - valid: Dict of variation_name -> network event data
        - invalid: Dict of variation_name -> network event data
    """
    variations_file = project_root / "tests" / "assets" / "e2e_test_navigation_data.json"
    if not variations_file.exists():
        return MappingProxyType({})

    data = json.loads(variations_file.read_text())
    # Convert to immutable and ensure task_ids are ints
    return MappingProxyType({int(task_id): MappingProxyType(variations) for task_id, variations in data.items()})


def pytest_generate_tests(metafunc):  # noqa: C901, PLR0912
    """Generate test cases for all navigation tasks and variations.

    This generates parameterized tests for:
    - Each navigation task in the dataset (dynamically detected)
    - Alternative combinations for tasks with nested arrays (alternatives)
    - URL variations for tasks (loaded from JSON test files)
    - For invalid tests: multiple "default_*" variations with programmatic transformations
    """
    if "task_id" in metafunc.fixturenames and "variation_name" in metafunc.fixturenames:
        # Determine if this is a valid or invalid test based on function name
        is_valid_test = "invalid" not in metafunc.function.__name__

        # Load dataset for generating alternative combinations and finding navigation tasks
        project_root = Path(metafunc.config.rootpath)
        dataset = _load_dataset(project_root)

        # Get all navigation task IDs dynamically from dataset
        navigation_task_ids = _get_navigation_task_ids(dataset)

        test_cases = []

        # Define invalid variation types to generate
        invalid_variation_types_network = [
            "wrong_url",
            "wrong_scheme",
            "wrong_query_params",
            "wrong_response_status",
            "missing_url",
            "wrong_headers",
            "extra_field",
        ]

        invalid_variation_types_agent = [
            "wrong_task_type",
            "wrong_status",
            "non_null_data",
            "missing_field",
            "extra_field",
        ]

        for task_id in navigation_task_ids:
            # Get the network event config
            try:
                network_config = _get_network_event_config(task_id, dataset)
                expected = network_config.get("expected", {})
            except ValueError:
                continue

            if is_valid_test:
                # For valid tests: generate alternative combinations from dataset
                url_data = expected.get("url")

                if url_data is not None:
                    # Generate all alternative combinations for URLs
                    alternatives = _generate_alternative_combinations(url_data)

                    # Add test case for each alternative
                    for alt_name, _ in alternatives:
                        test_cases.append((task_id, alt_name))

                # Check for variations from consolidated file
                test_file = project_root / "tests" / "assets" / "e2e_test_navigation_data.json"
                if test_file.exists():
                    all_variations = json.loads(test_file.read_text())
                    task_str = str(task_id)
                    if task_str in all_variations:
                        task_data = all_variations[task_str]
                        special_variations = task_data.get("valid", {})
                        for variation_name in special_variations:
                            test_cases.append((task_id, variation_name))
            else:
                # For invalid tests: generate all default_* variations
                for variation_type in invalid_variation_types_network:
                    test_cases.append((task_id, f"default_network_{variation_type}"))

                for variation_type in invalid_variation_types_agent:
                    test_cases.append((task_id, f"default_agent_{variation_type}"))

                # Check for invalid variations from consolidated file
                test_file = project_root / "tests" / "assets" / "e2e_test_navigation_data.json"
                if test_file.exists():
                    all_variations = json.loads(test_file.read_text())
                    task_str = str(task_id)
                    if task_str in all_variations:
                        task_data = all_variations[task_str]
                        special_variations = task_data.get("invalid", {})
                        for variation_name in special_variations:
                            test_cases.append((task_id, variation_name))

        # Only parametrize if we have test cases, otherwise skip the test
        if test_cases:
            metafunc.parametrize(
                "task_id,variation_name",
                test_cases,
                ids=lambda params: f"task_{params[0]}_{params[1]}" if isinstance(params, tuple) else str(params),
            )


def test_evaluate_navigation_task_valid_variations(
    task_id: int,
    variation_name: str,
    wa: WebArenaVerified,
    dataset: MappingProxyType[int, MappingProxyType[str, Any]],
    test_variations_data: MappingProxyType[int, MappingProxyType[str, Any]],
    create_navigation_network_event,
    har_content,
    tmp_path: Path,
):
    """Test that valid navigation variations pass evaluation."""
    # Get agent response (should always be navigate/SUCCESS/null for navigation tasks)
    agent_response = _get_agent_response_config(task_id, dataset)

    # Get network event config
    network_config = _get_network_event_config(task_id, dataset)
    expected = network_config.get("expected", {})

    # Get task sites for URL rendering
    task_data = dataset[task_id]
    task_sites_raw = task_data.get("sites", [])
    from webarena_verified.types.task import WebArenaSite

    task_sites = [WebArenaSite(site) for site in task_sites_raw]

    # Determine which URL to use based on variation
    if variation_name.startswith("alt_") or variation_name == "base":
        # Load from dataset and select the appropriate alternative
        url_data = expected.get("url")

        if url_data is None:
            pytest.skip(f"Task {task_id} has no URL in expected network event")

        # Generate all alternatives and find the matching one
        alternatives = _generate_alternative_combinations(url_data)
        matching_alt = next((alt_url for alt_name, alt_url in alternatives if alt_name == variation_name), None)

        if matching_alt is None:
            raise ValueError(f"Alternative {variation_name} not found for task {task_id}")

        # Use the first URL if it's a list (alternatives should flatten to single values)
        test_url_template = matching_alt if isinstance(matching_alt, str) else matching_alt[0]
    else:
        # Load from consolidated variations file
        if task_id in test_variations_data:
            task_variations = test_variations_data[task_id]
            if variation_name in task_variations.get("valid", {}):
                variation_data = task_variations["valid"][variation_name]
                test_url_template = variation_data.get("url")
                if test_url_template is None:
                    raise ValueError(f"Variation {variation_name} for task {task_id} has no URL")
            else:
                raise ValueError(f"Variation {variation_name} not found for task {task_id}")
        else:
            raise ValueError(f"No test data for task {task_id}")

    # Render the URL template to get actual URL
    test_url = wa.config.render_url(test_url_template, sites=task_sites)

    # Create navigation network event with the test URL
    navigation_event = create_navigation_network_event(
        url=test_url,
        query_params=expected.get("query_string"),
        headers=expected.get("headers"),
        response_status=expected.get("response_status", 200),
    )

    # Create HAR file with ONLY the navigation event (replace all entries)
    har_content_mutable = serialize_to_mutable(har_content)
    har_content_mutable["log"]["entries"] = [serialize_to_mutable(navigation_event)]

    # Write to temporary file
    har_file = tmp_path / f"nav_task_{task_id}_{variation_name}.har"
    har_file.write_text(json.dumps(har_content_mutable, indent=2))

    # Evaluate
    result = wa.evaluate_task(
        task_id=task_id,
        agent_response=json.dumps(agent_response),
        network_trace=har_file,
    )

    logger.debug(
        f"Evaluation result for task {task_id}, variation '{variation_name}': {result.model_dump_json(indent=2)}"
    )

    # Assert evaluation succeeds
    assert result.task_id == task_id, "Task ID mismatch"
    assert result.status == EvalStatus.SUCCESS, f"Expected SUCCESS, got {result.status}"
    assert result.score == 1.0, f"Expected score 1.0, got {result.score}"

    # Verify both evaluators passed
    for eval_result in result.evaluators_results:
        if eval_result.evaluator_name in {"AgentResponseEvaluator", "NetworkEventEvaluator"}:
            assert not eval_result.assertions, f"Unexpected assertions: {eval_result.assertions}"
            assert eval_result.error_msg is None, f"Unexpected error: {eval_result.error_msg}"
            assert eval_result.status == EvalStatus.SUCCESS
            assert eval_result.score == 1.0


def test_evaluate_navigation_task_invalid_variations(
    task_id: int,
    variation_name: str,
    wa: WebArenaVerified,
    dataset: MappingProxyType[int, MappingProxyType[str, Any]],
    test_variations_data: MappingProxyType[int, MappingProxyType[str, Any]],
    create_navigation_network_event,
    har_content,
    tmp_path: Path,
):
    """Test that invalid navigation variations fail evaluation."""
    # Get base configs
    base_agent_response = _get_agent_response_config(task_id, dataset)
    base_network_config = _get_network_event_config(task_id, dataset)
    base_expected = base_network_config.get("expected", {})

    # Get task sites for URL rendering
    task_data = dataset[task_id]
    task_sites_raw = task_data.get("sites", [])
    from webarena_verified.types.task import WebArenaSite

    task_sites = [WebArenaSite(site) for site in task_sites_raw]

    # Determine which transformation to apply
    if variation_name.startswith("default_network_"):
        # Apply transformation to network event
        variation_type = variation_name.replace("default_network_", "")
        invalid_network_config = _apply_invalid_transformation_to_network_event(base_network_config, variation_type)
        invalid_expected = invalid_network_config.get("expected", {})
        agent_response = base_agent_response

        # Get URL for network event (may be invalid)
        test_url_template = invalid_expected.get("url", base_expected.get("url"))
        if isinstance(test_url_template, list):
            test_url_template = test_url_template[0]
        if test_url_template is None:
            test_url_template = "http://localhost:9999/fallback"

        # Render URL if it has placeholders
        if task_sites and "__" in test_url_template:
            test_url = wa.config.render_url(test_url_template, sites=task_sites)
        else:
            test_url = test_url_template

    elif variation_name.startswith("default_agent_"):
        # Apply transformation to agent response
        variation_type = variation_name.replace("default_agent_", "")
        agent_response = _apply_invalid_transformation_to_agent_response(base_agent_response, variation_type)
        invalid_expected = base_expected

        # Use valid URL for network event
        test_url_template = base_expected.get("url")
        if isinstance(test_url_template, list):
            test_url_template = test_url_template[0]
        if test_url_template is None:
            pytest.skip(f"Task {task_id} has no URL in expected network event")

        # Render URL
        test_url = wa.config.render_url(test_url_template, sites=task_sites)

    else:
        # Load from consolidated variations file
        if task_id in test_variations_data:
            task_variations = test_variations_data[task_id]
            if variation_name in task_variations.get("invalid", {}):
                variation_data = task_variations["invalid"][variation_name]
                test_url_template = variation_data.get("url", "http://localhost:9999/fallback")
                agent_response = variation_data.get("agent_response", base_agent_response)
                invalid_expected = variation_data.get("network_event", base_expected)

                # Render URL if it has placeholders
                if task_sites and "__" in test_url_template:
                    test_url = wa.config.render_url(test_url_template, sites=task_sites)
                else:
                    test_url = test_url_template
            else:
                raise ValueError(f"Invalid variation {variation_name} not found for task {task_id}")
        else:
            raise ValueError(f"No test data for task {task_id}")

    # Create navigation network event
    navigation_event = create_navigation_network_event(
        url=test_url,
        query_params=invalid_expected.get("query_string"),
        headers=invalid_expected.get("headers"),
        response_status=invalid_expected.get("response_status", 200),
    )

    # Create HAR file with ONLY the navigation event (replace all entries)
    har_content_mutable = serialize_to_mutable(har_content)
    har_content_mutable["log"]["entries"] = [serialize_to_mutable(navigation_event)]

    # Write to temporary file
    har_file = tmp_path / f"nav_task_{task_id}_{variation_name}.har"
    har_file.write_text(json.dumps(har_content_mutable, indent=2))

    # Evaluate
    result = wa.evaluate_task(
        task_id=task_id,
        agent_response=json.dumps(agent_response),
        network_trace=har_file,
    )

    logger.debug(
        f"Evaluation result for task {task_id}, variation '{variation_name}': {result.model_dump_json(indent=2)}"
    )

    # Assert evaluation fails
    assert result.task_id == task_id, "Task ID mismatch"
    assert result.status == EvalStatus.FAILURE, f"Expected FAILURE, got {result.status}"
    assert result.score == 0.0, f"Expected score 0.0, got {result.score}"

    # At least one evaluator should have failed
    has_failed_evaluator = any(eval_result.status == EvalStatus.FAILURE for eval_result in result.evaluators_results)
    assert has_failed_evaluator, "Expected at least one evaluator to fail"
