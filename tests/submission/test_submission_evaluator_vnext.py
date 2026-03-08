from pathlib import Path

from webarena_verified.submission.models import SubmissionMetadata, SubmissionMode
from webarena_verified.submission.submission_evaluator import SubmissionEvaluator
from webarena_verified.types.agent_response import FinalAgentResponse, MainObjectiveType
from webarena_verified.types.eval import EvalStatus, TaskEvalResult
from webarena_verified.types.task import AgentResponseEvaluatorCfg, WebArenaSite, WebArenaVerifiedTask


def _task_result(task_id: int, status: EvalStatus, sites: tuple[WebArenaSite, ...]) -> TaskEvalResult:
    return TaskEvalResult(
        task_id=task_id,
        intent_template_id=1,
        sites=sites,
        task_revision=1,
        status=status,
        score=1.0 if status == EvalStatus.SUCCESS else 0.0,
        evaluators_results=(),
        webarena_verified_data_checksum="abc",
    )


def _expected_task(task_id: int, sites: tuple[WebArenaSite, ...]) -> WebArenaVerifiedTask:
    expected_response = FinalAgentResponse.model_construct(
        task_type=MainObjectiveType.RETRIEVE,
        status="SUCCESS",
        retrieved_data=None,
    )
    eval_config = AgentResponseEvaluatorCfg.model_construct(
        evaluator="AgentResponseEvaluator",
        expected=expected_response,
        ordered=False,
        results_schema={},
    )
    return WebArenaVerifiedTask.model_construct(
        task_id=task_id,
        intent_template_id=1,
        sites=sites,
        require_reset=False,
        require_login=False,
        eval=(eval_config,),
        intent="Test task",
        intent_template="Test template",
        instantiation_dict={},
        expected_agent_response=expected_response,
        revision=1,
    )


def test_evaluator_uses_expected_denominator_for_partial_full_submission(tmp_path: Path) -> None:
    submission_dir = tmp_path / "submission"
    (submission_dir / "1").mkdir(parents=True)

    evaluator = SubmissionEvaluator()
    evaluator._all_tasks = (
        _expected_task(1, (WebArenaSite.SHOPPING,)),
        _expected_task(2, (WebArenaSite.SHOPPING,)),
    )
    evaluator._all_task_ids = {1, 2}
    evaluator._hard_task_ids = {1, 2}
    setattr(
        evaluator._wa,
        "evaluate_task",
        lambda **_kwargs: _task_result(1, EvalStatus.SUCCESS, (WebArenaSite.SHOPPING,)),
    )

    submission = SubmissionMetadata(
        submission_uid="018f6f54-7e58-7f23-9d16-f4f8072b4f61",
        name="TeamX",
        model="ModelY",
        reference="https://example.com/paper",
        contact_email="team@example.com",
        submitted_tasks=1,
        task_network_filename="network.har",
    )

    summaries = evaluator.evaluate_submission(
        submission_dir=submission_dir,
        submission=submission,
        submission_mode=SubmissionMode.FULL,
    )

    full_summary = summaries[SubmissionMode.FULL]
    assert full_summary.scores.overall == 0.5
    assert full_summary.scores.shopping == 0.5
    assert full_summary.summary.overall.total == 1
    assert full_summary.summary.overall.expected_total == 2
    assert full_summary.summary.overall.missing_count == 1
    assert full_summary.summary.per_site["shopping"].expected_total == 2
    assert full_summary.summary.per_site["shopping"].missing_count == 1
