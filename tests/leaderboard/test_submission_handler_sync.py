from pathlib import Path
from types import SimpleNamespace

import pytest

from leaderboard.scripts import submission_data_backend, submission_handler


def test_sync_submissions_processes_recent_hf_refs(tmp_path: Path, monkeypatch) -> None:
    class FakeHfApi:
        def __init__(self, token=None) -> None:
            self.token = token

        def list_repo_refs(self, repo_id: str, repo_type: str):
            assert repo_id == "org/dataset"
            assert repo_type == "dataset"
            return SimpleNamespace(
                pull_requests=[
                    SimpleNamespace(ref="refs/pr/1", target_commit="sha-1"),
                    SimpleNamespace(ref="refs/pr/5", target_commit="sha-5"),
                ]
            )

    ingest_calls: list[dict] = []

    def fake_ingest(**kwargs):
        ingest_calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(submission_data_backend, "HfApi", FakeHfApi)
    monkeypatch.setattr(submission_handler, "ingest_hf_submission", fake_ingest)

    synced = submission_handler.sync_submissions(
        repo_root=tmp_path,
        hf_repo="org/dataset",
        hf_token="hf-token",
        max_recent_refs=1,
    )

    assert synced == [5]
    assert ingest_calls[0]["hf_pr_number"] == 5
    assert ingest_calls[0]["hf_repo"] == "org/dataset"
    assert ingest_calls[0]["hf_head_sha"] == "sha-5"


def test_sync_submissions_requires_hf_repo_and_hf_token(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="hf_repo and hf_token are required"):
        submission_handler.sync_submissions(
            repo_root=tmp_path,
            hf_repo="",
            hf_token="",
        )


def test_sync_submissions_rejects_invalid_max_recent_refs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_recent_refs must be >= 1"):
        submission_handler.sync_submissions(
            repo_root=tmp_path,
            hf_repo="org/dataset",
            hf_token="hf-token",
            max_recent_refs=0,
        )
