from __future__ import annotations

import datetime as dt
import hashlib
import shutil
import tempfile
import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from webarena_verified.core.utils import logger
from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.data import TaskSubset
from webarena_verified.utils import get_package_assets_path

from .config import SubmissionFlowConfig
from .models import (
    EvaluatorArtifactName,
    ManifestFileEntry,
    SubmissionInternalMetadata,
    SubmissionManifest,
    SubmissionMetadata,
    SubmissionMode,
)


class SubmissionPackageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_path: str
    tasks_packaged: list[int]
    submission_uid: str


class SubmissionPackager:
    def __init__(
        self,
        *,
        run_output_dirs: list[Path],
        evaluator_config: WebArenaVerifiedConfig,
        flow_config: SubmissionFlowConfig | None = None,
    ) -> None:
        self._run_output_dirs = run_output_dirs
        self._evaluator_config = evaluator_config
        self._flow_config = flow_config or SubmissionFlowConfig()
        hard_subset_path = (
            get_package_assets_path() / "dataset" / "subsets" / f"{self._flow_config.hard_subset_name}.json"
        )
        self._hard_task_ids = set(TaskSubset.from_file(hard_subset_path).task_ids)

    def create_package(self, *, output_dir: Path, mode: SubmissionMode, force: bool = False) -> SubmissionPackageResult:
        if output_dir.exists():
            if not force:
                raise FileExistsError(
                    f"Output path already exists: {output_dir}. Use --force to overwrite the existing directory."
                )
            if output_dir.is_dir():
                shutil.rmtree(output_dir)
            else:
                output_dir.unlink()

        discovered_tasks = self._discover_valid_tasks()
        if not discovered_tasks:
            raise ValueError("No valid numeric task directories found with required files")

        selected_tasks = self._select_tasks_for_mode(discovered_tasks=discovered_tasks, mode=mode)
        if not selected_tasks:
            raise ValueError(f"No tasks available for submission mode '{mode.value}'")

        submission_uid = str(uuid.uuid4())
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            copied_task_ids = self._copy_tasks(temp_dir=temp_dir, tasks=selected_tasks)
            if not copied_task_ids:
                raise ValueError("No valid tasks were copied into submission package")

            metadata = SubmissionMetadata(
                submission_uid=submission_uid,
                name="<EDIT: your submission name, e.g. MySystem-v1>",
                model="<EDIT: your model identifier, e.g. gpt-4.1-mini>",
                reference="https://example.com/replace-me",
                contact_email="replace-me@example.com",
                submitted_tasks=len(copied_task_ids),
                task_network_filename=self._flow_config.task_network_file_name,
            )
            (temp_dir / self._flow_config.submission_file_name).write_text(
                metadata.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )

            manifest_entries = self._build_manifest_entries(temp_dir)
            manifest = SubmissionManifest(
                schema_version=self._flow_config.schema_version,
                created_at_utc=self._now_utc_z(),
                files=manifest_entries,
            )
            manifest_path = temp_dir / self._flow_config.manifest_file_name
            manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")

            internal = SubmissionInternalMetadata(
                schema_version=self._flow_config.schema_version,
                submission_uid=submission_uid,
                submission_mode=mode,
                source_sha=self._flow_config.source_sha_placeholder,
                generated_at_utc=self._now_utc_z(),
                manifest_sha256=self._sha256_file(manifest_path),
                submission_package_checksum=self._compute_package_checksum(temp_dir),
                submission_package_checksum_algo=self._flow_config.checksum_algo,
            )
            (temp_dir / self._flow_config.internal_file_name).write_text(
                internal.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )

            output_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(temp_dir, output_dir)

        return SubmissionPackageResult(
            output_path=str(output_dir),
            tasks_packaged=sorted(copied_task_ids),
            submission_uid=submission_uid,
        )

    def _discover_valid_tasks(self) -> dict[int, Path]:
        tasks: dict[int, Path] = {}
        for run_output_dir in self._run_output_dirs:
            if not run_output_dir.exists() or not run_output_dir.is_dir():
                continue
            for child in sorted(run_output_dir.iterdir(), key=lambda item: item.name):
                if not child.is_dir() or not child.name.isdigit():
                    continue
                task_id = int(child.name)
                if task_id in tasks:
                    continue
                if self._is_valid_task_folder(child):
                    tasks[task_id] = child
        return tasks

    def _is_valid_task_folder(self, task_dir: Path) -> bool:
        agent_path = task_dir / self._evaluator_config.agent_response_file_name
        trace_path = task_dir / self._evaluator_config.trace_file_name
        return agent_path.exists() and trace_path.exists()

    def _select_tasks_for_mode(self, *, discovered_tasks: dict[int, Path], mode: SubmissionMode) -> dict[int, Path]:
        if mode == SubmissionMode.FULL:
            return discovered_tasks

        hard_only_tasks = {
            task_id: path for task_id, path in discovered_tasks.items() if task_id in self._hard_task_ids
        }
        if mode == SubmissionMode.HARD:
            return hard_only_tasks

        if not hard_only_tasks:
            raise ValueError("Submission mode 'both' requires at least one hard-subset task")
        return discovered_tasks

    def _copy_tasks(self, *, temp_dir: Path, tasks: dict[int, Path]) -> list[int]:
        copied: list[int] = []
        for task_id, source_dir in sorted(tasks.items(), key=lambda item: item[0]):
            destination_dir = temp_dir / str(task_id)
            destination_dir.mkdir(parents=True, exist_ok=True)

            agent_source = source_dir / self._evaluator_config.agent_response_file_name
            network_source = source_dir / self._evaluator_config.trace_file_name
            shutil.copy2(agent_source, destination_dir / self._flow_config.task_agent_response_file_name)
            shutil.copy2(network_source, destination_dir / self._flow_config.task_network_file_name)

            for artifact in EvaluatorArtifactName:
                artifact_path = source_dir / artifact.value
                if artifact_path.exists():
                    logger.debug("Ignoring evaluator artifact in source run folder: %s", artifact_path)

            copied.append(task_id)
        return copied

    def _build_manifest_entries(self, root_dir: Path) -> list[ManifestFileEntry]:
        entries: list[ManifestFileEntry] = []
        for file_path in sorted(root_dir.rglob("*")):
            if not file_path.is_file():
                continue
            relative_path = file_path.relative_to(root_dir).as_posix()
            if relative_path in {
                self._flow_config.manifest_file_name,
                self._flow_config.internal_file_name,
            }:
                continue
            entries.append(
                ManifestFileEntry(
                    path=relative_path,
                    sha256=self._sha256_file(file_path),
                    size_bytes=file_path.stat().st_size,
                )
            )
        return entries

    def _compute_package_checksum(self, root_dir: Path) -> str:
        digest = hashlib.sha256()
        for file_path in sorted(root_dir.rglob("*")):
            if not file_path.is_file() or file_path.name in {
                self._flow_config.internal_file_name,
                self._flow_config.manifest_file_name,
            }:
                continue
            relative_path = file_path.relative_to(root_dir).as_posix()
            digest.update(relative_path.encode("utf-8"))
            digest.update(b"\n")
            digest.update(file_path.read_bytes())
            digest.update(b"\n")
        return digest.hexdigest()

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now_utc_z() -> str:
        return dt.datetime.now(tz=dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
