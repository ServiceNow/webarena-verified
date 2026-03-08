import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from webarena_verified.api.internal.submit_handler import SubmitHandler
from webarena_verified.types.leaderboard import IntakeManifest, IntakeSubmission


@pytest.fixture
def submission_dir_fixture(tmp_path: Path) -> Path:
    submission_dir = tmp_path / "submission"
    submission_dir.mkdir()

    summary_payload = {
        "packaging_summary": {
            "tasks_packaged": 2,
            "tasks_with_issues": 0,
            "duplicate_tasks": 0,
            "unknown_tasks": 0,
            "missing_from_output": 0,
        }
    }
    (submission_dir / "summary.json").write_text(json.dumps(summary_payload), encoding="utf-8")

    task_101 = submission_dir / "101"
    task_101.mkdir()
    (task_101 / "agent_response.json").write_text('{"status":"SUCCESS"}', encoding="utf-8")
    (task_101 / "network.har").write_text('{"log":{"entries":[]}}', encoding="utf-8")

    task_102 = submission_dir / "102"
    task_102.mkdir()
    (task_102 / ".missing").write_text("", encoding="utf-8")

    return submission_dir


@pytest.fixture
def mock_hf_api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    captured: dict[str, object] = {}
    api_instance = Mock()

    def _create_commit(**kwargs):
        captured["commit_kwargs"] = kwargs
        operations = kwargs.get("operations", [])
        snapshot = tmp_path / "uploaded_snapshot"
        if snapshot.exists():
            shutil.rmtree(snapshot)
        snapshot.mkdir()
        for op in operations:
            dest = snapshot / op.path_in_repo
            dest.parent.mkdir(parents=True, exist_ok=True)
            source = op.path_or_fileobj
            if isinstance(source, (str, Path)):
                shutil.copy2(source, dest)
            elif isinstance(source, bytes):
                dest.write_bytes(source)
        captured["snapshot_dir"] = snapshot
        return SimpleNamespace(
            pr_num=42,
            pr_revision="refs/pr/42",
            pr_url="https://huggingface.co/datasets/org/repo/discussions/42",
        )

    api_instance.create_commit.side_effect = _create_commit

    api_class = Mock(return_value=api_instance)
    monkeypatch.setattr("webarena_verified.api.internal.submit_handler.HfApi", api_class)
    return api_class, api_instance, captured


def test_submit_validates_missing_dir(tmp_path: Path):
    handler = SubmitHandler(submission_dir=tmp_path / "does-not-exist", hf_repo="org/repo", hf_token="token")
    with pytest.raises(ValueError, match="does not exist"):
        handler.submit(name="TeamX/ModelY", leaderboard="both", reference="https://example.com")


def test_submit_validates_missing_summary(tmp_path: Path):
    submission_dir = tmp_path / "submission"
    submission_dir.mkdir()
    task_dir = submission_dir / "101"
    task_dir.mkdir()
    (task_dir / "agent_response.json").write_text("{}", encoding="utf-8")
    (task_dir / "network.har").write_text("{}", encoding="utf-8")

    handler = SubmitHandler(submission_dir=submission_dir, hf_repo="org/repo", hf_token="token")
    with pytest.raises(ValueError, match="summary.json"):
        handler.submit(name="TeamX/ModelY", leaderboard="both", reference="https://example.com")


def test_submit_validates_no_tasks(tmp_path: Path):
    submission_dir = tmp_path / "submission"
    submission_dir.mkdir()
    (submission_dir / "summary.json").write_text(
        json.dumps(
            {
                "packaging_summary": {
                    "tasks_packaged": 0,
                    "tasks_with_issues": 0,
                    "duplicate_tasks": 0,
                    "unknown_tasks": 0,
                    "missing_from_output": 0,
                }
            }
        ),
        encoding="utf-8",
    )

    handler = SubmitHandler(submission_dir=submission_dir, hf_repo="org/repo", hf_token="token")
    with pytest.raises(ValueError, match="No valid numeric task directories"):
        handler.submit(name="TeamX/ModelY", leaderboard="both", reference="https://example.com")


def test_submit_validates_name_format(submission_dir_fixture: Path):
    handler = SubmitHandler(submission_dir=submission_dir_fixture, hf_repo="org/repo", hf_token="token")
    with pytest.raises(ValueError, match="name"):
        handler.submit(name="Invalid Name!", leaderboard="both", reference="https://example.com")


def test_submit_validates_leaderboard_value(submission_dir_fixture: Path):
    handler = SubmitHandler(submission_dir=submission_dir_fixture, hf_repo="org/repo", hf_token="token")
    with pytest.raises(ValueError, match="leaderboard"):
        handler.submit(name="TeamX/ModelY", leaderboard="invalid", reference="https://example.com")


def test_submit_validates_reference_url(submission_dir_fixture: Path):
    handler = SubmitHandler(submission_dir=submission_dir_fixture, hf_repo="org/repo", hf_token="token")
    with pytest.raises(ValueError, match="reference"):
        handler.submit(name="TeamX/ModelY", leaderboard="both", reference="ftp://example.com")


def test_submit_validates_contact_email(submission_dir_fixture: Path):
    handler = SubmitHandler(submission_dir=submission_dir_fixture, hf_repo="org/repo", hf_token="token")
    with pytest.raises(ValueError, match="contact_info"):
        handler.submit(
            name="TeamX/ModelY",
            leaderboard="both",
            reference="https://example.com",
            contact_info="invalid-email",
        )


def test_submit_generates_valid_submission_json(submission_dir_fixture: Path, mock_hf_api):
    _, _, captured = mock_hf_api
    handler = SubmitHandler(submission_dir=submission_dir_fixture, hf_repo="org/repo", hf_token="token")

    result = handler.submit(
        name="TeamX/ModelY",
        leaderboard="both",
        reference="https://example.com/paper",
        version="v1.0",
        contact_info="team@example.com",
    )

    snapshot_dir = captured["snapshot_dir"]
    inbox_prefix = f"submissions/inbox/{result.submission_uid}"
    submission_payload = json.loads((snapshot_dir / inbox_prefix / "submission.json").read_text(encoding="utf-8"))
    submission = IntakeSubmission.model_validate(submission_payload)

    assert submission.name == "TeamX/ModelY"
    assert submission.leaderboard == "both"
    assert submission.reference == "https://example.com/paper"
    assert submission.version == "v1.0"
    assert submission.contact_info == "team@example.com"
    assert submission.packaging_summary.tasks_packaged == 2


def test_submit_generates_valid_manifest_json(submission_dir_fixture: Path, mock_hf_api):
    _, _, captured = mock_hf_api
    handler = SubmitHandler(submission_dir=submission_dir_fixture, hf_repo="org/repo", hf_token="token")

    result = handler.submit(name="TeamX/ModelY", leaderboard="both", reference="https://example.com/paper")

    snapshot_dir = captured["snapshot_dir"]
    inbox_prefix = f"submissions/inbox/{result.submission_uid}"
    manifest_payload = json.loads((snapshot_dir / inbox_prefix / "manifest.json").read_text(encoding="utf-8"))
    manifest = IntakeManifest.model_validate(manifest_payload)

    staging_root = snapshot_dir / inbox_prefix
    for entry in manifest.files:
        assert not entry.path.startswith("/")
        file_path = staging_root / entry.path
        assert file_path.exists()
        assert file_path.stat().st_size == entry.size_bytes

        from hashlib import sha256

        digest = sha256(file_path.read_bytes()).hexdigest()
        assert digest == entry.sha256


def test_submit_manifest_includes_submission_json(submission_dir_fixture: Path, mock_hf_api):
    _, _, captured = mock_hf_api
    handler = SubmitHandler(submission_dir=submission_dir_fixture, hf_repo="org/repo", hf_token="token")

    result = handler.submit(name="TeamX/ModelY", leaderboard="both", reference="https://example.com/paper")

    snapshot_dir = captured["snapshot_dir"]
    inbox_prefix = f"submissions/inbox/{result.submission_uid}"
    manifest_payload = json.loads((snapshot_dir / inbox_prefix / "manifest.json").read_text(encoding="utf-8"))
    paths = {entry["path"] for entry in manifest_payload["files"]}
    assert "submission.json" in paths


def test_submit_single_atomic_commit(submission_dir_fixture: Path, mock_hf_api):
    api_class, api_instance, captured = mock_hf_api
    handler = SubmitHandler(submission_dir=submission_dir_fixture, hf_repo="org/repo", hf_token="token")

    result = handler.submit(name="TeamX/ModelY", leaderboard="both", reference="https://example.com/paper")

    api_class.assert_called_once_with(token="token")
    api_instance.create_commit.assert_called_once()
    commit_kwargs = captured["commit_kwargs"]
    assert commit_kwargs["repo_id"] == "org/repo"
    assert commit_kwargs["repo_type"] == "dataset"
    assert commit_kwargs["create_pr"] is True

    operations = commit_kwargs["operations"]
    op_paths = {op.path_in_repo for op in operations}
    uid = result.submission_uid
    assert f"submissions/inbox/{uid}/submission.json" in op_paths
    assert f"submissions/inbox/{uid}/manifest.json" in op_paths
    assert f"submissions/inbox/{uid}/tasks/101/agent_response.json" in op_paths

    api_instance.upload_folder.assert_not_called()


def test_submit_returns_pr_url(submission_dir_fixture: Path, mock_hf_api):
    handler = SubmitHandler(submission_dir=submission_dir_fixture, hf_repo="org/repo", hf_token="token")
    result = handler.submit(name="TeamX/ModelY", leaderboard="both", reference="https://example.com/paper")

    assert result.pr_url == "https://huggingface.co/datasets/org/repo/discussions/42"
    assert result.pr_number == 42
    assert result.submission_uid
    assert result.hf_repo == "org/repo"
    assert result.tasks_submitted == 2


def test_submit_hf_error_propagation(submission_dir_fixture: Path, monkeypatch: pytest.MonkeyPatch):
    api_instance = Mock()
    api_instance.create_commit.side_effect = RuntimeError("hf failed")
    monkeypatch.setattr("webarena_verified.api.internal.submit_handler.HfApi", Mock(return_value=api_instance))

    handler = SubmitHandler(submission_dir=submission_dir_fixture, hf_repo="org/repo", hf_token="token")

    with pytest.raises(RuntimeError, match="hf failed"):
        handler.submit(name="TeamX/ModelY", leaderboard="both", reference="https://example.com/paper")


def test_submit_success_flow(submission_dir_fixture: Path, mock_hf_api):
    _, _, _ = mock_hf_api
    handler = SubmitHandler(submission_dir=submission_dir_fixture, hf_repo="org/repo", hf_token="token")

    result = handler.submit(name="TeamX/ModelY", leaderboard="both", reference="https://example.com/paper")

    assert result.pr_number == 42
