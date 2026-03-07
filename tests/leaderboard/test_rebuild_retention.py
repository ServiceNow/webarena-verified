import json
from pathlib import Path

from dev.leaderboard.publish import publish_from_canonical


def _canonical_record(submission_id: int, *, eval_completed_at_utc: str) -> dict:
    return {
        "submission_id": submission_id,
        "github_pr_number": submission_id,
        "github_pr_url": f"https://github.com/owner/repo/pull/{submission_id}",
        "source_repository_id": 777,
        "source_repository_full_name": "fork-owner/repo-fork",
        "github_pr_author_id": 456,
        "github_pr_author_login": "octocat",
        "eval_completed_at_utc": eval_completed_at_utc,
        "evaluator_version": "1.0.0",
        "status": "accepted",
        "hf_repo": "owner/dataset",
        "hf_path": f"submissions/{submission_id}",
        "hf_revision": f"rev-{submission_id}",
        "name": f"Team/{submission_id}",
        "leaderboard": "both",
        "reference": "https://example.com/paper",
        "overall_score": 0.8,
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
        "checksum": f"{submission_id:064x}"[-64:],
    }


def _write_canonical(canonical_dir: Path, submission_id: int, *, eval_completed_at_utc: str) -> None:
    payload = _canonical_record(submission_id, eval_completed_at_utc=eval_completed_at_utc)
    (canonical_dir / f"{submission_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_publish_from_canonical_prunes_to_latest_100(tmp_path: Path):
    canonical_dir = tmp_path / "submissions"
    canonical_dir.mkdir(parents=True)

    for submission_id in range(1, 103):
        second = submission_id % 60
        minute = submission_id // 60
        eval_completed_at = f"2026-02-07T12:{minute:02d}:{second:02d}Z"
        _write_canonical(canonical_dir, submission_id, eval_completed_at_utc=eval_completed_at)

    manifest = publish_from_canonical(
        branch_root=tmp_path,
        canonical_dir=canonical_dir,
        staging_dir=tmp_path / "staging",
        max_canonical_records=100,
        generation_id="gen-retention",
        generated_at_utc="2026-02-07T18:00:00Z",
    )

    retained_files = sorted(path.name for path in canonical_dir.glob("*.json"))
    assert len(retained_files) == 100
    assert "1.json" not in retained_files
    assert "2.json" not in retained_files
    assert "102.json" in retained_files

    manifest_payload = json.loads((tmp_path / "leaderboard_manifest.json").read_text(encoding="utf-8"))
    full_payload = json.loads((tmp_path / manifest.full_file).read_text(encoding="utf-8"))
    hard_payload = json.loads((tmp_path / manifest.hard_file).read_text(encoding="utf-8"))
    assert manifest_payload["generation_id"] == "gen-retention"
    assert len(full_payload["rows"]) == 100
    assert len(hard_payload["rows"]) == 100


def test_pruning_tie_breaks_by_submission_id_desc(tmp_path: Path):
    canonical_dir = tmp_path / "submissions"
    canonical_dir.mkdir(parents=True)

    same_time = "2026-02-07T12:30:00Z"
    _write_canonical(canonical_dir, 9, eval_completed_at_utc=same_time)
    _write_canonical(canonical_dir, 10, eval_completed_at_utc=same_time)

    publish_from_canonical(
        branch_root=tmp_path,
        canonical_dir=canonical_dir,
        staging_dir=tmp_path / "staging",
        max_canonical_records=1,
        generation_id="gen-tie",
        generated_at_utc="2026-02-07T18:00:00Z",
    )

    retained_files = sorted(path.name for path in canonical_dir.glob("*.json"))
    assert retained_files == ["10.json"]


def test_publish_from_canonical_default_generation_is_deterministic(tmp_path: Path):
    canonical_dir = tmp_path / "submissions"
    canonical_dir.mkdir(parents=True)
    _write_canonical(canonical_dir, 101, eval_completed_at_utc="2026-02-07T13:00:00Z")
    _write_canonical(canonical_dir, 102, eval_completed_at_utc="2026-02-07T14:00:00Z")

    manifest_one = publish_from_canonical(
        branch_root=tmp_path,
        canonical_dir=canonical_dir,
        staging_dir=tmp_path / "staging",
    )
    snapshot_manifest = (tmp_path / "leaderboard_manifest.json").read_text(encoding="utf-8")
    snapshot_full = (tmp_path / manifest_one.full_file).read_text(encoding="utf-8")
    snapshot_hard = (tmp_path / manifest_one.hard_file).read_text(encoding="utf-8")

    manifest_two = publish_from_canonical(
        branch_root=tmp_path,
        canonical_dir=canonical_dir,
        staging_dir=tmp_path / "staging",
    )

    assert manifest_one.generation_id == manifest_two.generation_id
    assert manifest_one.generated_at_utc == manifest_two.generated_at_utc
    assert (tmp_path / "leaderboard_manifest.json").read_text(encoding="utf-8") == snapshot_manifest
    assert (tmp_path / manifest_one.full_file).read_text(encoding="utf-8") == snapshot_full
    assert (tmp_path / manifest_one.hard_file).read_text(encoding="utf-8") == snapshot_hard
