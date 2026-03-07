"""Unit tests for _FinalAgentResponse Pydantic model.

Tests that _FinalAgentResponse correctly validates nested arrays in retrieved_data.
The type system should allow nested lists to support alternatives in evaluation.
This is the internal model used for loading task expected values.
"""

import pytest
from pydantic import ValidationError

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


def test_task_type_alias_precedence_prefers_task_type_when_both_present():
    """If both fields are provided, explicit task_type should win over legacy alias."""
    response = _FinalAgentResponse.model_validate(
        {
            "task_type": "retrieve",
            "performed_operation": "navigate",
            "status": "success",
            "retrieved_data": None,
        }
    )

    assert response.task_type == MainObjectiveType.RETRIEVE
    assert response.status == Status.SUCCESS


def test_missing_task_type_and_alias_raises_validation_error():
    """Model should fail fast when neither task_type nor performed_operation is provided."""
    with pytest.raises(ValidationError, match="task_type"):
        _FinalAgentResponse.model_validate(
            {
                "status": "SUCCESS",
                "retrieved_data": None,
            }
        )


def test_invalid_status_value_raises_validation_error():
    """Model should reject unknown status values."""
    with pytest.raises(ValidationError, match="status"):
        _FinalAgentResponse.model_validate(
            {
                "task_type": "RETRIEVE",
                "status": "COMPLETED",
                "retrieved_data": None,
            }
        )


def test_invalid_retrieved_data_shape_raises_validation_error():
    """retrieved_data must be a list or null, not a plain object."""
    with pytest.raises(ValidationError, match="retrieved_data"):
        _FinalAgentResponse.model_validate(
            {
                "task_type": "RETRIEVE",
                "status": "SUCCESS",
                "retrieved_data": {"item": "value"},
            }
        )
