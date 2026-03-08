from pathlib import Path

HF_INGEST_WORKFLOW_PATH = Path(".github/workflows/leaderboard-hf-ingest.yml")
HF_PUBLISH_WORKFLOW_PATH = Path(".github/workflows/leaderboard-hf-publish-pr.yml")
DOCS_WORKFLOW_PATH = Path(".github/workflows/dev-docs-publish.yml")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_hf_ingest_workflow_is_schedule_only() -> None:
    workflow = _read(HF_INGEST_WORKFLOW_PATH)

    assert "repository_dispatch:" not in workflow
    assert "hf_submission_event" not in workflow
    assert "schedule:" in workflow
    assert "Resolve HF settings" not in workflow
    assert "dev.leaderboard.hf-sync-submissions" in workflow
    assert "WEBARENA_VERIFIED_LEADERBOARD_SUBMISSION_HF_REPO" in workflow
    assert '--hf-repo "$WEBARENA_VERIFIED_LEADERBOARD_SUBMISSION_HF_REPO"' in workflow
    assert "python - <<'PY'" not in workflow


def test_hf_publish_pr_workflow_validates_rebuild_contract() -> None:
    workflow = _read(HF_PUBLISH_WORKFLOW_PATH)

    assert "group: leaderboard-data-writer" in workflow
    assert "dev.leaderboard.hf-publish-pr-gate" in workflow
    assert "python - <<'PY'" not in workflow


def test_docs_publish_trigger_is_independent_from_leaderboard_data() -> None:
    workflow = _read(DOCS_WORKFLOW_PATH)

    assert 'group: "pages"' in workflow
    assert '- "docs/**"' in workflow
    assert '- "mkdocs.yml"' in workflow
    assert "leaderboard_manifest.json" not in workflow
    assert '"submissions/**"' not in workflow
