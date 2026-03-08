import json
from pathlib import Path

from leaderboard.scripts.publish import rebuild_leaderboard_artifacts
from webarena_verified.submission.leaderboard_builder import LeaderboardBuilder
from webarena_verified.submission.models import EvaluationSummaryPayload, SubmissionMode


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


def test_rebuild_dry_run_does_not_modify_tree(tmp_path: Path) -> None:
    _seed_submission(tmp_path)
    latest_path = tmp_path / "leaderboard" / "latest.json"
    before = latest_path.read_text(encoding="utf-8")

    result = rebuild_leaderboard_artifacts(branch_root=tmp_path, dry_run=True)

    assert result == {"mode": "dry_run"}
    assert latest_path.read_text(encoding="utf-8") == before


def test_rebuild_is_deterministic_for_existing_rows(tmp_path: Path) -> None:
    _seed_submission(tmp_path)

    result_one = rebuild_leaderboard_artifacts(branch_root=tmp_path, dry_run=False)
    latest_one = json.loads((tmp_path / "leaderboard" / "latest.json").read_text(encoding="utf-8"))
    full_one = Path(result_one["full"]).read_text(encoding="utf-8")
    hard_one = Path(result_one["hard"]).read_text(encoding="utf-8")

    result_two = rebuild_leaderboard_artifacts(branch_root=tmp_path, dry_run=False)
    latest_two = json.loads((tmp_path / "leaderboard" / "latest.json").read_text(encoding="utf-8"))

    assert result_one["generation_id"] == result_two["generation_id"]
    assert latest_one["generation_id"] == latest_two["generation_id"]
    assert Path(result_two["full"]).read_text(encoding="utf-8") == full_one
    assert Path(result_two["hard"]).read_text(encoding="utf-8") == hard_one
