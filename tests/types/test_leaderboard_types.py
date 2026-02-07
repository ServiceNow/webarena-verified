import pytest
from pydantic import ValidationError

from webarena_verified.types.leaderboard import (
    LeaderboardManifest,
    LeaderboardRow,
    LeaderboardTableFile,
    SubmissionRecord,
    SubmissionStatus,
)


def _valid_submission_record() -> dict:
    return {
        "submission_id": "sub-123",
        "status": "pending",
        "hf_repo": "org/repo",
        "hf_pr_id": 42,
        "hf_pr_url": "https://huggingface.co/datasets/org/repo/discussions/42",
        "created_at_utc": "2026-02-07T12:00:00Z",
        "updated_at_utc": "2026-02-07T12:05:00Z",
        "processed_at_utc": None,
        "result_reason": None,
    }


def _valid_row() -> dict:
    return {
        "rank": 1,
        "submission_id": "sub-123",
        "name": "TeamX/ModelY",
        "overall_score": 0.95,
        "shopping_score": 0.91,
        "reddit_score": 0.88,
        "gitlab_score": 0.9,
        "wikipedia_score": -1,
        "map_score": 0.86,
        "shopping_admin_score": 0.92,
        "success_count": 10,
        "failure_count": 2,
        "error_count": 0,
        "missing_count": 1,
        "webarena_verified_version": "1.0.0",
        "checksum": "a" * 64,
    }


def test_submission_record_pending_valid():
    record = SubmissionRecord(**_valid_submission_record())
    assert record.status == SubmissionStatus.PENDING


def test_submission_record_rejected_requires_reason():
    payload = _valid_submission_record()
    payload["status"] = "rejected"
    payload["processed_at_utc"] = "2026-02-07T13:00:00Z"
    payload["result_reason"] = None

    with pytest.raises(ValidationError, match="result_reason is required"):
        SubmissionRecord(**payload)


def test_submission_record_pending_disallows_processed_timestamp():
    payload = _valid_submission_record()
    payload["processed_at_utc"] = "2026-02-07T13:00:00Z"

    with pytest.raises(ValidationError, match="processed_at_utc must be null"):
        SubmissionRecord(**payload)


def test_submission_record_timestamp_requires_rfc3339_utc_z():
    payload = _valid_submission_record()
    payload["created_at_utc"] = "2026-02-07T12:00:00+00:00"

    with pytest.raises(ValidationError, match="RFC3339 UTC ending with 'Z'"):
        SubmissionRecord(**payload)


def test_manifest_validates_hashes_and_timestamp():
    manifest = LeaderboardManifest(
        schema_version="1.0",
        generation_id="gen-abc",
        generated_at_utc="2026-02-07T12:00:00Z",
        full_file="leaderboard_full.gen-abc.json",
        hard_file="leaderboard_hard.gen-abc.json",
        full_sha256="b" * 64,
        hard_sha256="c" * 64,
    )
    assert manifest.generation_id == "gen-abc"


def test_manifest_rejects_invalid_hash():
    with pytest.raises(ValidationError, match="64-character SHA256"):
        LeaderboardManifest(
            schema_version="1.0",
            generation_id="gen-abc",
            generated_at_utc="2026-02-07T12:00:00Z",
            full_file="leaderboard_full.gen-abc.json",
            hard_file="leaderboard_hard.gen-abc.json",
            full_sha256="not-a-hash",
            hard_sha256="c" * 64,
        )


def test_row_accepts_site_score_missing_sentinel():
    row = LeaderboardRow(**_valid_row())
    assert row.wikipedia_score == -1


def test_row_rejects_invalid_site_score():
    payload = _valid_row()
    payload["shopping_score"] = 1.2

    with pytest.raises(ValidationError, match="within \\[0, 1\\] or exactly -1"):
        LeaderboardRow(**payload)


def test_row_rejects_invalid_overall_score():
    payload = _valid_row()
    payload["overall_score"] = -0.1

    with pytest.raises(ValidationError, match="overall_score must be within \\[0, 1\\]"):
        LeaderboardRow(**payload)


def test_table_file_valid():
    table = LeaderboardTableFile(
        schema_version="1.0",
        generation_id="gen-abc",
        generated_at_utc="2026-02-07T12:00:00Z",
        leaderboard="full",
        rows=[LeaderboardRow(**_valid_row())],
    )
    assert table.leaderboard == "full"
