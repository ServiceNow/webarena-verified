from __future__ import annotations

from types import SimpleNamespace

import dev.leaderboard.utils.hf_sync as hf_sync


def test_discover_submission_prs_returns_structured_data(monkeypatch):
    calls: list[tuple[str, int, str, str]] = []

    class FakeApi:
        def __init__(self, token: str):
            self.token = token

        def get_repo_discussions(self, repo_id: str, discussion_type: str, discussion_status: str, repo_type: str):
            assert repo_id == "org/repo"
            assert discussion_type == "pull_request"
            assert discussion_status == "open"
            assert repo_type == "dataset"
            return [
                SimpleNamespace(num=11, title="Leaderboard Submission: good", status="open"),
                SimpleNamespace(num=12, title="Not a submission", status="open"),
                # This should be ignored by discover filtering even if returned by mock.
                SimpleNamespace(num=13, title="Leaderboard Submission: closed", status="closed"),
            ]

        def get_discussion_details(self, repo_id: str, discussion_num: int, repo_type: str, token: str):
            calls.append((repo_id, discussion_num, repo_type, token))
            return SimpleNamespace(sha=f"sha-{discussion_num}")

    monkeypatch.setattr(hf_sync, "HfApi", FakeApi)
    monkeypatch.setattr(hf_sync, "_latest_head_sha", lambda details: details.sha)
    monkeypatch.setattr(
        hf_sync,
        "_get_open_submission_prs",
        lambda api, hf_repo: [
            d
            for d in api.get_repo_discussions(
                repo_id=hf_repo,
                repo_type="dataset",
                discussion_type="pull_request",
                discussion_status="open",
            )
            if (d.title or "").startswith("Leaderboard Submission: ") and (d.status or "").lower() == "open"
        ],
    )

    result = hf_sync.discover_submission_prs("org/repo", "token-123")

    assert result["count"] == 1
    assert result["matrix"] == {
        "include": [
            {"hf_pr_id": 11, "hf_head_sha": "sha-11"},
        ]
    }
    assert calls == [
        ("org/repo", 11, "dataset", "token-123"),
    ]
