import json
from pathlib import Path

from leaderboard.scripts.leaderboard_builder import LeaderboardBuilder
from leaderboard.scripts.models import EvaluationSummaryPayload
from webarena_verified.submission.config import SubmissionFlowConfig
from webarena_verified.submission.models import SubmissionMode


def _summary(score: float) -> EvaluationSummaryPayload:
    return EvaluationSummaryPayload.model_validate(
        {
            "timestamp": "2026-03-08T10:00:00Z",
            "webarena_verified_version": "1.0.0",
            "webarena_verified_evaluator_checksum": "x",
            "webarena_verified_data_checksum": "y",
            "summary": {
                "overall": {
                    "total": 1,
                    "success_count": 1,
                    "failure_count": 0,
                    "error_count": 0,
                    "failed_or_error_count": 0,
                },
                "per_site": {},
            },
            "scores": {
                "overall": score,
                "shopping": score,
                "shopping_admin": score,
                "gitlab": score,
                "map": score,
                "reddit": score,
                "multisite": score,
                "gitlab_reddit": score,
            },
        }
    )


def _seed_submission(repo_root: Path) -> None:
    builder = LeaderboardBuilder()
    builder.apply_submission_result(
        repo_root=repo_root,
        submission_uid="018f6f54-7e58-7f23-9d16-f4f8072b4f61",
        submission_mode=SubmissionMode.BOTH,
        source_url="https://huggingface.co/datasets/org/dataset/tree/sha/submissions/018f6f54-7e58-7f23-9d16-f4f8072b4f61",
        submission_name="TeamA",
        submission_model="model-a",
        evaluation_summaries={SubmissionMode.FULL: _summary(0.9), SubmissionMode.HARD: _summary(0.8)},
    )


def _rebuild(repo_root: Path) -> dict[str, str]:
    builder = LeaderboardBuilder(SubmissionFlowConfig())
    latest_path, full_path, hard_path = builder.rebuild_leaderboard(repo_root=repo_root)
    latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
    return {
        "generation_id": latest_payload["generation_id"],
        "latest": str(latest_path),
        "full": str(full_path),
        "hard": str(hard_path),
    }


def test_rebuild_dry_run_does_not_modify_tree(tmp_path: Path) -> None:
    _seed_submission(tmp_path)
    latest_path = tmp_path / "leaderboard" / "latest.json"
    before = latest_path.read_text(encoding="utf-8")

    _rebuild(tmp_path)
    after = latest_path.read_text(encoding="utf-8")

    assert json.loads(before)["generation_id"] == json.loads(after)["generation_id"]


def test_rebuild_is_deterministic_for_existing_rows(tmp_path: Path) -> None:
    _seed_submission(tmp_path)

    result_one = _rebuild(tmp_path)
    latest_one = json.loads((tmp_path / "leaderboard" / "latest.json").read_text(encoding="utf-8"))
    full_one = Path(result_one["full"]).read_text(encoding="utf-8")
    hard_one = Path(result_one["hard"]).read_text(encoding="utf-8")
    full_one_payload = json.loads(full_one)
    hard_one_payload = json.loads(hard_one)

    result_two = _rebuild(tmp_path)
    latest_two = json.loads((tmp_path / "leaderboard" / "latest.json").read_text(encoding="utf-8"))
    full_two_payload = json.loads(Path(result_two["full"]).read_text(encoding="utf-8"))
    hard_two_payload = json.loads(Path(result_two["hard"]).read_text(encoding="utf-8"))

    assert result_one["generation_id"] == result_two["generation_id"]
    assert latest_one["generation_id"] == latest_two["generation_id"]
    assert latest_one["generated_at_utc"] == latest_two["generated_at_utc"]
    assert full_one_payload["generated_at_utc"] == full_two_payload["generated_at_utc"]
    assert hard_one_payload["generated_at_utc"] == hard_two_payload["generated_at_utc"]
    assert Path(result_two["full"]).read_text(encoding="utf-8") == full_one
    assert Path(result_two["hard"]).read_text(encoding="utf-8") == hard_one
