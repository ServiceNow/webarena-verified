from pathlib import Path


REBUILD_WORKFLOW_PATH = Path(".github/workflows/leaderboard-rebuild.yml")
HF_INGEST_WORKFLOW_PATH = Path(".github/workflows/leaderboard-hf-ingest.yml")
HF_PUBLISH_WORKFLOW_PATH = Path(".github/workflows/leaderboard-hf-publish-pr.yml")
DOCS_WORKFLOW_PATH = Path(".github/workflows/dev-docs-publish.yml")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_rebuild_workflow_has_single_writer_concurrency_contract() -> None:
    workflow = _read(REBUILD_WORKFLOW_PATH)

    assert "concurrency:" in workflow
    assert "group: leaderboard-data-writer" in workflow
    assert "cancel-in-progress: false" in workflow
    assert 'group: "pages"' not in workflow


def test_rebuild_workflow_is_manual_only_on_leaderboard_submissions_branch() -> None:
    workflow = _read(REBUILD_WORKFLOW_PATH)

    assert "workflow_run:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "github.ref_name == 'leaderboard-submissions'" in workflow


def test_hf_ingest_workflow_supports_dispatch_and_schedule() -> None:
    workflow = _read(HF_INGEST_WORKFLOW_PATH)

    assert "repository_dispatch:" in workflow
    assert "- hf_submission_event" in workflow
    assert "schedule:" in workflow
    assert "inv dev.leaderboard.hf-ingest" in workflow


def test_hf_publish_pr_workflow_validates_rebuild_contract() -> None:
    workflow = _read(HF_PUBLISH_WORKFLOW_PATH)

    assert "group: leaderboard-data-writer" in workflow
    assert "inv dev.leaderboard.rebuild-canonical" in workflow
    assert "--dry-run" in workflow


def test_docs_publish_trigger_is_independent_from_leaderboard_data() -> None:
    workflow = _read(DOCS_WORKFLOW_PATH)

    assert 'group: "pages"' in workflow
    assert '- "docs/**"' in workflow
    assert '- "mkdocs.yml"' in workflow
    assert "leaderboard_manifest.json" not in workflow
    assert '"submissions/**"' not in workflow
