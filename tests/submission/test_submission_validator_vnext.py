import json
from pathlib import Path

import pytest

from webarena_verified.submission.submission_validator import SubmissionValidator


def _write_submission_tree(root: Path) -> None:
    (root / "101").mkdir(parents=True)
    (root / "101" / "agent_response.json").write_text('{"ok":true}', encoding="utf-8")
    (root / "101" / "network.har").write_text('{"log":{"entries":[]}}', encoding="utf-8")

    submission = {
        "submission_uid": "018f6f54-7e58-7f23-9d16-f4f8072b4f61",
        "name": "TeamX-ModelY",
        "model": "gpt-4.1-mini",
        "reference": "https://example.com/paper",
        "contact_email": "team@example.com",
        "submitted_tasks": 1,
        "task_network_filename": "network.har",
    }
    (root / "submission.json").write_text(json.dumps(submission, indent=2), encoding="utf-8")

    manifest_payload = {
        "schema_version": "1.0",
        "created_at_utc": "2026-03-08T10:00:00Z",
        "files": [],
    }
    for rel in ["101/agent_response.json", "101/network.har", "submission.json"]:
        path = root / rel
        manifest_payload["files"].append(
            {
                "path": rel,
                "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
        )
    (root / "manifest.json").write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    manifest_sha = __import__("hashlib").sha256((root / "manifest.json").read_bytes()).hexdigest()
    digest = __import__("hashlib").sha256()
    for rel in ["101/agent_response.json", "101/network.har", "submission.json"]:
        path = root / rel
        digest.update(rel.encode("utf-8"))
        digest.update(b"\n")
        digest.update(path.read_bytes())
        digest.update(b"\n")
    package_sha = digest.hexdigest()
    internal = {
        "schema_version": "1.0",
        "submission_uid": "018f6f54-7e58-7f23-9d16-f4f8072b4f61",
        "submission_mode": "full",
        "source_sha": None,
        "generated_at_utc": "2026-03-08T10:00:00Z",
        "manifest_sha256": manifest_sha,
        "submission_package_checksum": package_sha,
        "submission_package_checksum_algo": "sha256",
    }
    (root / "_internal.json").write_text(json.dumps(internal, indent=2), encoding="utf-8")


def _refresh_manifest_and_internal(root: Path) -> None:
    manifest_payload = {
        "schema_version": "1.0",
        "created_at_utc": "2026-03-08T10:00:00Z",
        "files": [],
    }
    for rel in ["101/agent_response.json", "101/network.har", "submission.json"]:
        path = root / rel
        manifest_payload["files"].append(
            {
                "path": rel,
                "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
        )
    (root / "manifest.json").write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    manifest_sha = __import__("hashlib").sha256((root / "manifest.json").read_bytes()).hexdigest()
    digest = __import__("hashlib").sha256()
    for rel in ["101/agent_response.json", "101/network.har", "submission.json"]:
        path = root / rel
        digest.update(rel.encode("utf-8"))
        digest.update(b"\n")
        digest.update(path.read_bytes())
        digest.update(b"\n")

    internal = json.loads((root / "_internal.json").read_text(encoding="utf-8"))
    internal["manifest_sha256"] = manifest_sha
    internal["submission_package_checksum"] = digest.hexdigest()
    (root / "_internal.json").write_text(json.dumps(internal, indent=2), encoding="utf-8")


def test_validator_rejects_evaluator_artifact_in_uploaded_payload(tmp_path: Path) -> None:
    _write_submission_tree(tmp_path)
    (tmp_path / "101" / "eval_result.json").write_text("{}", encoding="utf-8")

    validator = SubmissionValidator()
    with pytest.raises(ValueError, match="must not include evaluator artifacts"):
        validator.validate_submission_tree(tmp_path)


def test_validator_rejects_unexpected_task_file(tmp_path: Path) -> None:
    _write_submission_tree(tmp_path)
    (tmp_path / "101" / "unexpected.txt").write_text("x", encoding="utf-8")

    validator = SubmissionValidator()
    with pytest.raises(ValueError, match="Unexpected task file"):
        validator.validate_submission_tree(tmp_path)


def test_validator_rejects_task_folder_missing_required_file(tmp_path: Path) -> None:
    _write_submission_tree(tmp_path)
    (tmp_path / "101" / "network.har").unlink()

    validator = SubmissionValidator()
    with pytest.raises(ValueError, match="missing required file"):
        validator.validate_submission_tree(tmp_path)


def test_validator_rejects_placeholder_submission_metadata(tmp_path: Path) -> None:
    _write_submission_tree(tmp_path)
    payload = json.loads((tmp_path / "submission.json").read_text(encoding="utf-8"))
    payload["reference"] = "https://example.com/replace-me"
    (tmp_path / "submission.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _refresh_manifest_and_internal(tmp_path)

    validator = SubmissionValidator()
    with pytest.raises(ValueError, match="placeholder value"):
        validator.validate_submission_tree(tmp_path)
