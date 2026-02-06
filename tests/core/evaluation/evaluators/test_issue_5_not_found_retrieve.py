"""Test to reproduce Issue #5: AgentResponseEvaluator raises on NOT_FOUND retrieve tasks.

GitHub Issue: https://github.com/.../issues/5

Problem:
When evaluating retrieve tasks where the expected outcome is an error (e.g., NOT_FOUND_ERROR),
the evaluator raises:
    "Expected retrieved_data must be set in config for retrieve tasks."

This happens because in `_compare_values`, the code raises an error when
`expected_retrieved_data is None`, without checking if the expected status is an error status.

For retrieve tasks where the expected status is an error (NOT_FOUND_ERROR, etc.),
it's reasonable for expected `retrieved_data` to be null/omitted.
"""

import json

import pytest

from webarena_verified.types.eval import EvalStatus


class TestIssue5NotFoundRetrieve:
    """Tests reproducing Issue #5: AgentResponseEvaluator fails on NOT_FOUND retrieve tasks."""

    def test_not_found_retrieve_task_returns_error_status(
        self,
        evaluate_task,
        create_agent_response,
    ):
        """Reproduce Issue #5: Evaluator returns error for NOT_FOUND retrieve tasks.

        Task 22 is a retrieve task with:
        - expected.task_type = "retrieve"
        - expected.status = "NOT_FOUND_ERROR"
        - expected.retrieved_data = None

        When the agent correctly responds with NOT_FOUND_ERROR and empty/null retrieved_data,
        the evaluator should succeed. But currently it returns an error result because
        the ValueError is raised and caught in the base evaluator.

        This test verifies the bug exists by checking for the error status and message.
        Once the bug is fixed, this test should be updated to verify success.
        """
        # Task 22 has expected: {task_type: "retrieve", status: "NOT_FOUND_ERROR", retrieved_data: None}
        task_id = 22

        # Agent correctly responds with NOT_FOUND_ERROR and empty retrieved_data
        agent_response = create_agent_response(
            status="NOT_FOUND_ERROR",
            retrieved_data=[],  # Empty array, which normalizes to None
        )

        _, result = evaluate_task(task_id=task_id, agent_response=agent_response)

        # Bug: The evaluator returns error status instead of success
        assert result.status == EvalStatus.ERROR, f"Expected ERROR status due to bug, got {result.status}"
        assert result.score == 0.0, f"Expected score 0.0 due to bug, got {result.score}"

        # Verify the error message is from the bug
        agent_resp_eval = next(
            (e for e in result.evaluators_results if e.evaluator_name == "AgentResponseEvaluator"),
            None,
        )
        assert agent_resp_eval is not None
        assert agent_resp_eval.error_msg is not None
        assert "Expected retrieved_data must be set in config for retrieve tasks" in agent_resp_eval.error_msg

    def test_not_found_retrieve_task_with_null_retrieved_data(
        self,
        evaluate_task,
        create_agent_response,
    ):
        """Same as above but with retrieved_data=None instead of empty array."""
        task_id = 22

        agent_response = create_agent_response(
            status="NOT_FOUND_ERROR",
            retrieved_data=None,
        )

        _, result = evaluate_task(task_id=task_id, agent_response=agent_response)

        # Bug: The evaluator returns error status instead of success
        assert result.status == EvalStatus.ERROR
        assert result.score == 0.0

        agent_resp_eval = next(
            (e for e in result.evaluators_results if e.evaluator_name == "AgentResponseEvaluator"),
            None,
        )
        assert agent_resp_eval is not None
        assert "Expected retrieved_data must be set in config for retrieve tasks" in (agent_resp_eval.error_msg or "")

    def test_not_found_retrieve_task_with_json_response(
        self,
        evaluate_task,
    ):
        """Test with raw JSON string response (as would come from an agent)."""
        task_id = 22

        # This is similar to the example from the issue
        agent_response = json.dumps({
            "task_type": "retrieve",
            "status": "NOT_FOUND_ERROR",
            "retrieved_data": [],
            "error_details": "Searched all reviews and found no matches.",
        })

        _, result = evaluate_task(task_id=task_id, agent_response=agent_response)

        # Bug: The evaluator returns error status instead of success
        assert result.status == EvalStatus.ERROR
        assert result.score == 0.0

        agent_resp_eval = next(
            (e for e in result.evaluators_results if e.evaluator_name == "AgentResponseEvaluator"),
            None,
        )
        assert agent_resp_eval is not None
        assert "Expected retrieved_data must be set in config for retrieve tasks" in (agent_resp_eval.error_msg or "")


class TestIssue5ExpectedBehavior:
    """Tests showing what the CORRECT behavior should be after the fix.

    These tests are marked as xfail because they currently fail due to the bug.
    After the fix, remove the xfail markers and these tests should pass.
    """

    @pytest.mark.xfail(reason="Issue #5: Evaluator incorrectly raises on NOT_FOUND retrieve tasks")
    def test_not_found_retrieve_should_succeed_with_matching_response(
        self,
        evaluate_task,
        create_agent_response,
    ):
        """After fix: NOT_FOUND retrieve task should succeed when agent response matches.

        Expected behavior:
        - If expected.status is NOT_FOUND_ERROR and expected.retrieved_data is None
        - And actual.status is NOT_FOUND_ERROR and actual.retrieved_data is None/empty
        - Then evaluation should SUCCEED with score 1.0
        """
        task_id = 22

        agent_response = create_agent_response(
            status="NOT_FOUND_ERROR",
            retrieved_data=None,
        )

        _, result = evaluate_task(task_id=task_id, agent_response=agent_response)

        # After fix, this should pass
        assert result.status == EvalStatus.SUCCESS
        assert result.score == 1.0

    @pytest.mark.xfail(reason="Issue #5: Evaluator incorrectly raises on NOT_FOUND retrieve tasks")
    def test_not_found_retrieve_should_fail_with_wrong_status(
        self,
        evaluate_task,
        create_agent_response,
    ):
        """After fix: Should fail when agent returns SUCCESS but expected is NOT_FOUND_ERROR."""
        task_id = 22

        # Agent incorrectly returns SUCCESS when NOT_FOUND_ERROR is expected
        agent_response = create_agent_response(
            status="SUCCESS",
            retrieved_data=["some data"],
        )

        _, result = evaluate_task(task_id=task_id, agent_response=agent_response)

        # After fix, this should fail due to status mismatch (not due to ValueError)
        assert result.status == EvalStatus.FAILURE
        assert result.score == 0.0
