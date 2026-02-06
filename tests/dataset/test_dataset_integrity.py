"""Dataset integrity tests."""

from collections import Counter
from typing import Any

import pytest
from jinja2 import Template


def _get_site_distribution(tasks: list[dict[str, Any]]) -> Counter[tuple[str, ...]]:
    """Count tasks per unique sorted site combination."""
    return Counter(tuple(sorted(task["sites"])) for task in tasks)


def test_data_coverage(
    dataset: list[dict[str, Any]],
    original_dataset: list[dict[str, Any]],
    dataset_by_task_id: dict[int, dict[str, Any]],
    original_by_task_id: dict[int, dict[str, Any]],
) -> None:
    """Verify dataset coverage matches original data."""
    assert len(dataset) == len(original_dataset), (
        f"Task count mismatch: current has {len(dataset)}, original has {len(original_dataset)}"
    )

    for task_id, original_task in original_by_task_id.items():
        assert task_id in dataset_by_task_id, f"Missing task_id {task_id}"
        current_task = dataset_by_task_id[task_id]
        assert current_task["intent_template_id"] == original_task["intent_template_id"], (
            f"Task {task_id}: intent_template_id mismatch - "
            f"current has {current_task['intent_template_id']}, "
            f"original has {original_task['intent_template_id']}"
        )
        assert sorted(current_task["sites"]) == sorted(original_task["sites"]), (
            f"Task {task_id}: sites mismatch - "
            f"current has {sorted(current_task['sites'])}, "
            f"original has {sorted(original_task['sites'])}"
        )

    # Compare site distribution
    current_distribution = _get_site_distribution(dataset)
    original_distribution = _get_site_distribution(original_dataset)

    assert current_distribution == original_distribution, (
        f"Site distribution mismatch:\n  Current:  {current_distribution}\n  Original: {original_distribution}"
    )


@pytest.mark.parametrize("task_id", range(812))
def test_intent_rendering(task_id: int, dataset_by_task_id: dict[int, dict[str, Any]]) -> None:
    """Verify intent matches rendered intent_template for each task."""
    task = dataset_by_task_id[task_id]

    intent = task["intent"]
    intent_template = task["intent_template"]
    instantiation_dict = task["instantiation_dict"]

    rendered = Template(intent_template).render(**instantiation_dict)
    assert intent == rendered, (
        f"Task {task_id}: intent mismatch\n"
        f"  Expected (rendered): {rendered}\n"
        f"  Actual (intent):     {intent}\n"
        f"  Template: {intent_template}\n"
        f"  Variables: {instantiation_dict}"
    )


@pytest.mark.parametrize("task_id", range(812))
def test_eval_config(task_id: int, dataset_by_task_id: dict[int, dict[str, Any]]) -> None:
    """Verify eval configuration matches task type requirements.

    Validates two rules:
    1. Every task must have at least one AgentResponseEvaluator
    2. Retrieve tasks should not have NetworkEventEvaluator, while navigate/mutate tasks should

    Known exceptions are documented and allowed:
    - Retrieve tasks with NetworkEventEvaluator: Map-based tasks that need route API verification
    - Non-retrieve tasks without NetworkEventEvaluator: Tasks expecting ACTION_NOT_ALLOWED_ERROR
      or open-ended navigation without specific URL targets
    """
    # Known exceptions: retrieve tasks that legitimately need NetworkEventEvaluator
    # These are map-based tasks that verify the routing API was called
    retrieve_with_network_allowed = {97, 265, 266, 267, 268}

    # Known exceptions: non-retrieve tasks that don't require NetworkEventEvaluator
    # These expect ACTION_NOT_ALLOWED_ERROR or are open-ended navigation tasks
    non_retrieve_without_network_allowed = {118, 491, 790, 805, 807}

    task = dataset_by_task_id[task_id]

    # Extract evaluators
    evals = task["eval"]
    agent_response_evals = [e for e in evals if e["evaluator"] == "AgentResponseEvaluator"]
    network_event_evals = [e for e in evals if e["evaluator"] == "NetworkEventEvaluator"]

    # Every task must have AgentResponseEvaluator
    assert len(agent_response_evals) > 0, f"Task {task_id}: must have at least one AgentResponseEvaluator"

    # Get task_type from first AgentResponseEvaluator
    task_type = agent_response_evals[0]["expected"]["task_type"]

    # Validate based on task_type
    if task_type == "retrieve":
        if task_id not in retrieve_with_network_allowed:
            assert len(network_event_evals) == 0, (
                f"Task {task_id}: retrieve tasks must not have NetworkEventEvaluator configs"
            )
    else:  # navigate or mutate
        if task_id not in non_retrieve_without_network_allowed:
            assert len(network_event_evals) > 0, (
                f"Task {task_id}: {task_type} tasks must have at least one NetworkEventEvaluator"
            )


def test_intent_template_consistency(
    intent_template_id: int,
    tasks_by_intent_template_id: dict[int, list[dict[str, Any]]],
) -> None:
    """Verify tasks with same intent_template_id have consistent template and keys."""
    tasks = tasks_by_intent_template_id.get(intent_template_id, [])

    if len(tasks) < 2:
        return  # Nothing to compare for single-task templates

    first_task = tasks[0]
    expected_template = first_task["intent_template"]
    expected_keys = set(first_task["instantiation_dict"].keys())

    for task in tasks[1:]:
        task_id = task["task_id"]
        assert task["intent_template"] == expected_template, (
            f"Task {task_id}: intent_template differs from other tasks with template_id {intent_template_id}\n"
            f"  Expected: {expected_template}\n"
            f"  Actual:   {task['intent_template']}"
        )
        actual_keys = set(task["instantiation_dict"].keys())
        assert actual_keys == expected_keys, (
            f"Task {task_id}: instantiation_dict keys differ from other tasks with template_id {intent_template_id}\n"
            f"  Expected keys: {expected_keys}\n"
            f"  Actual keys:   {actual_keys}"
        )
