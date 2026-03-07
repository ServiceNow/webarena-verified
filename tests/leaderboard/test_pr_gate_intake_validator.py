import hashlib
import json
from pathlib import Path

import pytest

import dev.leaderboard.pr_gate_intake_validator as validator


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _create_valid_intake(repo_root: Path, intake_id: str = "intake-1") -> Path:
    intake_root = repo_root / "submissions" / "inbox" / intake_id
    tasks_root = intake_root / "tasks"

    _write_json(
        intake_root / "submission.json",
        {
            "name": "TeamX/ModelY",
            "leaderboard": "both",
            "reference": "https://example.com/paper",
            "created_at_utc": "2026-03-07T12:00:00Z",
            "packaging_summary": {"tasks_packaged": 1},
        },
    )

    _write_json(tasks_root / "1" / "agent_response.json", {"ok": True})
    _write_json(tasks_root / "1" / "network.har", {"log": {"entries": []}})

    declared_files = [
        "submission.json",
        "tasks/1/agent_response.json",
        "tasks/1/network.har",
    ]
    manifest_files = []
    for relative_path in declared_files:
        target = intake_root / relative_path
        manifest_files.append(
            {
                "path": relative_path,
                "sha256": _sha256_file(target),
                "size_bytes": target.stat().st_size,
            }
        )

    _write_json(
        intake_root / "manifest.json",
        {
            "created_at_utc": "2026-03-07T12:00:00Z",
            "schema_version": "1.0",
            "files": manifest_files,
        },
    )
    return intake_root


def test_select_single_intake_accepts_valid_scope():
    intake_id = validator._select_single_intake_id(
        [
            "submissions/inbox/intake-1/submission.json",
            "submissions/inbox/intake-1/manifest.json",
        ]
    )
    assert intake_id == "intake-1"


def test_select_single_intake_rejects_out_of_scope_paths():
    with pytest.raises(validator.PRGateValidationError, match="Invalid paths"):
        validator._select_single_intake_id(["README.md"])


def test_select_single_intake_rejects_multiple_intake_ids():
    with pytest.raises(validator.PRGateValidationError, match="Exactly one intake folder"):
        validator._select_single_intake_id(
            [
                "submissions/inbox/intake-a/submission.json",
                "submissions/inbox/intake-b/submission.json",
            ]
        )


def test_validate_intake_tree_accepts_valid_payload(tmp_path: Path):
    intake_root = _create_valid_intake(tmp_path)

    submission, manifest = validator.validate_intake_tree(intake_root)

    assert submission.leaderboard == "both"
    assert len(manifest.files) == 3


def test_validate_intake_tree_rejects_manifest_sha_mismatch(tmp_path: Path):
    intake_root = _create_valid_intake(tmp_path)
    (intake_root / "tasks" / "1" / "agent_response.json").write_text('{"ok": trve}', encoding="utf-8")

    with pytest.raises(validator.PRGateValidationError, match="sha256 mismatch"):
        validator.validate_intake_tree(intake_root)


def test_validate_task_invariants_rejects_missing_xor_violation(tmp_path: Path):
    intake_root = _create_valid_intake(tmp_path)
    invalid_task_root = intake_root / "tasks" / "2"
    invalid_task_root.mkdir(parents=True, exist_ok=True)
    (invalid_task_root / ".missing").write_text("", encoding="utf-8")
    _write_json(invalid_task_root / "agent_response.json", {"ok": True})

    with pytest.raises(validator.PRGateValidationError, match="cannot coexist"):
        validator.validate_task_invariants(intake_root / "tasks")


def test_run_pr_gate_intake_validation_uses_git_diff_selection(monkeypatch, tmp_path: Path):
    _create_valid_intake(tmp_path, intake_id="intake-xyz")

    monkeypatch.setattr(
        validator,
        "_run_git_diff_paths",
        lambda **_: [
            "submissions/inbox/intake-xyz/submission.json",
            "submissions/inbox/intake-xyz/manifest.json",
            "submissions/inbox/intake-xyz/tasks/1/agent_response.json",
        ],
    )

    result = validator.run_pr_gate_intake_validation(tmp_path, base_sha="abc", head_sha="def")

    assert result.intake_id == "intake-xyz"
    assert len(result.changed_paths) == 3
