import json
from pathlib import Path

import pytest

from dev.leaderboard import finalize


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _merged_pr_event() -> dict:
    return {
        "pull_request": {
            "merged": True,
            "number": 42,
            "html_url": "https://github.com/org/repo/pull/42",
            "merge_commit_sha": "abc123",
            "head": {"repo": {"id": 999, "full_name": "fork-owner/repo"}},
            "user": {"id": 77, "login": "alice"},
        }
    }


def test_parse_finalize_event_extracts_required_fields(tmp_path: Path):
    event_path = tmp_path / "event.json"
    _write_json(event_path, _merged_pr_event())

    parsed = finalize.parse_finalize_event(event_path)

    assert parsed.pr_number == 42
    assert parsed.pr_url.endswith("/pull/42")
    assert parsed.source_repository_full_name == "fork-owner/repo"
    assert parsed.github_pr_author_login == "alice"


def test_resolve_single_intake_id_requires_exactly_one():
    changed = [
        "submissions/inbox/intake-1/submission.json",
        "submissions/inbox/intake-1/manifest.json",
    ]
    assert finalize.resolve_single_intake_id(changed) == "intake-1"

    with pytest.raises(finalize.FinalizeError, match="Expected exactly one intake_id"):
        finalize.resolve_single_intake_id(
            [
                "submissions/inbox/intake-1/submission.json",
                "submissions/inbox/intake-2/submission.json",
            ]
        )


def test_finalize_submission_writes_canonical_record_and_deletes_inbox(tmp_path: Path, monkeypatch):
    repo_root = tmp_path
    event_path = repo_root / "event.json"
    _write_json(event_path, _merged_pr_event())

    intake_root = repo_root / "submissions" / "inbox" / "intake-123"
    _write_json(
        intake_root / "submission.json",
        {
            "name": "TeamX/ModelY",
            "leaderboard": "both",
            "reference": "https://example.com/paper",
            "created_at_utc": "2026-03-07T10:00:00Z",
            "packaging_summary": {"tasks_packaged": 2},
        },
    )
    _write_json(
        intake_root / "manifest.json",
        {
            "schema_version": "1.0",
            "created_at_utc": "2026-03-07T10:00:00Z",
            "files": [],
        },
    )

    monkeypatch.setattr(
        finalize,
        "list_merged_pr_changed_files",
        lambda repo, pr_number, token: [
            "submissions/inbox/intake-123/submission.json",
            "submissions/inbox/intake-123/manifest.json",
        ],
    )
    monkeypatch.setattr(
        finalize,
        "run_evaluation",
        lambda repo_root, intake_id, evaluator_version: {
            "overall_score": 0.5,
            "shopping_score": 1.0,
            "reddit_score": 0.0,
            "gitlab_score": 0.0,
            "wikipedia_score": 0.0,
            "map_score": 0.0,
            "shopping_admin_score": 1.0,
            "success_count": 1,
            "failure_count": 1,
            "error_count": 0,
            "missing_count": 0,
            "webarena_verified_version": "1.2.3",
        },
    )
    monkeypatch.setattr(
        finalize,
        "persist_payload_to_hf",
        lambda **kwargs: finalize.HFPersistResult(
            hf_repo=kwargs["hf_repo"],
            hf_path=f"submissions/{kwargs['submission_id']}",
            hf_revision="hf-rev-1",
        ),
    )
    monkeypatch.setattr(finalize, "_now_utc_z", lambda: "2026-03-07T12:00:00Z")

    result = finalize.finalize_submission(
        repo_root=repo_root,
        event_path=event_path,
        github_repo="org/repo",
        github_token="gh",
        hf_repo="org/hf",
        hf_token="hf",
        evaluator_version="",
    )

    canonical_path = repo_root / "submissions" / "42.json"
    assert result.submission_id == 42
    assert canonical_path.exists()
    assert not intake_root.exists()

    canonical_payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    assert canonical_payload["github_pr_number"] == 42
    assert canonical_payload["huggingface_dataset_revision"] == "hf-rev-1"
    assert canonical_payload["submission_id"] == 42
