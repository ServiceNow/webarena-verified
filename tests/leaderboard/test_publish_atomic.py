import json
from pathlib import Path

import pytest

from dev.leaderboard.publish import (
    LEADERBOARD_DATA_DIR,
    LEADERBOARD_MANIFEST_FILE,
    generate_leaderboard_staging,
    publish_from_processed,
    publish_staged_leaderboard,
)


def _row(submission_id: int, overall_score: float) -> dict:
    return {
        "submission_id": submission_id,
        "name": f"Team/{submission_id}",
        "overall_score": overall_score,
        "shopping_score": 0.8,
        "reddit_score": 0.8,
        "gitlab_score": 0.8,
        "wikipedia_score": 0.8,
        "map_score": 0.8,
        "shopping_admin_score": 0.8,
        "success_count": 10,
        "failure_count": 0,
        "error_count": 0,
        "missing_count": 0,
        "webarena_verified_version": "1.0.0",
        "checksum": "a" * 64,
    }


def test_generate_is_deterministic_and_tie_breaks_by_submission_id(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    full_rows = [
        _row(10, 0.9),
        _row(2, 0.9),
        _row(7, 0.95),
    ]
    hard_rows = [_row(99, 0.5)]

    manifest = generate_leaderboard_staging(
        staging_dir=staging_dir,
        generation_id="gen-001",
        generated_at_utc="2026-02-07T18:00:00Z",
        full_rows=full_rows,
        hard_rows=hard_rows,
    )

    assert manifest.generation_id == "gen-001"

    full_table = json.loads((staging_dir / manifest.full_file).read_text(encoding="utf-8"))
    ranked_ids = [row["submission_id"] for row in full_table["rows"]]
    ranked_positions = [row["rank"] for row in full_table["rows"]]

    assert ranked_ids == [7, 2, 10]
    assert ranked_positions == [1, 2, 3]


def test_publish_is_atomic_and_replaces_old_generation_files(tmp_path: Path):
    gh_pages_root = tmp_path / "gh-pages"
    live_data = gh_pages_root / LEADERBOARD_DATA_DIR
    old_generation = live_data / "leaderboard_full.old.json"
    live_data.mkdir(parents=True)
    old_generation.write_text("{}", encoding="utf-8")
    (live_data / "leaderboard_hard.old.json").write_text("{}", encoding="utf-8")
    (live_data / LEADERBOARD_MANIFEST_FILE).write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generation_id": "old",
                "generated_at_utc": "2026-02-07T10:00:00Z",
                "full_file": "leaderboard_full.old.json",
                "hard_file": "leaderboard_hard.old.json",
                "full_sha256": "b" * 64,
                "hard_sha256": "c" * 64,
            }
        ),
        encoding="utf-8",
    )

    staging_dir = tmp_path / "staging"
    manifest = generate_leaderboard_staging(
        staging_dir=staging_dir,
        generation_id="gen-atomic",
        generated_at_utc="2026-02-07T18:00:00Z",
        full_rows=[_row(1, 0.7)],
        hard_rows=[_row(2, 0.6)],
    )

    publish_staged_leaderboard(staging_dir=staging_dir, gh_pages_root=gh_pages_root)

    live_files = {path.name for path in live_data.iterdir() if path.is_file()}
    assert live_files == {LEADERBOARD_MANIFEST_FILE, manifest.full_file, manifest.hard_file}
    assert old_generation.exists() is False


def test_publish_failure_never_switches_live_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    gh_pages_root = tmp_path / "gh-pages"
    live_data = gh_pages_root / LEADERBOARD_DATA_DIR
    live_data.mkdir(parents=True)

    old_manifest_path = live_data / LEADERBOARD_MANIFEST_FILE
    old_manifest_content = json.dumps(
        {
            "schema_version": "1.0",
            "generation_id": "old-gen",
            "generated_at_utc": "2026-02-07T10:00:00Z",
            "full_file": "leaderboard_full.old-gen.json",
            "hard_file": "leaderboard_hard.old-gen.json",
            "full_sha256": "b" * 64,
            "hard_sha256": "c" * 64,
        }
    )
    old_manifest_path.write_text(old_manifest_content, encoding="utf-8")
    (live_data / "leaderboard_full.old-gen.json").write_text("{}", encoding="utf-8")
    (live_data / "leaderboard_hard.old-gen.json").write_text("{}", encoding="utf-8")

    staging_dir = tmp_path / "staging"
    generate_leaderboard_staging(
        staging_dir=staging_dir,
        generation_id="new-gen",
        generated_at_utc="2026-02-07T18:00:00Z",
        full_rows=[_row(1, 0.8)],
        hard_rows=[_row(2, 0.7)],
    )

    copy2_impl = __import__("shutil").copy2

    def fail_on_hard_copy(src: Path, dst: Path, *, follow_symlinks: bool = True):
        if str(src).endswith("leaderboard_hard.new-gen.json"):
            raise RuntimeError("injected publish failure")
        return copy2_impl(src, dst, follow_symlinks=follow_symlinks)

    monkeypatch.setattr("dev.leaderboard.publish.shutil.copy2", fail_on_hard_copy)

    with pytest.raises(RuntimeError, match="injected publish failure"):
        publish_staged_leaderboard(staging_dir=staging_dir, gh_pages_root=gh_pages_root)

    assert old_manifest_path.read_text(encoding="utf-8") == old_manifest_content
    assert json.loads(old_manifest_path.read_text(encoding="utf-8"))["generation_id"] == "old-gen"


def test_generate_rejects_duplicate_submission_ids(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    duplicate_full_rows = [
        _row(42, 0.9),
        _row(42, 0.8),
    ]

    with pytest.raises(ValueError, match="duplicate submission_id"):
        generate_leaderboard_staging(
            staging_dir=staging_dir,
            generation_id="gen-dup",
            generated_at_utc="2026-02-07T18:00:00Z",
            full_rows=duplicate_full_rows,
            hard_rows=[],
        )


def test_publish_from_processed_supports_canonical_integer_records(tmp_path: Path):
    processed_dir = tmp_path / "submissions"
    processed_dir.mkdir(parents=True)
    canonical_record = {
        "submission_id": 101,
        "github_pr_number": 101,
        "github_pr_url": "https://github.com/owner/repo/pull/101",
        "source_repository_id": 9,
        "source_repository_full_name": "fork-owner/repo-fork",
        "github_pr_author_id": 10,
        "github_pr_author_login": "alice",
        "eval_completed_at_utc": "2026-02-07T12:00:00Z",
        "evaluator_version": "2.0.0",
        "status": "accepted",
        "hf_repo": "owner/dataset",
        "hf_path": "submissions/101",
        "hf_revision": "deadbeef",
        "name": "Team/Model",
        "leaderboard": "full",
        "reference": "https://example.com",
        "overall_score": 0.9,
        "shopping_score": 0.9,
        "reddit_score": 0.9,
        "gitlab_score": 0.9,
        "wikipedia_score": 0.9,
        "map_score": 0.9,
        "shopping_admin_score": 0.9,
        "success_count": 10,
        "failure_count": 0,
        "error_count": 0,
        "missing_count": 0,
        "checksum": "f" * 64,
    }
    (processed_dir / "101.json").write_text(json.dumps(canonical_record), encoding="utf-8")

    staging_dir = tmp_path / "staging"
    manifest = publish_from_processed(
        gh_pages_root=tmp_path / "gh-pages",
        processed_dir=processed_dir,
        staging_dir=staging_dir,
        generation_id="gen-canonical",
        generated_at_utc="2026-02-07T18:00:00Z",
        dry_run=True,
    )

    full_table = json.loads((staging_dir / manifest.full_file).read_text(encoding="utf-8"))
    assert full_table["rows"][0]["submission_id"] == 101
    assert full_table["rows"][0]["webarena_verified_version"] == "2.0.0"
