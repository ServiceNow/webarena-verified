import datetime as dt

import pytest

from dev.leaderboard import submission_pr_validator as validator


def test_validate_changed_files_accepts_single_control_json_change():
    changed = [validator.ChangedFile(status="A", path="leaderboard/data/submissions/pending/sub-123.json")]

    selected = validator._validate_changed_files(changed)

    assert selected == "leaderboard/data/submissions/pending/sub-123.json"


def test_validate_changed_files_rejects_unrelated_path():
    changed = [validator.ChangedFile(status="A", path="README.md")]

    with pytest.raises(validator.SubmissionPRValidationError, match="may only change control records"):
        validator._validate_changed_files(changed)


def test_validate_changed_files_requires_exactly_one_file():
    changed = [
        validator.ChangedFile(status="A", path="leaderboard/data/submissions/pending/sub-1.json"),
        validator.ChangedFile(status="A", path="leaderboard/data/submissions/pending/sub-2.json"),
    ]

    with pytest.raises(validator.SubmissionPRValidationError, match="exactly one"):
        validator._validate_changed_files(changed)


def test_enforce_github_rate_limits_rejects_existing_open_submission_pr(monkeypatch):
    def fake_list_all_repo_pulls(repo: str, token: str):
        return [
            {
                "number": 101,
                "state": "open",
                "created_at": "2026-02-07T01:00:00Z",
                "user": {"login": "alice"},
            }
        ]

    monkeypatch.setattr(validator, "_list_all_repo_pulls", fake_list_all_repo_pulls)
    monkeypatch.setattr(validator, "_is_submission_pr", lambda repo, number, token: True)

    with pytest.raises(validator.SubmissionPRValidationError, match="already has an open submission PR"):
        validator._enforce_github_rate_limits(
            repo="owner/repo",
            actor="alice",
            current_pr_number=999,
            token="token",
            now_utc=dt.datetime(2026, 2, 7, 12, 0, tzinfo=dt.UTC),
        )


def test_enforce_github_rate_limits_rejects_recent_submission_with_next_allowed(monkeypatch):
    def fake_list_all_repo_pulls(repo: str, token: str):
        return [
            {
                "number": 201,
                "state": "closed",
                "created_at": "2026-02-07T03:15:00Z",
                "user": {"login": "alice"},
            }
        ]

    monkeypatch.setattr(validator, "_list_all_repo_pulls", fake_list_all_repo_pulls)
    monkeypatch.setattr(validator, "_is_submission_pr", lambda repo, number, token: True)

    with pytest.raises(validator.SubmissionPRValidationError, match="Next allowed UTC timestamp: 2026-02-08T03:15:00Z"):
        validator._enforce_github_rate_limits(
            repo="owner/repo",
            actor="alice",
            current_pr_number=999,
            token="token",
            now_utc=dt.datetime(2026, 2, 7, 4, 0, tzinfo=dt.UTC),
        )


def test_enforce_github_rate_limits_fail_closed_when_api_unavailable(monkeypatch):
    def fake_list_all_repo_pulls(repo: str, token: str):
        raise RuntimeError("network down")

    monkeypatch.setattr(validator, "_list_all_repo_pulls", fake_list_all_repo_pulls)

    with pytest.raises(validator.SubmissionPRValidationError, match="fail-closed"):
        validator._enforce_github_rate_limits(
            repo="owner/repo",
            actor="alice",
            current_pr_number=999,
            token="token",
            now_utc=dt.datetime(2026, 2, 7, 4, 0, tzinfo=dt.UTC),
        )


def test_enforce_github_rate_limits_allows_when_no_violations(monkeypatch):
    def fake_list_all_repo_pulls(repo: str, token: str):
        return [
            {
                "number": 301,
                "state": "closed",
                "created_at": "2026-02-05T00:00:00Z",
                "user": {"login": "alice"},
            }
        ]

    monkeypatch.setattr(validator, "_list_all_repo_pulls", fake_list_all_repo_pulls)
    monkeypatch.setattr(validator, "_is_submission_pr", lambda repo, number, token: True)

    validator._enforce_github_rate_limits(
        repo="owner/repo",
        actor="alice",
        current_pr_number=999,
        token="token",
        now_utc=dt.datetime(2026, 2, 7, 12, 0, tzinfo=dt.UTC),
    )


def test_enforce_github_rate_limits_skips_non_submission_prs(monkeypatch):
    def fake_list_all_repo_pulls(repo: str, token: str):
        return [
            {
                "number": 401,
                "state": "open",
                "created_at": "2026-02-07T03:15:00Z",
                "user": {"login": "alice"},
            }
        ]

    monkeypatch.setattr(validator, "_list_all_repo_pulls", fake_list_all_repo_pulls)
    monkeypatch.setattr(validator, "_is_submission_pr", lambda repo, number, token: False)

    validator._enforce_github_rate_limits(
        repo="owner/repo",
        actor="alice",
        current_pr_number=999,
        token="token",
        now_utc=dt.datetime(2026, 2, 7, 12, 0, tzinfo=dt.UTC),
    )
