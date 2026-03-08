from pathlib import Path

SMOKE_WORKFLOW_PATH = Path(".github/workflows/leaderboard-smoke.yml")


def test_smoke_workflow_uses_scripted_check() -> None:
    workflow = SMOKE_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "dev.leaderboard.smoke-check" in workflow
    assert "curl -fsSL" not in workflow
    assert "jq -e" not in workflow
