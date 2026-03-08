from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import SubmissionFlowConfig
from .models import (
    EvaluatorArtifactName,
    SubmissionInternalMetadata,
    SubmissionManifest,
    SubmissionMetadata,
)


class SubmissionValidator:
    def __init__(self, flow_config: SubmissionFlowConfig | None = None) -> None:
        self._flow_config = flow_config or SubmissionFlowConfig()

    def validate_submission_tree(
        self, submission_dir: Path
    ) -> tuple[SubmissionMetadata, SubmissionManifest, SubmissionInternalMetadata]:
        if not submission_dir.exists() or not submission_dir.is_dir():
            raise ValueError(f"Submission directory does not exist: {submission_dir}")

        submission = SubmissionMetadata.model_validate(
            self._load_json_object(submission_dir / self._flow_config.submission_file_name)
        )
        manifest = SubmissionManifest.model_validate(
            self._load_json_object(submission_dir / self._flow_config.manifest_file_name)
        )
        internal = SubmissionInternalMetadata.model_validate(
            self._load_json_object(submission_dir / self._flow_config.internal_file_name)
        )

        if submission.submission_uid != internal.submission_uid:
            raise ValueError("submission_uid mismatch between submission.json and _internal.json")

        self._validate_root_and_tasks(submission_dir)
        self._validate_manifest_matches_tree(submission_dir, manifest)
        self._validate_submission_contract(submission_dir, submission)
        self._validate_submission_metadata_values(submission)
        self._validate_internal_checksum(submission_dir, manifest, internal)
        return submission, manifest, internal

    def _validate_root_and_tasks(self, submission_dir: Path) -> None:
        allowed_root_files = {
            self._flow_config.submission_file_name,
            self._flow_config.manifest_file_name,
            self._flow_config.internal_file_name,
        }
        allowed_task_files = {
            self._flow_config.task_agent_response_file_name,
            self._flow_config.task_network_file_name,
        }

        for child in sorted(submission_dir.iterdir(), key=lambda item: item.name):
            if child.is_file():
                if child.name not in allowed_root_files:
                    raise ValueError(f"Unexpected root file in uploaded payload: {child.name}")
                continue
            if not child.is_dir():
                raise ValueError(f"Unexpected non-file path in uploaded payload: {child}")
            if not child.name.isdigit():
                raise ValueError(f"Task folder names must be numeric only. Found: {child.name}")

            present_task_files: set[str] = set()
            for task_file in sorted(child.iterdir(), key=lambda item: item.name):
                if not task_file.is_file():
                    raise ValueError(f"Unexpected nested path in task folder: {task_file}")
                if task_file.name in {artifact.value for artifact in EvaluatorArtifactName}:
                    raise ValueError(
                        f"Uploaded intake payload must not include evaluator artifacts: {child.name}/{task_file.name}"
                    )
                if task_file.name not in allowed_task_files:
                    raise ValueError(f"Unexpected task file in uploaded payload: {child.name}/{task_file.name}")
                present_task_files.add(task_file.name)

            missing_required = sorted(allowed_task_files - present_task_files)
            if missing_required:
                missing = ", ".join(missing_required)
                raise ValueError(f"Task folder {child.name} is missing required file(s): {missing}")

        for forbidden_artifact in EvaluatorArtifactName:
            matches = list(submission_dir.rglob(forbidden_artifact.value))
            if matches:
                example_path = matches[0].relative_to(submission_dir).as_posix()
                raise ValueError(
                    "Uploaded intake payload must not include evaluator artifacts: "
                    f"{forbidden_artifact.value} ({example_path})"
                )

    def _validate_manifest_matches_tree(self, submission_dir: Path, manifest: SubmissionManifest) -> None:
        manifest_paths = [entry.path for entry in manifest.files]
        actual_paths = self._actual_payload_paths(submission_dir)
        if manifest_paths != actual_paths:
            raise ValueError("manifest.files must exactly match uploaded tree paths")

        entry_by_path = {entry.path: entry for entry in manifest.files}
        for relative_path in actual_paths:
            file_path = submission_dir / relative_path
            entry = entry_by_path[relative_path]
            actual_size = file_path.stat().st_size
            actual_sha = self._sha256_file(file_path)
            if entry.size_bytes != actual_size:
                raise ValueError(f"manifest size mismatch for {relative_path}")
            if entry.sha256 != actual_sha:
                raise ValueError(f"manifest hash mismatch for {relative_path}")

    def _validate_submission_contract(self, submission_dir: Path, submission: SubmissionMetadata) -> None:
        task_dirs = sorted(path for path in submission_dir.iterdir() if path.is_dir() and path.name.isdigit())
        if submission.submitted_tasks != len(task_dirs):
            raise ValueError("submission.json submitted_tasks does not match task directory count")

        if submission.task_network_filename != self._flow_config.task_network_file_name:
            raise ValueError("submission.json task_network_filename does not match required task file name")

    @staticmethod
    def _contains_placeholder_text(value: str) -> bool:
        return "<EDIT:" in value

    def _validate_submission_metadata_values(self, submission: SubmissionMetadata) -> None:
        if self._contains_placeholder_text(submission.name):
            raise ValueError("submission.json contains placeholder value in field: name")
        if self._contains_placeholder_text(submission.model):
            raise ValueError("submission.json contains placeholder value in field: model")
        if (
            self._contains_placeholder_text(submission.reference)
            or submission.reference == "https://example.com/replace-me"
        ):
            raise ValueError("submission.json contains placeholder value in field: reference")
        if (
            self._contains_placeholder_text(submission.contact_email)
            or submission.contact_email == "replace-me@example.com"
        ):
            raise ValueError("submission.json contains placeholder value in field: contact_email")

    def _validate_internal_checksum(
        self,
        submission_dir: Path,
        _manifest: SubmissionManifest,
        internal: SubmissionInternalMetadata,
    ) -> None:
        manifest_sha = self._sha256_file(submission_dir / self._flow_config.manifest_file_name)
        if internal.manifest_sha256 != manifest_sha:
            raise ValueError("_internal.json manifest_sha256 does not match manifest.json")

        package_sha = self._compute_package_checksum(submission_dir)
        if internal.submission_package_checksum != package_sha:
            raise ValueError("_internal.json submission_package_checksum mismatch")

    def _actual_payload_paths(self, submission_dir: Path) -> list[str]:
        paths: list[str] = []
        for file_path in sorted(submission_dir.rglob("*")):
            if not file_path.is_file() or file_path.name in {
                self._flow_config.manifest_file_name,
                self._flow_config.internal_file_name,
            }:
                continue
            paths.append(file_path.relative_to(submission_dir).as_posix())
        return paths

    def _compute_package_checksum(self, submission_dir: Path) -> str:
        digest = hashlib.sha256()
        for relative_path in self._actual_payload_paths(submission_dir):
            path = submission_dir / relative_path
            digest.update(relative_path.encode("utf-8"))
            digest.update(b"\n")
            digest.update(path.read_bytes())
            digest.update(b"\n")
        return digest.hexdigest()

    @staticmethod
    def _load_json_object(path: Path) -> dict:
        if not path.exists() or not path.is_file():
            raise ValueError(f"Missing required file: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object in file: {path}")
        return payload

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
