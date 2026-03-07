import pytest
from pydantic import ValidationError

from webarena_verified.types.leaderboard import (
    CanonicalSubmissionRecord,
    IntakeManifest,
    IntakeSubmission,
    LeaderboardManifest,
    LeaderboardRow,
    LeaderboardTableFile,
    SubmissionMetadata,
    SubmissionPayloadManifest,
    SubmissionRecord,
    SubmissionStatus,
)


def _valid_legacy_submission_record() -> dict:
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


def _valid_canonical_submission_record() -> dict:
    return {
        "submission_id": 123,
        "github_pr_number": 123,
        "github_pr_url": "https://github.com/owner/repo/pull/123",
        "source_repository_id": 777,
        "source_repository_full_name": "fork-owner/repo-fork",
        "github_pr_author_id": 456,
        "github_pr_author_login": "octocat",
        "status": "accepted",
        "eval_completed_at_utc": "2026-02-07T12:10:00Z",
        "evaluator_version": "1.2.3",
        "hf_repo": "owner/dataset",
        "hf_path": "submissions/123",
        "hf_revision": "abc123",
        "name": "TeamX/ModelY",
        "leaderboard": "both",
        "reference": "https://example.com/paper",
        "version": "v1",
        "contact_info": "team@example.com",
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
        "checksum": "a" * 64,
    }


def _valid_row() -> dict:
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


def _valid_intake_submission() -> dict:
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


def _valid_intake_manifest() -> dict:
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


def test_submission_record_pending_valid_legacy_shape():
    record = SubmissionRecord(**_valid_legacy_submission_record())
    assert record.status == SubmissionStatus.PENDING


def test_canonical_submission_record_valid():
    record = CanonicalSubmissionRecord(**_valid_canonical_submission_record())
    assert record.submission_id == 123
    assert record.status == "accepted"


def test_canonical_submission_record_requires_matching_identity():
    payload = _valid_canonical_submission_record()
    payload["github_pr_number"] = 456

    with pytest.raises(ValidationError, match="submission_id must equal github_pr_number"):
        CanonicalSubmissionRecord(**payload)


def test_canonical_submission_record_rejects_invalid_overall_score():
    payload = _valid_canonical_submission_record()
    payload["overall_score"] = 2.0

    with pytest.raises(ValidationError, match="overall_score must be within \\[0, 1\\]"):
        CanonicalSubmissionRecord(**payload)


def test_canonical_submission_record_rejects_invalid_contact_info():
    payload = _valid_canonical_submission_record()
    payload["contact_info"] = "not-an-email"

    with pytest.raises(ValidationError, match="contact_info must be a valid email"):
        CanonicalSubmissionRecord(**payload)


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


def test_row_rejects_non_integer_submission_id():
    payload = _valid_row()
    payload["submission_id"] = "sub-123"

    with pytest.raises(ValidationError):
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


def test_intake_submission_valid():
    intake = IntakeSubmission(**_valid_intake_submission())
    assert intake.packaging_summary.tasks_packaged == 100


def test_intake_submission_rejects_unknown_field():
    payload = _valid_intake_submission()
    payload["submission_id"] = 123

    with pytest.raises(ValidationError):
        IntakeSubmission(**payload)


def test_intake_manifest_valid():
    manifest = IntakeManifest(**_valid_intake_manifest())
    assert len(manifest.files) == 2


def test_intake_manifest_rejects_duplicate_paths():
    payload = _valid_intake_manifest()
    payload["files"] = [
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
        IntakeManifest(**payload)


def test_intake_manifest_rejects_path_traversal():
    payload = _valid_intake_manifest()
    payload["files"][0]["path"] = "../submission.json"

    with pytest.raises(ValidationError, match="must not contain '..'"):
        IntakeManifest(**payload)


def test_legacy_submission_metadata_still_valid_for_transition():
    metadata = SubmissionMetadata(
        submission_id="sub-123",
        name="TeamX/ModelY",
        leaderboard="both",
        reference="https://example.com/paper",
        created_at_utc="2026-02-07T12:00:00Z",
        contact_info="team@example.com",
    )
    assert metadata.submission_id == "sub-123"


def test_legacy_submission_payload_manifest_still_valid_for_transition():
    manifest = SubmissionPayloadManifest(
        submission_id="sub-123",
        archive_file="payload.tar.zst",
        archive_sha256="d" * 64,
        archive_size_bytes=42,
        created_at_utc="2026-02-07T12:00:00Z",
        hf_pr_id=10,
        hf_pr_url="https://huggingface.co/datasets/org/repo/discussions/10",
    )
    assert manifest.archive_file == "payload.tar.zst"
