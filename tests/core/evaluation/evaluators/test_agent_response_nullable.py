from types import SimpleNamespace

import pytest

from webarena_verified.core.evaluation.evaluators.agent_response_evaluator import AgentResponseEvaluator
from webarena_verified.types.eval import EvalStatus
from webarena_verified.types.task import AgentResponseEvaluatorCfg


@pytest.fixture
def evaluator_config():
    return AgentResponseEvaluatorCfg(
        expected={"task_type": "RETRIEVE", "status": "NOT_FOUND_ERROR", "retrieved_data": None},
        results_schema={"type": "null"},
    )


def _evaluate(config, response):
    # Synthetic context: no fixture, browser, network, or historical response is used.
    context = SimpleNamespace(
        task=SimpleNamespace(task_id=0, is_retrieve_task=True, sites=[]),
        config=SimpleNamespace(derender_url=lambda value, **kwargs: value),
        agent_response_raw=response,
    )
    return AgentResponseEvaluator().evaluate(context=context, config=config)


@pytest.mark.parametrize("data", [None, []])
def test_null_schema_accepts_existing_empty_data_policy(evaluator_config, data):
    result = _evaluate(
        evaluator_config,
        {"task_type": "RETRIEVE", "status": "NOT_FOUND_ERROR", "retrieved_data": data},
    )
    assert result.status == EvalStatus.SUCCESS
    assert result.score == 1.0
    assert result.error_msg is None
    assert result.expected["retrieved_data"] is None


def test_null_schema_accepts_existing_missing_data_policy(evaluator_config):
    result = _evaluate(evaluator_config, {"task_type": "RETRIEVE", "status": "NOT_FOUND_ERROR"})
    assert result.status == EvalStatus.SUCCESS
    assert result.score == 1.0


@pytest.mark.parametrize("status", ["NOT_FOUND_ERROR", "SUCCESS"])
@pytest.mark.parametrize("data", [["unexpected"], [{"review": "unexpected"}], [None], "unexpected", 0, False])
def test_null_schema_unexpected_data_is_failure_not_error(evaluator_config, status, data):
    result = _evaluate(evaluator_config, {"task_type": "RETRIEVE", "status": status, "retrieved_data": data})
    assert result.status == EvalStatus.FAILURE
    assert result.score == 0.0
    assert result.error_msg is None
    assert result.actual_normalized["retrieved_data"] is not None
    assert result.expected["retrieved_data"] is None
    assert any(assertion.assertion_name == "retrieved_data_unexpected" for assertion in result.assertions)


def test_null_data_does_not_hide_wrong_status(evaluator_config):
    result = _evaluate(evaluator_config, {"task_type": "RETRIEVE", "status": "SUCCESS", "retrieved_data": None})
    assert result.status == EvalStatus.FAILURE
    assert result.score == 0.0
    assert result.error_msg is None


def test_null_schema_still_rejects_nonempty_expected_data():
    config = AgentResponseEvaluatorCfg(
        expected={"task_type": "RETRIEVE", "status": "SUCCESS", "retrieved_data": ["invalid oracle"]},
        results_schema={"type": "null"},
    )
    result = _evaluate(config, {"task_type": "RETRIEVE", "status": "SUCCESS", "retrieved_data": None})
    assert result.status == EvalStatus.ERROR
    assert "Null results schema expects no retrieved_data" in result.error_msg


@pytest.mark.parametrize(
    ("data", "expected_status"),
    [(["example"], EvalStatus.SUCCESS), (["different"], EvalStatus.FAILURE), (None, EvalStatus.FAILURE)],
)
def test_array_schema_normalization_is_unchanged(data, expected_status):
    config = AgentResponseEvaluatorCfg(
        expected={"task_type": "RETRIEVE", "status": "SUCCESS", "retrieved_data": ["Example"]},
        results_schema={"type": "array", "items": {"type": "string"}},
    )
    result = _evaluate(config, {"task_type": "RETRIEVE", "status": "SUCCESS", "retrieved_data": data})
    assert result.status == expected_status
    assert result.error_msg is None
