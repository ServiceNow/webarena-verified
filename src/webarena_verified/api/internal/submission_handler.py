"""Handler for submission package creation."""

import datetime
import hashlib
import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from webarena_verified.core.utils import logger
from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.leaderboard import IntakeManifest, IntakeManifestFile
from webarena_verified.types.submission import PackagedTaskStats, SubmissionResult


class SubmissionHandler:
    """Handler for creating submission packages."""

    _MANIFEST_FILE_NAME = "manifest.json"
    _SUBMISSION_FILE_NAME = "submission.json"
    _MANIFEST_SCHEMA_VERSION = "1.0"
    _LEADERBOARD_CHOICES = {"hard", "full", "both"}

    _NAME_PLACEHOLDER = "<EDIT: your submission name, e.g. MySystem-v1>"
    _REFERENCE_PLACEHOLDER = "<EDIT: https://link-to-paper-or-model>"

    def __init__(
        self,
        output_dirs: list[Path],
        config: WebArenaVerifiedConfig,
        full_task_ids: set[int],
        hard_task_ids: set[int],
    ) -> None:
        self.output_dirs = output_dirs
        self.config = config
        self.full_task_ids = full_task_ids
        self.hard_task_ids = hard_task_ids

    def create_submission(
        self,
        output_dir: Path,
        *,
        leaderboard: str,
        force: bool = False,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> SubmissionResult:
        if leaderboard not in self._LEADERBOARD_CHOICES:
            valid = ", ".join(sorted(self._LEADERBOARD_CHOICES))
            raise ValueError(f"Invalid leaderboard '{leaderboard}'. Must be one of: {valid}")

        if output_dir.exists():
            if not force:
                raise FileExistsError(
                    f"Output path already exists: {output_dir}. Use --force to overwrite the existing directory."
                )
            if output_dir.is_dir():
                shutil.rmtree(output_dir)
            else:
                output_dir.unlink()

        discovery_result = self._discover_task_outputs()
        duplicate_task_ids = sorted(discovery_result["duplicate_tasks"].keys())
        if duplicate_task_ids:
            logger.warning(
                "Found duplicate task IDs in multiple output directories. "
                f"Using first occurrence for task IDs: {duplicate_task_ids}"
            )

        expected_task_ids_by_board, task_ids_to_package = self._resolve_task_sets(leaderboard)
        packaged_tasks_stats = self._compute_packaged_task_stats(
            found_tasks=discovery_result["found_tasks"],
            expected_task_ids_by_board=expected_task_ids_by_board,
        )

        for board, stats in packaged_tasks_stats.items():
            if stats.valid == 0:
                if board == "hard" and leaderboard == "both":
                    raise ValueError(
                        "No valid hard tasks found (0/expected). "
                        "Use --leaderboard full if your run outputs do not include hard tasks."
                    )
                raise ValueError(f"No valid {board} tasks found (0/{stats.expected}).")

        return self._package_tasks(
            found_tasks=discovery_result["found_tasks"],
            task_ids_to_package=task_ids_to_package,
            output_path=output_dir,
            leaderboard=leaderboard,
            packaged_tasks_stats=packaged_tasks_stats,
            progress_callback=progress_callback,
        )

    def _discover_task_outputs(self) -> dict[str, Any]:
        found_tasks: dict[int, Path] = {}
        duplicate_tasks: dict[int, list[Path]] = {}
        unknown_tasks: dict[int, Path] = {}

        for output_dir in self.output_dirs:
            if not output_dir.exists():
                continue

            for task_dir in output_dir.iterdir():
                if not task_dir.is_dir() or not task_dir.name.isdigit():
                    continue

                task_id = int(task_dir.name)
                if task_id not in self.full_task_ids:
                    unknown_tasks[task_id] = task_dir
                    continue

                if task_id in found_tasks:
                    if task_id not in duplicate_tasks:
                        duplicate_tasks[task_id] = [found_tasks[task_id]]
                    duplicate_tasks[task_id].append(task_dir)
                else:
                    found_tasks[task_id] = task_dir

        return {
            "found_tasks": found_tasks,
            "duplicate_tasks": duplicate_tasks,
            "unknown_tasks": unknown_tasks,
        }

    def _resolve_task_sets(self, leaderboard: str) -> tuple[dict[str, set[int]], set[int]]:
        if leaderboard == "hard":
            return {"hard": self.hard_task_ids}, self.hard_task_ids
        if leaderboard == "full":
            return {"full": self.full_task_ids}, self.full_task_ids
        return {"full": self.full_task_ids, "hard": self.hard_task_ids}, self.full_task_ids

    def _compute_packaged_task_stats(
        self,
        *,
        found_tasks: dict[int, Path],
        expected_task_ids_by_board: dict[str, set[int]],
    ) -> dict[str, PackagedTaskStats]:
        stats_by_board: dict[str, PackagedTaskStats] = {}
        for board, expected_task_ids in expected_task_ids_by_board.items():
            valid = 0
            incomplete = 0
            missing = 0

            for task_id in expected_task_ids:
                task_dir = found_tasks.get(task_id)
                if task_dir is None:
                    missing += 1
                    continue

                has_agent_response, has_network_har = self._has_required_files(task_dir)
                if has_agent_response and has_network_har:
                    valid += 1
                elif has_agent_response or has_network_har:
                    incomplete += 1
                else:
                    missing += 1

            expected = len(expected_task_ids)
            if valid + incomplete + missing != expected:
                raise ValueError(
                    f"Internal packaging stats error for {board}: {valid} + {incomplete} + {missing} != {expected}"
                )

            stats_by_board[board] = PackagedTaskStats(
                valid=valid,
                incomplete=incomplete,
                missing=missing,
                expected=expected,
            )

        return stats_by_board

    def _package_tasks(
        self,
        *,
        found_tasks: dict[int, Path],
        task_ids_to_package: set[int],
        output_path: Path,
        leaderboard: str,
        packaged_tasks_stats: dict[str, PackagedTaskStats],
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> SubmissionResult:
        packaged_tasks: list[int] = []
        incomplete_tasks: list[int] = []

        selected_task_ids = [task_id for task_id in sorted(task_ids_to_package) if task_id in found_tasks]
        total_tasks = len(selected_task_ids)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            for idx, task_id in enumerate(selected_task_ids, 1):
                if progress_callback:
                    progress_callback(idx, total_tasks, task_id)

                task_dir = found_tasks[task_id]
                agent_response = task_dir / self.config.agent_response_file_name
                network_har = task_dir / self.config.trace_file_name
                has_agent_response, has_network_har = self._has_required_files(task_dir)

                if not has_agent_response or not has_network_har:
                    if has_agent_response or has_network_har:
                        incomplete_tasks.append(task_id)
                    continue

                task_tmp_dir = tmp_path / str(task_id)
                task_tmp_dir.mkdir(exist_ok=True)
                shutil.copy2(agent_response, task_tmp_dir / self.config.agent_response_file_name)
                shutil.copy2(network_har, task_tmp_dir / self.config.trace_file_name)
                packaged_tasks.append(task_id)

            if incomplete_tasks:
                logger.warning(f"Skipped incomplete tasks (one required file missing): {sorted(incomplete_tasks)}")

            submission_payload = self._build_submission_payload(
                leaderboard=leaderboard,
                packaged_tasks_stats=packaged_tasks_stats,
            )
            (tmp_path / self._SUBMISSION_FILE_NAME).write_text(
                json.dumps(submission_payload, indent=2) + "\n",
                encoding="utf-8",
            )

            manifest_entries = self._build_manifest_entries(tmp_path)
            manifest = IntakeManifest(
                schema_version=self._MANIFEST_SCHEMA_VERSION,
                created_at_utc=self._now_utc_z(),
                files=manifest_entries,
            )
            (tmp_path / self._MANIFEST_FILE_NAME).write_text(
                manifest.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(tmp_path, output_path)

        return SubmissionResult(
            output_path=str(output_path),
            tasks_packaged=sorted(packaged_tasks),
            packaged_tasks=packaged_tasks_stats,
        )

    def _build_submission_payload(
        self,
        *,
        leaderboard: str,
        packaged_tasks_stats: dict[str, PackagedTaskStats],
    ) -> dict[str, Any]:
        return {
            "name": self._NAME_PLACEHOLDER,
            "leaderboard": leaderboard,
            "reference": self._REFERENCE_PLACEHOLDER,
            "version": None,
            "contact_info": None,
            "packaged_tasks": {
                key: stats.model_dump(mode="json") for key, stats in sorted(packaged_tasks_stats.items())
            },
        }

    def _has_required_files(self, task_dir: Path) -> tuple[bool, bool]:
        has_agent_response = (task_dir / self.config.agent_response_file_name).exists()
        has_network_har = (task_dir / self.config.trace_file_name).exists()
        return has_agent_response, has_network_har

    def _build_manifest_entries(self, output_dir: Path) -> list[IntakeManifestFile]:
        entries: list[IntakeManifestFile] = []
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file() or path.name == self._MANIFEST_FILE_NAME:
                continue
            relative = path.relative_to(output_dir).as_posix()
            entries.append(
                IntakeManifestFile(
                    path=relative,
                    sha256=self._sha256(path),
                    size_bytes=path.stat().st_size,
                )
            )
        return entries

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now_utc_z() -> str:
        return datetime.datetime.now(tz=datetime.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
