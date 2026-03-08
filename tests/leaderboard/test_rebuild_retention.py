import json
from pathlib import Path

from leaderboard.scripts.tasks import rebuild_leaderboard_artifacts
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


def _append_submission(repo_root: Path, uid: str, full_score: float, hard_score: float) -> None:
    builder = LeaderboardBuilder()
    builder.apply_submission_result(
        repo_root=repo_root,
        submission_uid=uid,
        submission_mode=SubmissionMode.BOTH,
        source_url=f"https://huggingface.co/datasets/org/dataset/tree/sha/submissions/{uid}",
        submission_name=f"Team-{uid[-4:]}",
        submission_model="model",
        evaluation_summaries={SubmissionMode.FULL: _summary(full_score), SubmissionMode.HARD: _summary(hard_score)},
    )


def test_rebuild_latest_points_to_generated_artifacts(tmp_path: Path) -> None:
    _append_submission(tmp_path, "018f6f54-7e58-7f23-9d16-f4f8072b4f61", 0.9, 0.8)
    result = rebuild_leaderboard_artifacts(branch_root=tmp_path, dry_run=False)

    latest = json.loads((tmp_path / "leaderboard" / "latest.json").read_text(encoding="utf-8"))
    assert latest["generation_id"] == result["generation_id"]
    assert (tmp_path / latest["full_file"]).exists()
    assert (tmp_path / latest["hard_file"]).exists()


def test_rebuild_preserves_ordering_and_ranks(tmp_path: Path) -> None:
    _append_submission(tmp_path, "018f6f54-7e58-7f23-9d16-f4f8072b4f61", 0.7, 0.6)
    _append_submission(tmp_path, "018f6f54-7e58-7f23-9d16-f4f8072b4f62", 0.9, 0.8)
    result = rebuild_leaderboard_artifacts(branch_root=tmp_path, dry_run=False)

    full_payload = json.loads(Path(result["full"]).read_text(encoding="utf-8"))
    hard_payload = json.loads(Path(result["hard"]).read_text(encoding="utf-8"))

    assert [row["rank"] for row in full_payload["rows"]] == [1, 2]
    assert [row["rank"] for row in hard_payload["rows"]] == [1, 2]
    assert full_payload["rows"][0]["overall"] >= full_payload["rows"][1]["overall"]
    assert hard_payload["rows"][0]["overall"] >= hard_payload["rows"][1]["overall"]
