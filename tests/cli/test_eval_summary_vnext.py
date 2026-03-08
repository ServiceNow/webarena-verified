import json
from pathlib import Path
from unittest.mock import Mock, patch

from webarena_verified.__main__ import eval_tasks
from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.eval import EvalStatus, TaskEvalResult
from webarena_verified.types.task import WebArenaSite


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


def test_eval_tasks_writes_evaluation_summary_file(tmp_path: Path) -> None:
    out = tmp_path / "run"
    (out / "1").mkdir(parents=True)
    (out / "1" / "agent_response.json").write_text("{}", encoding="utf-8")
    (out / "1" / "trace.json").write_text("[]", encoding="utf-8")

    args = Mock(
        task_ids=None,
        output_dir=str(out),
        config=None,
        sites=None,
        task_type=None,
        template_id=None,
        dry_run=False,
        agent_response_transform=None,
        write_evaluation_summary=True,
    )
    cfg = WebArenaVerifiedConfig(
        agent_response_file_name="agent_response.json",
        trace_file_name="trace.json",
        eval_result_file_name="eval_result.json",
    )
    evaluator = Mock()
    evaluator.get_tasks.return_value = []
    evaluator.evaluate_task.return_value = _task_result(1, EvalStatus.SUCCESS, (WebArenaSite.SHOPPING,))

    with (
        patch("webarena_verified.__main__._resolve_config", return_value=cfg),
        patch("webarena_verified.__main__._create_evaluator", return_value=evaluator),
    ):
        code = eval_tasks(args)

    assert code == 0
    summary_path = out / "evaluation_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "scores" in summary
    assert "overall" in summary["scores"]


def test_eval_tasks_rejects_summary_flag_with_task_ids(tmp_path: Path) -> None:
    args = Mock(
        task_ids="1",
        output_dir=str(tmp_path),
        config=None,
        sites=None,
        task_type=None,
        template_id=None,
        dry_run=False,
        agent_response_transform=None,
        write_evaluation_summary=True,
    )
    assert eval_tasks(args) == 1
