import json
from pathlib import Path

import pytest

from leaderboard.scripts import hf_publish_pr


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_path_allowlist_includes_expected_patterns() -> None:
    assert hf_publish_pr._path_is_allowlisted("submission_control/42.json")
    assert hf_publish_pr._path_is_allowlisted("submissions/42.json")
    assert hf_publish_pr._path_is_allowlisted("leaderboard_manifest.json")
    assert hf_publish_pr._path_is_allowlisted("leaderboard_full.gen-1.json")
    assert not hf_publish_pr._path_is_allowlisted("docs/index.md")


def test_verify_head_sha_linkage_passes_when_matching(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "submissions/7.json",
        {"submission_id": 7, "hf_head_sha": "sha-1"},
    )
    _write_json(
        tmp_path / "submission_control/7.json",
        {"submission_id": 7, "hf_head_sha": "sha-1"},
    )

    hf_publish_pr._verify_latest_accepted_head_sha_linkage(repo_root=tmp_path)


def test_verify_head_sha_linkage_fails_when_mismatched(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "submissions/7.json",
        {"submission_id": 7, "hf_head_sha": "sha-1"},
    )
    _write_json(
        tmp_path / "submission_control/7.json",
        {"submission_id": 7, "hf_head_sha": "sha-2"},
    )

    with pytest.raises(ValueError, match="mismatch"):
        hf_publish_pr._verify_latest_accepted_head_sha_linkage(repo_root=tmp_path)
