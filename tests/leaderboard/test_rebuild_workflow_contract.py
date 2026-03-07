from pathlib import Path


REBUILD_WORKFLOW_PATH = Path(".github/workflows/leaderboard-rebuild.yml")
DOCS_WORKFLOW_PATH = Path(".github/workflows/dev-docs-publish.yml")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_rebuild_workflow_has_single_writer_concurrency_contract() -> None:
    workflow = _read(REBUILD_WORKFLOW_PATH)

    assert "concurrency:" in workflow
    assert "group: leaderboard-data-writer" in workflow
    assert "cancel-in-progress: false" in workflow
    assert 'group: "pages"' not in workflow


def test_rebuild_workflow_runs_after_finalize_success() -> None:
    workflow = _read(REBUILD_WORKFLOW_PATH)

    assert "workflow_run:" in workflow
    assert "- Leaderboard Finalize" in workflow
    assert "- completed" in workflow
    assert "- leaderboard-submissions" in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow


def test_docs_publish_trigger_is_independent_from_leaderboard_data() -> None:
    workflow = _read(DOCS_WORKFLOW_PATH)

    assert 'group: "pages"' in workflow
    assert '- "docs/**"' in workflow
    assert '- "mkdocs.yml"' in workflow
    assert "leaderboard_manifest.json" not in workflow
    assert '"submissions/**"' not in workflow
