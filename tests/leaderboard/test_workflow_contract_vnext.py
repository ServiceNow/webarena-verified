from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_hf_ingest_workflow_uses_sync_script_and_single_writer_concurrency() -> None:
    workflow = _read(".github/workflows/leaderboard-hf-ingest.yml")
    assert "group: leaderboard-data-writer" in workflow
    assert "dev.leaderboard.hf-sync-submissions" in workflow
    assert "python - <<'PY'" not in workflow


def test_hf_publish_workflow_allows_only_vnext_paths() -> None:
    workflow = _read(".github/workflows/leaderboard-hf-publish-pr.yml")
    assert '"submissions/**"' not in workflow
    assert '"submission_records/**"' not in workflow
    assert '"leaderboard/**"' in workflow
    assert '"submission_control/**"' not in workflow


def test_rebuild_workflow_uses_script_entrypoint_without_records_args() -> None:
    workflow = _read(".github/workflows/leaderboard-rebuild.yml")
    assert '--records-dir "submission_records"' not in workflow
    assert "dev.leaderboard.rebuild-and-push" in workflow
