import json
from pathlib import Path

from leaderboard.scripts import hf_ingest


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _dispatch_event(*, event_id: str = "evt-1", head_sha: str = "sha-1") -> dict:
    return {
        "action": "hf_submission_event",
        "client_payload": {
            "event_id": event_id,
            "event_scope": "discussion",
            "event_action": "update",
            "event_ts": "2026-03-07T12:00:00Z",
            "hf_repo": "org/dataset",
            "hf_pr_number": 42,
            "hf_head_sha": head_sha,
            "hf_pr_url": "https://huggingface.co/datasets/org/dataset/discussions/42",
        },
    }


def _write_intake(repo_root: Path) -> None:
    intake_root = repo_root / "submissions" / "inbox" / "pr-42"
    submission_path = intake_root / "submission.json"
    _write_json(
        submission_path,
        {
            "name": "TeamX/ModelY",
            "leaderboard": "both",
            "reference": "https://example.com/paper",
            "created_at_utc": "2026-03-07T10:00:00Z",
            "packaging_summary": {
                "tasks_packaged": 2,
                "tasks_with_issues": 0,
                "duplicate_tasks": 0,
                "unknown_tasks": 0,
                "missing_from_output": 0,
            },
        },
    )
    _write_json(
        intake_root / "manifest.json",
        {
            "schema_version": "1.0",
            "created_at_utc": "2026-03-07T10:00:00Z",
            "files": [
                {
                    "path": "submission.json",
                    "sha256": "a" * 64,
                    "size_bytes": max(submission_path.stat().st_size, 1),
                }
            ],
        },
    )


def test_hf_ingest_writes_control_and_canonical_records(tmp_path: Path, monkeypatch) -> None:
    _write_intake(tmp_path)
    event_path = tmp_path / "event.json"
    _write_json(event_path, _dispatch_event())

    monkeypatch.setattr(
        hf_ingest,
        "_run_hf_evaluation",
        lambda *_args, **_kwargs: hf_ingest.EvaluationSummary(
            overall_score=0.5,
            shopping_score=1.0,
            reddit_score=0.0,
            gitlab_score=0.0,
            wikipedia_score=0.0,
            map_score=0.0,
            shopping_admin_score=1.0,
            success_count=1,
            failure_count=1,
            error_count=0,
            missing_count=0,
            evaluator_version="1.2.3",
        ),
    )
    monkeypatch.setattr(hf_ingest, "_now_utc_z", lambda: "2026-03-07T12:00:00Z")

    monkeypatch.setattr(hf_ingest, "_materialize_hf_payload", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(hf_ingest, "_latest_hf_pr_sha", lambda **_kwargs: "sha-1")
    result = hf_ingest.ingest_hf_submission(
        repo_root=tmp_path,
        event_path=event_path,
        github_repo="org/repo",
        hf_repo_canonical="org/dataset",
        hf_token="hf-token",
        evaluator_version="",
    )

    assert result.submission_id == 42
    assert (tmp_path / "submission_control" / "42.json").exists()
    assert (tmp_path / "submissions" / "42.json").exists()

    control_payload = json.loads((tmp_path / "submission_control" / "42.json").read_text(encoding="utf-8"))
    assert control_payload["status"] == "accepted_pending_publish"
    assert control_payload["processed_event_ids"] == ["evt-1"]

    canonical_payload = json.loads((tmp_path / "submissions" / "42.json").read_text(encoding="utf-8"))
    assert canonical_payload["submission_uid"].endswith("@sha-1")
    assert canonical_payload["hf_pr_number"] == 42
    assert canonical_payload["status"] == "accepted"


def test_hf_ingest_is_idempotent_for_same_event_id(tmp_path: Path, monkeypatch) -> None:
    _write_intake(tmp_path)
    event_path = tmp_path / "event.json"
    _write_json(event_path, _dispatch_event(event_id="evt-1"))

    monkeypatch.setattr(
        hf_ingest,
        "_run_hf_evaluation",
        lambda *_args, **_kwargs: hf_ingest.EvaluationSummary(
            overall_score=1.0,
            shopping_score=1.0,
            reddit_score=1.0,
            gitlab_score=1.0,
            wikipedia_score=1.0,
            map_score=1.0,
            shopping_admin_score=1.0,
            success_count=1,
            failure_count=0,
            error_count=0,
            missing_count=0,
            evaluator_version="1.2.3",
        ),
    )
    monkeypatch.setattr(hf_ingest, "_now_utc_z", lambda: "2026-03-07T12:00:00Z")

    monkeypatch.setattr(hf_ingest, "_materialize_hf_payload", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(hf_ingest, "_latest_hf_pr_sha", lambda **_kwargs: "sha-1")
    hf_ingest.ingest_hf_submission(
        repo_root=tmp_path,
        event_path=event_path,
        github_repo="org/repo",
        hf_repo_canonical="org/dataset",
        hf_token="hf-token",
        evaluator_version="",
    )
    control_before = (tmp_path / "submission_control" / "42.json").read_text(encoding="utf-8")

    hf_ingest.ingest_hf_submission(
        repo_root=tmp_path,
        event_path=event_path,
        github_repo="org/repo",
        hf_repo_canonical="org/dataset",
        hf_token="hf-token",
        evaluator_version="",
    )
    control_after = (tmp_path / "submission_control" / "42.json").read_text(encoding="utf-8")

    assert control_before == control_after
