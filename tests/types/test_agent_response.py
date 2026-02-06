"""Unit tests for _FinalAgentResponse Pydantic model.

Tests that _FinalAgentResponse correctly validates nested arrays in retrieved_data.
The type system should allow nested lists to support alternatives in evaluation.
This is the internal model used for loading task expected values.
"""

from webarena_verified.types.agent_response import MainObjectiveType, Status, _FinalAgentResponse


def test_alternatives_pydantic_model_accepts_nested_list():
    """Test that _FinalAgentResponse accepts nested arrays in retrieved_data.

    Scenario: Create _FinalAgentResponse with nested array structure
    Expected: Model validates successfully
    """

    # Create response with nested array
    response = _FinalAgentResponse.model_validate(
        {
            "task_type": "RETRIEVE",
            "status": "SUCCESS",
            "retrieved_data": [["item1", "item2"], ["item3", "item4"]],
        }
    )

    assert response.task_type == MainObjectiveType.RETRIEVE
    assert response.status == Status.SUCCESS
    assert response.retrieved_data == [["item1", "item2"], ["item3", "item4"]]


def test_alternatives_pydantic_model_accepts_single_level_array():
    """Test that _FinalAgentResponse still accepts single-level arrays.

    Scenario: Create _FinalAgentResponse with regular array structure
    Expected: Model validates successfully
    """

    # Create response with regular array
    response = _FinalAgentResponse.model_validate(
        {
            "task_type": "RETRIEVE",
            "status": "SUCCESS",
            "retrieved_data": ["item1", "item2", "item3"],
        }
    )

    assert response.task_type == MainObjectiveType.RETRIEVE
    assert response.status == Status.SUCCESS
    assert response.retrieved_data == ["item1", "item2", "item3"]


def test_backward_compatibility_with_performed_operation():
    """Test that _FinalAgentResponse accepts the old 'performed_operation' field name.

    Scenario: Create _FinalAgentResponse using the deprecated field name
    Expected: Model validates successfully and maps to main_objective_type
    """

    # Create response using old field name
    response = _FinalAgentResponse.model_validate(
        {
            "performed_operation": "NAVIGATE",
            "status": "SUCCESS",
            "retrieved_data": None,
        }
    )

    # Should be accessible via new field name
    assert response.task_type == MainObjectiveType.NAVIGATE
    assert response.status == Status.SUCCESS
    assert response.retrieved_data is None
