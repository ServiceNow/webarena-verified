import json
from pathlib import Path

from leaderboard.scripts.leaderboard_builder import LeaderboardBuilder
from leaderboard.scripts.models import EvaluationSummaryPayload
from webarena_verified.submission.models import SubmissionMode


def _summary() -> EvaluationSummaryPayload:
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
                "overall": 1.0,
                "shopping": 1.0,
                "shopping_admin": 0.0,
                "gitlab": 0.0,
                "map": 0.0,
                "reddit": 0.0,
                "multisite": 0.0,
                "gitlab_reddit": 0.0,
            },
        }
    )


def _summary_with_overall(overall: float) -> EvaluationSummaryPayload:
    payload = _summary().model_dump(mode="json")
    payload["scores"]["overall"] = overall
    return EvaluationSummaryPayload.model_validate(payload)


def test_leaderboard_builder_writes_latest_and_generation_files(tmp_path: Path) -> None:
    builder = LeaderboardBuilder()
    latest, full, hard = builder.apply_submission_result(
        repo_root=tmp_path,
        submission_uid="018f6f54-7e58-7f23-9d16-f4f8072b4f61",
        submission_mode=SubmissionMode.BOTH,
        source_url="https://huggingface.co/datasets/org/dataset/tree/abc123/submissions/018f6f54-7e58-7f23-9d16-f4f8072b4f61",
        submission_name="TeamX-ModelY",
        submission_model="gpt-4.1-mini",
        evaluation_summaries={
            SubmissionMode.FULL: _summary_with_overall(1.0),
            SubmissionMode.HARD: _summary_with_overall(0.5),
        },
    )

    assert latest == tmp_path / "leaderboard" / "latest.json"
    assert full.name == "full.json"
    assert hard.name == "hard.json"
    assert not (tmp_path / "leaderboard" / "meta.json").exists()

    latest_payload = json.loads(latest.read_text(encoding="utf-8"))
    assert latest_payload["full_file"].endswith("/full.json")
    assert latest_payload["hard_file"].endswith("/hard.json")
    assert len(latest_payload["checksum"]) == 64

    full_payload = json.loads(full.read_text(encoding="utf-8"))
    hard_payload = json.loads(hard.read_text(encoding="utf-8"))
    assert full_payload["leaderboard"] == "full"
    assert hard_payload["leaderboard"] == "hard"
    assert full_payload["rows"][0]["overall"] == 1.0
    assert hard_payload["rows"][0]["overall"] == 0.5
