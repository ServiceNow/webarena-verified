import json
from urllib import error as urlerror
from pathlib import Path

import pytest

from leaderboard.scripts import finalize


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


def test_resolve_single_intake_id_rejects_out_of_scope_paths():
    with pytest.raises(finalize.FinalizeError, match="Out-of-scope paths"):
        finalize.resolve_single_intake_id(
            [
                "submissions/inbox/intake-1/submission.json",
                "README.md",
            ]
        )


def test_list_merged_pr_changed_files_preserves_owner_repo_path(monkeypatch):
    captured: dict[str, str] = {}

    def _fake_get(url: str, token: str):
        captured["url"] = url
        return []

    monkeypatch.setattr(finalize, "_http_get_json", _fake_get)

    result = finalize.list_merged_pr_changed_files("owner/repo", 42, "token")

    assert result == []
    assert "/repos/owner/repo/pulls/42/files" in captured["url"]


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
    assert canonical_payload["hf_revision"] == "hf-rev-1"
    assert canonical_payload["status"] == "accepted"
    assert canonical_payload["submission_id"] == 42


def test_http_get_json_retries_on_transient_errors(monkeypatch):
    calls = {"count": 0}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true}'

    def _fake_urlopen(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise urlerror.URLError("temporary network error")
        return _Response()

    monkeypatch.setattr(finalize.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(finalize.time, "sleep", lambda _seconds: None)

    payload = finalize._http_get_json("https://example.com", "")
    assert payload == {"ok": True}
    assert calls["count"] == 3


def test_persist_payload_to_hf_retries_transient_errors(tmp_path: Path, monkeypatch):
    intake_root = tmp_path / "submissions" / "inbox" / "intake-1"
    intake_root.mkdir(parents=True, exist_ok=True)
    (intake_root / "submission.json").write_text("{}", encoding="utf-8")

    calls = {"count": 0}

    class _CommitInfo:
        oid = "hf-rev-123"

    class _FakeHfApi:
        def __init__(self, token):
            self.token = token

        def upload_folder(self, **_kwargs):
            calls["count"] += 1
            if calls["count"] < 3:
                raise RuntimeError("transient hf error")
            return _CommitInfo()

    monkeypatch.setattr(finalize, "HfApi", _FakeHfApi)
    monkeypatch.setattr(finalize.time, "sleep", lambda _seconds: None)

    result = finalize.persist_payload_to_hf(
        repo_root=tmp_path,
        intake_id="intake-1",
        submission_id=42,
        hf_repo="owner/dataset",
        hf_token="hf-token",
    )

    assert result.hf_revision == "hf-rev-123"
    assert calls["count"] == 3
