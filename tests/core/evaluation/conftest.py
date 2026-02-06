"""Shared fixtures for core evaluation tests.

This file provides common fixtures for all tests in tests/core/evaluation/.
"""

from pathlib import Path
from typing import Any

import pytest

from webarena_verified.api.webarena_verified import WebArenaVerified
from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.eval import TaskEvalContext, TaskEvalResult
from webarena_verified.types.tracing import NetworkTrace

__all__ = [
    "base_trace",
    "create_agent_response",
    "create_navigate_response",
    "create_response",
    "evaluate_task",
    "test_har_path",
]


@pytest.fixture
def create_response():
    """Base fixture to create agent response dicts.

    This is the foundational fixture used by create_agent_response and create_navigate_response.

    Returns:
        Callable that creates properly formatted agent response dict

    Example:
        >>> def test_custom(create_response):
        ...     response = create_response("MUTATE", status="SUCCESS", retrieved_data={"id": 123})
    """

    def _create(task_type: str, status: str = "SUCCESS", retrieved_data: Any = None) -> dict:
        """Create properly formatted agent response dict.

        Args:
            task_type: Operation type (e.g., "RETRIEVE", "NAVIGATE", "MUTATE")
            status: Status string (default: "SUCCESS")
            retrieved_data: Data to return (default: None)

        Returns:
            Dict formatted as agent response
        """
        return {
            "task_type": task_type.upper(),
            "status": status.upper(),
            "retrieved_data": retrieved_data,
        }

    return _create


@pytest.fixture
def create_agent_response(create_response):
    """Fixture to create agent responses for RETRIEVE tasks.

    This is a convenience wrapper around create_response that defaults to task_type="retrieve".

    Returns:
        Callable that creates RETRIEVE agent response dicts

    Example:
        >>> def test_retrieve(create_agent_response):
        ...     response = create_agent_response(retrieved_data=["data"])
    """

    def _create(status: str = "SUCCESS", retrieved_data: Any = None) -> dict:
        """Create RETRIEVE agent response dict.

        Args:
            status: Status string (default: "SUCCESS")
            retrieved_data: Data to return (default: None)

        Returns:
            Dict formatted as RETRIEVE agent response
        """
        return create_response("retrieve", status=status, retrieved_data=retrieved_data)

    return _create


@pytest.fixture
def create_navigate_response(create_response):
    """Fixture to create NAVIGATE agent response dicts.

    This fixture wraps create_response with task_type pre-filled as "NAVIGATE".

    Args:
        create_response: Base response creation fixture

    Returns:
        Callable that creates NAVIGATE agent response dict

    Example:
        >>> def test_my_task(create_navigate_response):
        ...     response = create_navigate_response()
        ...     # Or with custom status
        ...     response = create_navigate_response(status="FAILURE")
    """

    def _create(status: str = "SUCCESS", retrieved_data: Any = None) -> dict:
        """Create NAVIGATE agent response dict.

        Args:
            status: Status string (default: "SUCCESS")
            retrieved_data: Data to return (default: None)

        Returns:
            Dict formatted as agent response with task_type="NAVIGATE"
        """
        return create_response("NAVIGATE", status=status, retrieved_data=retrieved_data)

    return _create


@pytest.fixture(scope="module")
def test_har_path(project_root) -> Path:
    """Path to test HAR file with real network events.

    Returns:
        Path to network.har containing 358 real network events
    """
    return project_root / "tests" / "assets" / "network.har"


@pytest.fixture(scope="module")
def base_trace(test_har_path):
    """NetworkTrace loaded from HAR file.

    This fixture is module-scoped to avoid reloading the HAR file
    for every test (358 events is expensive to parse repeatedly).

    Returns:
        NetworkTrace with real events from shopping_admin session
    """
    return NetworkTrace.from_har(test_har_path)


@pytest.fixture
def evaluate_task(
    main_config: WebArenaVerifiedConfig,
):
    """Unified fixture to evaluate tasks with agent responses and/or network traces.

    This fixture supports both agent response validation and network event validation:
    - Agent response tests: Pass agent_response parameter
    - Network event tests: Pass network_trace parameter
    - Both: Pass both parameters

    Uses the WebArenaVerified facade class for evaluation.

    Args:
        main_config: WebArenaVerifiedConfig fixture

    Returns:
        Callable that takes task_id and optional agent_response/network_trace

    Example:
        >>> # Agent response test
        >>> def test_agent(evaluate_task, create_agent_response):
        ...     response = create_agent_response(retrieved_data=[{"order_count": 0, "amount": 0}])
        ...     eval_context, result = evaluate_task(task_id=47, agent_response=response)
        ...
        >>> # Network event test
        >>> def test_network(evaluate_task, create_navigate_response, base_trace):
        ...     eval_context, result = evaluate_task(
        ...         task_id=677,
        ...         network_trace=base_trace,
        ...         agent_response=create_navigate_response()
        ...     )
    """
    # Create WebArenaVerified facade once for all evaluations
    wa = WebArenaVerified(config=main_config)

    def _evaluate(
        *,
        task_id: int,
        agent_response: Any,
        network_trace: NetworkTrace | None = None,
    ) -> tuple[TaskEvalContext, TaskEvalResult]:
        """Evaluate a task with the given agent response and/or network trace.

        Args:
            task_id: Task ID to evaluate
            agent_response: Agent response dict (required - use create_agent_response or create_navigate_response)
            network_trace: Optional NetworkTrace (creates minimal trace if not provided)

        Returns:
            Tuple of (TaskEvalContext, TaskEvalResult) for backward compatibility with existing tests
        """
        # Get the task for building the context
        task = wa.get_task(task_id)

        # Create network trace if not provided
        if network_trace is None:
            minimal_trace = [
                {
                    "type": "resource-snapshot",
                    "snapshot": {
                        "request": {
                            "url": "http://localhost:7780/",
                            "method": "GET",
                            "headers": {},
                        },
                        "response": {
                            "status": 200,
                            "headers": {},
                        },
                    },
                }
            ]
            network_trace = NetworkTrace.from_content(minimal_trace)

        # Evaluate using the facade
        result = wa.evaluate_task(
            task_id=task_id,
            agent_response=agent_response,
            network_trace=network_trace,
        )

        # Build context for backward compatibility with assertion helpers
        eval_context = TaskEvalContext(
            task=task,
            agent_response_raw=agent_response,
            network_trace=network_trace,
            config=main_config,
        )

        return eval_context, result

    return _evaluate
