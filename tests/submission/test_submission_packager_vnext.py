import json
from pathlib import Path

from webarena_verified.submission import SubmissionPackager
from webarena_verified.submission.models import SubmissionMode
from webarena_verified.types.config import WebArenaVerifiedConfig


def test_packager_ignores_local_evaluator_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    task_dir = run_dir / "101"
    task_dir.mkdir(parents=True)
    (task_dir / "agent_response.json").write_text('{"ok":true}', encoding="utf-8")
    (task_dir / "network.har").write_text('{"log":{"entries":[]}}', encoding="utf-8")
    (task_dir / "eval_result.json").write_text("{}", encoding="utf-8")
    (run_dir / "evaluation_summary.json").write_text("{}", encoding="utf-8")

    output_dir = tmp_path / "submission"
    packager = SubmissionPackager(
        run_output_dirs=[run_dir],
        evaluator_config=WebArenaVerifiedConfig(
            agent_response_file_name="agent_response.json",
            trace_file_name="network.har",
            eval_result_file_name="eval_result.json",
        ),
    )
    result = packager.create_package(output_dir=output_dir, mode=SubmissionMode.FULL)

    assert result.tasks_packaged == [101]
    assert not (output_dir / "101" / "eval_result.json").exists()
    assert not (output_dir / "evaluation_summary.json").exists()

    payload = json.loads((output_dir / "submission.json").read_text(encoding="utf-8"))
    assert payload["submitted_tasks"] == 1
    assert payload["task_network_filename"] == "network.har"
