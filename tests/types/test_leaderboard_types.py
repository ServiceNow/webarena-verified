import pytest
from pydantic import ValidationError

from webarena_verified.types.leaderboard import (
    CanonicalSubmissionRecord,
    IntakeManifest,
    IntakeSubmission,
    LeaderboardManifest,
    LeaderboardRow,
    LeaderboardTableFile,
    LeaderboardView,
    SubmissionLeaderboard,
)


@pytest.fixture
def canonical_submission_record_payload() -> dict:
    return {
        "submission_id": 123,
        "github_pr_number": 123,
        "github_pr_url": "https://github.com/owner/repo/pull/123",
        "source_repository_id": 777,
        "source_repository_full_name": "fork-owner/repo-fork",
        "github_pr_author_id": 456,
        "github_pr_author_login": "octocat",
        "eval_completed_at_utc": "2026-02-07T12:10:00Z",
        "webarena_verified_version": "1.2.3",
        "huggingface_dataset_repo": "owner/dataset/submissions/123",
        "huggingface_dataset_revision": "abc123",
        "name": "TeamX/ModelY",
        "leaderboard": "both",
        "reference": "https://example.com/paper",
        "model_version": "v1",
        "contact_info": "team@example.com",
        "overall_score": 0.95,
        "shopping_score": 0.91,
        "reddit_score": 0.88,
        "gitlab_score": 0.9,
        "wikipedia_score": 0.87,
        "map_score": 0.86,
        "shopping_admin_score": 0.92,
        "success_count": 10,
        "failure_count": 2,
        "error_count": 0,
        "missing_count": 1,
        "checksum": "a" * 64,
    }


@pytest.fixture
def leaderboard_row_payload() -> dict:
    return {
        "rank": 1,
        "submission_id": 123,
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


@pytest.fixture
def intake_submission_payload() -> dict:
    return {
        "name": "TeamX/ModelY",
        "leaderboard": "both",
        "reference": "https://example.com/paper",
        "created_at_utc": "2026-02-07T12:00:00Z",
        "packaging_summary": {
            "tasks_packaged": 100,
            "tasks_with_issues": 3,
            "duplicate_tasks": 1,
            "unknown_tasks": 1,
            "missing_from_output": 1,
        },
        "version": "v1",
        "contact_info": "team@example.com",
    }


@pytest.fixture
def intake_manifest_payload() -> dict:
    return {
        "schema_version": "1.0",
        "created_at_utc": "2026-02-07T12:00:00Z",
        "files": [
            {
                "path": "submission.json",
                "sha256": "b" * 64,
                "size_bytes": 128,
            },
            {
                "path": "tasks/1/agent_response.json",
                "sha256": "c" * 64,
                "size_bytes": 256,
            },
        ],
    }


def test_canonical_submission_record_valid(canonical_submission_record_payload: dict):
    record = CanonicalSubmissionRecord(**canonical_submission_record_payload)
    assert record.submission_id == 123
    assert record.huggingface_dataset_revision == "abc123"


def test_canonical_submission_record_requires_matching_identity(canonical_submission_record_payload: dict):
    canonical_submission_record_payload["github_pr_number"] = 456

    with pytest.raises(ValidationError, match="submission_id must equal github_pr_number"):
        CanonicalSubmissionRecord(**canonical_submission_record_payload)


def test_canonical_submission_record_rejects_invalid_overall_score(canonical_submission_record_payload: dict):
    canonical_submission_record_payload["overall_score"] = -0.1

    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        CanonicalSubmissionRecord(**canonical_submission_record_payload)


def test_canonical_submission_record_rejects_invalid_contact_info(canonical_submission_record_payload: dict):
    canonical_submission_record_payload["contact_info"] = "not-an-email"

    with pytest.raises(ValidationError, match="contact_info must be a valid email"):
        CanonicalSubmissionRecord(**canonical_submission_record_payload)


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


def test_row_accepts_site_score_missing_sentinel(leaderboard_row_payload: dict):
    row = LeaderboardRow(**leaderboard_row_payload)
    assert row.wikipedia_score == -1


def test_row_rejects_invalid_site_score(leaderboard_row_payload: dict):
    leaderboard_row_payload["shopping_score"] = 1.2

    with pytest.raises(ValidationError, match="within \\[0, 1\\] or exactly -1"):
        LeaderboardRow(**leaderboard_row_payload)


def test_row_rejects_invalid_overall_score(leaderboard_row_payload: dict):
    leaderboard_row_payload["overall_score"] = -0.1

    with pytest.raises(ValidationError, match="overall_score must be within \\[0, 1\\]"):
        LeaderboardRow(**leaderboard_row_payload)


def test_row_rejects_non_integer_submission_id(leaderboard_row_payload: dict):
    leaderboard_row_payload["submission_id"] = "sub-123"

    with pytest.raises(ValidationError):
        LeaderboardRow(**leaderboard_row_payload)


def test_table_file_valid(leaderboard_row_payload: dict):
    table = LeaderboardTableFile(
        schema_version="1.0",
        generation_id="gen-abc",
        generated_at_utc="2026-02-07T12:00:00Z",
        leaderboard="full",
        rows=[LeaderboardRow(**leaderboard_row_payload)],
    )
    assert table.leaderboard == LeaderboardView.FULL


def test_intake_submission_valid(intake_submission_payload: dict):
    intake = IntakeSubmission(**intake_submission_payload)
    assert intake.packaging_summary.tasks_packaged == 100
    assert intake.leaderboard == SubmissionLeaderboard.BOTH


def test_intake_submission_rejects_unknown_field(intake_submission_payload: dict):
    intake_submission_payload["submission_id"] = 123

    with pytest.raises(ValidationError):
        IntakeSubmission(**intake_submission_payload)


def test_intake_manifest_valid(intake_manifest_payload: dict):
    manifest = IntakeManifest(**intake_manifest_payload)
    assert len(manifest.files) == 2


def test_intake_manifest_rejects_duplicate_paths(intake_manifest_payload: dict):
    intake_manifest_payload["files"] = [
        {
            "path": "tasks/1/network.har",
            "sha256": "d" * 64,
            "size_bytes": 1,
        },
        {
            "path": "tasks/1/network.har",
            "sha256": "e" * 64,
            "size_bytes": 2,
        },
    ]

    with pytest.raises(ValidationError, match="unique path"):
        IntakeManifest(**intake_manifest_payload)


def test_intake_manifest_rejects_path_traversal(intake_manifest_payload: dict):
    intake_manifest_payload["files"][0]["path"] = "../submission.json"

    with pytest.raises(ValidationError, match="must not contain '..'"):
        IntakeManifest(**intake_manifest_payload)
