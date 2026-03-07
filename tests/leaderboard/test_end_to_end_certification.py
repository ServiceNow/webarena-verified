import hashlib
import json
from pathlib import Path

import dev.leaderboard.pr_gate_intake_validator as pr_gate
from dev.leaderboard import finalize
from dev.leaderboard.publish import publish_from_canonical
from webarena_verified.types.leaderboard import LeaderboardManifest, LeaderboardTableFile


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _create_intake(repo_root: Path, intake_id: str) -> Path:
    intake_root = repo_root / "submissions" / "inbox" / intake_id

    _write_json(
        intake_root / "submission.json",
        {
            "name": "TeamX/ModelY",
            "leaderboard": "both",
            "reference": "https://example.com/paper",
            "created_at_utc": "2026-03-07T12:00:00Z",
            "packaging_summary": {
                "tasks_packaged": 1,
                "tasks_with_issues": 0,
                "duplicate_tasks": 0,
                "unknown_tasks": 0,
                "missing_from_output": 0,
            },
        },
    )
    _write_json(intake_root / "tasks" / "1" / "agent_response.json", {"ok": True})
    _write_json(intake_root / "tasks" / "1" / "network.har", {"log": {"entries": []}})

    declared_files = [
        "submission.json",
        "tasks/1/agent_response.json",
        "tasks/1/network.har",
    ]
    manifest_files = []
    for relative_path in declared_files:
        target = intake_root / relative_path
        manifest_files.append(
            {
                "path": relative_path,
                "sha256": _sha256_file(target),
                "size_bytes": target.stat().st_size,
            }
        )

    _write_json(
        intake_root / "manifest.json",
        {
            "created_at_utc": "2026-03-07T12:00:00Z",
            "schema_version": "1.0",
            "files": manifest_files,
        },
    )
    return intake_root


def _merged_pr_event(pr_number: int) -> dict:
    return {
        "pull_request": {
            "merged": True,
            "number": pr_number,
            "html_url": f"https://github.com/org/repo/pull/{pr_number}",
            "merge_commit_sha": "abc123",
            "head": {"repo": {"id": 999, "full_name": "fork-owner/repo"}},
            "user": {"id": 77, "login": "alice"},
        }
    }


def test_g08_end_to_end_certification_flow(monkeypatch, tmp_path: Path):
    repo_root = tmp_path
    intake_id = "intake-42"
    submission_id = 42
    _create_intake(repo_root, intake_id)

    changed_paths = [
        f"submissions/inbox/{intake_id}/submission.json",
        f"submissions/inbox/{intake_id}/manifest.json",
        f"submissions/inbox/{intake_id}/tasks/1/agent_response.json",
        f"submissions/inbox/{intake_id}/tasks/1/network.har",
    ]

    monkeypatch.setattr(pr_gate, "_run_git_diff_paths", lambda **_: changed_paths)
    gate_result = pr_gate.run_pr_gate_intake_validation(repo_root, base_sha="base", head_sha="head")
    assert gate_result.intake_id == intake_id
    assert gate_result.score_preview.success_count == 1

    event_path = repo_root / "event.json"
    _write_json(event_path, _merged_pr_event(submission_id))

    monkeypatch.setattr(finalize, "list_merged_pr_changed_files", lambda *_: changed_paths)
    monkeypatch.setattr(
        finalize,
        "run_evaluation",
        lambda *_args, **_kwargs: {
            "overall_score": 1.0,
            "shopping_score": 1.0,
            "reddit_score": 1.0,
            "gitlab_score": 1.0,
            "wikipedia_score": 1.0,
            "map_score": 1.0,
            "shopping_admin_score": 1.0,
            "success_count": 1,
            "failure_count": 0,
            "error_count": 0,
            "missing_count": 0,
            "evaluator_version": "1.2.3",
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

    finalize_result = finalize.finalize_submission(
        repo_root=repo_root,
        event_path=event_path,
        github_repo="org/repo",
        github_token="gh-token",
        hf_repo="org/hf-repo",
        hf_token="hf-token",
        evaluator_version="1.2.3",
    )

    canonical_path = repo_root / "submissions" / f"{submission_id}.json"
    assert finalize_result.submission_id == submission_id
    assert canonical_path.exists()
    assert not (repo_root / "submissions" / "inbox" / intake_id).exists()

    manifest = publish_from_canonical(
        branch_root=repo_root,
        canonical_dir=repo_root / "submissions",
        staging_dir=repo_root / ".tmp" / "leaderboard-staging",
        max_canonical_records=100,
        generation_id="gen-g08",
        generated_at_utc="2026-03-07T12:00:00Z",
    )

    manifest_payload = json.loads((repo_root / "leaderboard_manifest.json").read_text(encoding="utf-8"))
    LeaderboardManifest.model_validate(manifest_payload)
    assert manifest_payload["generation_id"] == manifest.generation_id

    full_path = repo_root / manifest.full_file
    hard_path = repo_root / manifest.hard_file
    assert full_path.exists()
    assert hard_path.exists()

    full_payload = json.loads(full_path.read_text(encoding="utf-8"))
    hard_payload = json.loads(hard_path.read_text(encoding="utf-8"))
    LeaderboardTableFile.model_validate(full_payload)
    LeaderboardTableFile.model_validate(hard_payload)
    assert full_payload["rows"][0]["submission_id"] == submission_id
    assert hard_payload["rows"][0]["submission_id"] == submission_id
