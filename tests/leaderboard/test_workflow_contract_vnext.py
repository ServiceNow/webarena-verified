from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_hf_ingest_workflow_uses_sync_script_and_single_writer_concurrency() -> None:
    workflow = _read(".github/workflows/leaderboard-hf-ingest.yml")
    assert "group: leaderboard-data-writer" in workflow
    assert "dev.leaderboard.hf-sync-submissions" in workflow
    assert "python - <<'PY'" not in workflow


def test_hf_ingest_workflow_pushes_directly_without_publish_pr_stage() -> None:
    workflow = _read(".github/workflows/leaderboard-hf-ingest.yml")
    assert "gh pr create" not in workflow
    assert "git push origin HEAD:leaderboard-submissions" in workflow
