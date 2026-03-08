from pathlib import Path

from leaderboard.scripts import hf_publish_pr


def test_path_allowlist_is_leaderboard_only() -> None:
    assert hf_publish_pr._path_is_allowlisted("leaderboard/latest.json")
    assert hf_publish_pr._path_is_allowlisted("leaderboard/generations/gen-1/full.json")
    assert hf_publish_pr._path_is_allowlisted("leaderboard/generations/gen-1/hard.json")
    assert not hf_publish_pr._path_is_allowlisted("submissions/uid/submission.json")
    assert not hf_publish_pr._path_is_allowlisted("submission_records/uid.json")


def test_publish_gate_runs_rebuild_and_path_checks(monkeypatch, tmp_path: Path) -> None:
    called: dict[str, object] = {}

    def fake_overlay(**kwargs):
        called["overlay"] = kwargs
        return "sha-head"

    def fake_rebuild(**kwargs):
        called["rebuild"] = kwargs
        return {"generation_id": "gen-1"}

    def fake_allowlist(**kwargs):
        called["allowlist"] = kwargs

    def fake_idempotent(**kwargs):
        called["idempotent"] = kwargs

    monkeypatch.setattr(hf_publish_pr, "_overlay_pr_head_data", fake_overlay)
    monkeypatch.setattr(hf_publish_pr, "rebuild_leaderboard_artifacts", fake_rebuild)
    monkeypatch.setattr(hf_publish_pr, "_ensure_rebuild_is_idempotent", fake_idempotent)
    monkeypatch.setattr(hf_publish_pr, "_enforce_allowlisted_changed_paths", fake_allowlist)

    result = hf_publish_pr._run_hf_publish_pr_gate(
        repo_root=tmp_path,
        pr_number=42,
        base_branch="leaderboard-submissions",
    )

    assert result == "sha-head"
    assert called["overlay"] == {"repo_root": tmp_path, "pr_number": 42}
    assert called["rebuild"] == {"branch_root": tmp_path, "dry_run": False}
    assert called["idempotent"] == {"repo_root": tmp_path}
    assert called["allowlist"] == {
        "repo_root": tmp_path,
        "base_branch": "leaderboard-submissions",
        "pr_head_sha": "sha-head",
    }
