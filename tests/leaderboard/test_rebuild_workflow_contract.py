from pathlib import Path

HF_INGEST_WORKFLOW_PATH = Path(".github/workflows/leaderboard-hf-ingest.yml")
DEPLOY_SITE_WORKFLOW_PATH = Path(".github/workflows/deploy-site.yml")


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


def test_deploy_site_workflow_triggers_on_docs_and_leaderboard_changes() -> None:
    workflow = _read(DEPLOY_SITE_WORKFLOW_PATH)

    assert '- "docs/**"' in workflow
    assert '- "mkdocs.yml"' in workflow
    assert '- "leaderboard/site/**"' in workflow
    assert 'group: "pages"' in workflow


def test_deploy_site_workflow_builds_docs_and_leaderboard() -> None:
    workflow = _read(DEPLOY_SITE_WORKFLOW_PATH)

    # Docs: mike deploy without --push (worktree handles the push)
    assert "mike deploy" in workflow
    assert "mike deploy --push" not in workflow

    # Leaderboard: npm build + manifest resolution
    assert "npm run build" in workflow
    assert "PUBLIC_LEADERBOARD_MANIFEST_URL" in workflow
    assert "dev.leaderboard.site-resolve-manifest-url" in workflow


def test_deploy_site_workflow_uses_worktree_inject() -> None:
    workflow = _read(DEPLOY_SITE_WORKFLOW_PATH)

    assert "git worktree add" in workflow
    assert "gh-pages" in workflow
    assert "cp -r leaderboard/site/dist" in workflow
