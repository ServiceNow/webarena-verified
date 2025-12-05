"""Handler for submission package creation."""

import datetime
import re
import shutil
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from webarena_verified.core.utils import logger
from webarena_verified.core.utils.trim_network_logs import trim_har_file
from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.submission import SubmissionResult
from webarena_verified.types.submission_summary import (
    DuplicateTasks,
    MissingFileCategory,
    MissingFiles,
    MissingFromOutput,
    PackagedTasks,
    PackagingSummary,
    SubmissionIssues,
    SubmissionSummary,
    SummaryMetadata,
    UnknownTasks,
)


class SubmissionHandler:
    """Handler for creating submission packages.

    Scans output directories for completed tasks, trims network traces,
    and packages them into a tar.gz archive or folder.
    """

    def __init__(
        self,
        output_dirs: list[Path],
        config: WebArenaVerifiedConfig,
        valid_task_ids: set[int],
    ):
        """Initialize handler.

        Args:
            output_dirs: List of output directories to scan for task outputs
            config: Configuration containing file template names
            valid_task_ids: Set of valid task IDs from the dataset
        """
        self.output_dirs = output_dirs
        self.config = config
        self.valid_task_ids = valid_task_ids

    @staticmethod
    def _validate_custom_name(name: str) -> None:
        """Validate custom submission name.

        Args:
            name: Custom name to validate

        Raises:
            ValueError: If name contains invalid characters or is empty
        """
        if not name or not name.strip():
            raise ValueError("Submission name cannot be empty")

        # Allow alphanumeric, hyphens, underscores only
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            raise ValueError(
                f"Invalid submission name '{name}'. Only alphanumeric characters, hyphens, and underscores are allowed."
            )

    def create_submission(
        self,
        output_root: Path,
        *,
        no_tar: bool = False,
        custom_name: str | None = None,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> SubmissionResult:
        """Create submission package from task outputs.

        Never fails - always creates a package with summary.json documenting issues.

        Args:
            output_root: Root directory where submission will be created
            no_tar: If True, output as folder instead of tar.gz
            custom_name: Optional custom name for the submission package (auto-generates timestamp if None)
            progress_callback: Optional callback for progress updates (current, total, task_id)

        Returns:
            SubmissionResult with comprehensive issue tracking and summary_file path

        Raises:
            ValueError: If custom_name contains invalid characters
            FileExistsError: If output path already exists
        """
        # Generate output path (custom or auto-generated with timestamp)
        output_path = self._generate_output_path(output_root, no_tar, custom_name)

        # Discover tasks using reader's task IDs as source of truth
        discovery_result = self._discover_task_outputs()

        # Package tasks (never fails, creates summary.json)
        result = self._package_tasks(discovery_result, output_path, no_tar, progress_callback)

        return result

    def _generate_output_path(self, output_root: Path, no_tar: bool, custom_name: str | None = None) -> Path:
        """Generate output path with custom or auto-generated name.

        Args:
            output_root: Root directory for output
            no_tar: If True, output as folder; if False, output as tar.gz
            custom_name: Optional custom name (if None, auto-generates timestamp)

        Returns:
            Full output path

        Raises:
            ValueError: If custom_name contains invalid characters
            FileExistsError: If output path already exists
        """
        if custom_name:
            # Strip .tar.gz or .tar extension if user provided it (case-insensitive)
            name = custom_name
            for suffix in (".tar.gz", ".TAR.GZ", ".tar", ".TAR"):
                name = name.removesuffix(suffix)

            # Validate custom name (after stripping extensions)
            self._validate_custom_name(name)
        else:
            # Auto-generate timestamp-based name
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"webarena-verified-submission-{timestamp}"

        # Construct full path
        if no_tar:
            output_path = output_root / name
        else:
            output_path = output_root / f"{name}.tar.gz"

        # Check for conflicts
        if output_path.exists():
            raise FileExistsError(
                f"Output path already exists: {output_path}. "
                "Please choose a different name or remove the existing file."
            )

        return output_path

    def _discover_task_outputs(self) -> dict[str, Any]:
        """Discover task outputs and categorize them.

        Returns:
            Dict containing:
                - found_tasks: dict[int, Path] - Valid tasks found in output dirs
                - duplicate_tasks: dict[int, list[Path]] - Tasks in multiple dirs
                - unknown_tasks: dict[int, Path] - Tasks not in reader's dataset
                - missing_tasks: list[int] - Valid task IDs with no output
        """
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

                # Check if task is in reader's dataset
                if task_id not in self.valid_task_ids:
                    unknown_tasks[task_id] = task_dir
                    continue

                # Track duplicates (use first found)
                if task_id in found_tasks:
                    if task_id not in duplicate_tasks:
                        duplicate_tasks[task_id] = [found_tasks[task_id]]
                    duplicate_tasks[task_id].append(task_dir)
                else:
                    found_tasks[task_id] = task_dir

        # Find missing tasks
        missing_tasks = sorted(self.valid_task_ids - set(found_tasks.keys()))

        return {
            "found_tasks": found_tasks,
            "duplicate_tasks": duplicate_tasks,
            "unknown_tasks": unknown_tasks,
            "missing_tasks": missing_tasks,
        }

    def _create_summary(
        self,
        discovery_result: dict[str, Any],
        packaged_tasks: list[int],
        missing_agent_response: list[int],
        missing_network_har: list[int],
        missing_both_files: list[int],
        invalid_har_files: list[int],
        empty_agent_response: list[int],
    ) -> SubmissionSummary:
        """Create summary data for the submission package."""
        return SubmissionSummary(
            metadata=SummaryMetadata(
                created_at=datetime.datetime.now(datetime.UTC).isoformat(),
                total_valid_tasks=len(self.valid_task_ids),
                output_directories=[str(d) for d in self.output_dirs],
            ),
            packaging_summary=PackagingSummary(
                tasks_packaged=len(packaged_tasks),
                tasks_with_issues=(
                    len(missing_agent_response)
                    + len(missing_network_har)
                    + len(missing_both_files)
                    + len(invalid_har_files)
                    + len(empty_agent_response)
                ),
                duplicate_tasks=len(discovery_result["duplicate_tasks"]),
                unknown_tasks=len(discovery_result["unknown_tasks"]),
                missing_from_output=len(discovery_result["missing_tasks"]),
            ),
            packaged_tasks=PackagedTasks(
                task_ids=sorted(packaged_tasks),
                count=len(packaged_tasks),
                expected_count=len(self.valid_task_ids),
            ),
            issues=SubmissionIssues(
                missing_files=MissingFiles(
                    missing_agent_response_only=MissingFileCategory(
                        task_ids=sorted(missing_agent_response),
                        count=len(missing_agent_response),
                        file=self.config.agent_response_file_name,
                    ),
                    missing_network_har_only=MissingFileCategory(
                        task_ids=sorted(missing_network_har),
                        count=len(missing_network_har),
                        file=self.config.trace_file_name,
                    ),
                    missing_both_files=MissingFileCategory(
                        task_ids=sorted(missing_both_files),
                        count=len(missing_both_files),
                        files=[
                            self.config.agent_response_file_name,
                            self.config.trace_file_name,
                        ],
                    ),
                    invalid_har_files=MissingFileCategory(
                        task_ids=sorted(invalid_har_files),
                        count=len(invalid_har_files),
                        description="HAR files that exist but are invalid or empty",
                    ),
                    empty_agent_response=MissingFileCategory(
                        task_ids=sorted(empty_agent_response),
                        count=len(empty_agent_response),
                        description="Agent response files that exist but are empty",
                    ),
                ),
                duplicate_tasks=DuplicateTasks(
                    description="Task IDs found in multiple output directories",
                    task_ids=sorted(discovery_result["duplicate_tasks"].keys()),
                    count=len(discovery_result["duplicate_tasks"]),
                    details={
                        str(tid): [str(p) for p in paths]
                        for tid, paths in sorted(discovery_result["duplicate_tasks"].items())
                    },
                ),
                unknown_tasks=UnknownTasks(
                    description="Task IDs not in dataset but found in output directories",
                    task_ids=sorted(discovery_result["unknown_tasks"].keys()),
                    count=len(discovery_result["unknown_tasks"]),
                    details={str(tid): str(path) for tid, path in sorted(discovery_result["unknown_tasks"].items())},
                ),
                missing_from_output=MissingFromOutput(
                    description="Valid task IDs with no corresponding output directory",
                    task_ids=discovery_result["missing_tasks"],
                    count=len(discovery_result["missing_tasks"]),
                ),
            ),
        )

    def _package_tasks(
        self,
        discovery_result: dict[str, Any],
        output_path: Path,
        no_tar: bool,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> SubmissionResult:
        """Package tasks into output.

        Args:
            discovery_result: Result from _discover_task_outputs()
            output_path: Final output path (with timestamp)
            no_tar: If True, output as folder

        Returns:
            SubmissionResult with summary file included
        """
        found_tasks = discovery_result["found_tasks"]
        total_tasks = len(found_tasks)

        packaged_tasks: list[int] = []
        missing_agent_response: list[int] = []
        missing_network_har: list[int] = []
        missing_both_files: list[int] = []
        invalid_har_files: list[int] = []
        empty_agent_response: list[int] = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            for idx, (task_id, task_dir) in enumerate(sorted(found_tasks.items()), 1):
                # Report progress
                if progress_callback:
                    progress_callback(idx, total_tasks, task_id)
                agent_response = task_dir / self.config.agent_response_file_name
                network_har = task_dir / self.config.trace_file_name

                has_agent_response = agent_response.exists()
                has_network_har = network_har.exists()

                # Track missing files
                if not has_agent_response and not has_network_har:
                    missing_both_files.append(task_id)
                elif not has_agent_response:
                    missing_agent_response.append(task_id)
                elif not has_network_har:
                    missing_network_har.append(task_id)

                # Skip if either file is missing
                if not has_agent_response or not has_network_har:
                    continue

                # Create task subfolder and copy files
                task_tmp_dir = tmp_path / str(task_id)
                task_tmp_dir.mkdir(exist_ok=True)

                # Check if agent response is empty before copying
                if agent_response.stat().st_size == 0:
                    empty_agent_response.append(task_id)

                # Copy agent response
                shutil.copy2(agent_response, task_tmp_dir / self.config.agent_response_file_name)

                try:
                    trim_har_file(network_har, task_tmp_dir / self.config.trace_file_name)
                    packaged_tasks.append(task_id)
                except (ValueError, FileNotFoundError, KeyError) as e:
                    invalid_har_files.append(task_id)
                    logger.debug(f"Task {task_id}: Invalid HAR file - {e}")

            # Create summary.json
            summary_data = self._create_summary(
                discovery_result=discovery_result,
                packaged_tasks=packaged_tasks,
                missing_agent_response=missing_agent_response,
                missing_network_har=missing_network_har,
                missing_both_files=missing_both_files,
                invalid_har_files=invalid_har_files,
                empty_agent_response=empty_agent_response,
            )
            summary_file = tmp_path / "summary.json"
            summary_file.write_text(summary_data.model_dump_json(indent=2))

            # Output as folder or tar
            archive_size = None
            summary_file_path = None
            if no_tar:
                shutil.copytree(tmp_path, output_path)
                summary_file_path = str(output_path / "summary.json")
            else:
                with tarfile.open(output_path, "w:gz") as tar:
                    # Add summary.json at root level
                    tar.add(summary_file, arcname="summary.json")

                    # Add task subdirectories
                    for task_subdir in sorted(tmp_path.iterdir()):
                        if task_subdir.name != "summary.json":
                            tar.add(task_subdir, arcname=task_subdir.name)
                archive_size = output_path.stat().st_size

                # Create external summary file alongside the tar
                external_summary_path = output_path.parent / f"{output_path.stem}_summary.json"
                external_summary_path.write_text(summary_data.model_dump_json(indent=2))
                summary_file_path = str(external_summary_path)

        return SubmissionResult(
            output_path=str(output_path),
            is_tar=not no_tar,
            tasks_packaged=packaged_tasks,
            missing_agent_response=missing_agent_response,
            missing_network_har=missing_network_har,
            missing_both_files=missing_both_files,
            invalid_har_files=invalid_har_files,
            empty_agent_response=empty_agent_response,
            duplicate_task_ids=sorted(discovery_result["duplicate_tasks"].keys()),
            unknown_task_ids=sorted(discovery_result["unknown_tasks"].keys()),
            missing_task_ids=discovery_result["missing_tasks"],
            archive_size=archive_size,
            summary_file=summary_file_path,
        )
