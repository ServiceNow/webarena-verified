from __future__ import annotations

from types import SimpleNamespace

import dev.leaderboard.utils.hf_sync as hf_sync


def test_discover_submission_prs_returns_structured_data(monkeypatch):
    calls: list[tuple[str, int, str, str]] = []

    class FakeApi:
        def __init__(self, token: str):
            self.token = token

        def get_discussion_details(self, repo_id: str, discussion_num: int, repo_type: str, token: str):
            calls.append((repo_id, discussion_num, repo_type, token))
            return SimpleNamespace(sha=f"sha-{discussion_num}")

    monkeypatch.setattr(hf_sync, "HfApi", FakeApi)
    monkeypatch.setattr(
        hf_sync,
        "_get_open_submission_prs",
        lambda api, hf_repo: [SimpleNamespace(num=11), SimpleNamespace(num=22)],
    )
    monkeypatch.setattr(hf_sync, "_latest_head_sha", lambda details: details.sha)

    result = hf_sync.discover_submission_prs("org/repo", "token-123")

    assert result["count"] == 2
    assert result["matrix"] == {
        "include": [
            {"hf_pr_id": 11, "hf_head_sha": "sha-11"},
            {"hf_pr_id": 22, "hf_head_sha": "sha-22"},
        ]
    }
    assert calls == [
        ("org/repo", 11, "dataset", "token-123"),
        ("org/repo", 22, "dataset", "token-123"),
    ]
