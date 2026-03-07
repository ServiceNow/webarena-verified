from pathlib import Path


SITE_BUILD_WORKFLOW_PATH = Path(".github/workflows/leaderboard-site-build.yml")


def test_site_build_workflow_sets_branch_hosted_manifest_default() -> None:
    workflow = SITE_BUILD_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "PUBLIC_LEADERBOARD_MANIFEST_URL" in workflow
    assert "leaderboard-submissions/leaderboard_manifest.json" in workflow
    assert (
        "https://raw.githubusercontent.com/ServiceNow/webarena-verified/leaderboard-submissions/leaderboard_manifest.json"
        in workflow
    )


def test_site_build_workflow_runs_tests_and_build() -> None:
    workflow = SITE_BUILD_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "Run site tests" in workflow
    assert "npm test" in workflow
    assert "Build site" in workflow
    assert "npm run build" in workflow
