"""Manager for task subset operations."""

import json
import subprocess
from pathlib import Path
from typing import TypedDict

from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.data import TaskSubset
from webarena_verified.utils import get_package_assets_path

from .data_reader import WebArenaVerifiedDataReader


class SubsetInfo(TypedDict):
    """Information about a subset."""

    name: str
    description: str
    task_count: int
    path: str
    error: str | None


class ChecksumInfo(TypedDict):
    """Information about checksum recomputation."""

    old_checksum: str
    new_checksum: str
    file_path: str
    had_uncommitted_changes: bool


class CreationInfo(TypedDict):
    """Information about subset creation."""

    name: str
    task_count: int
    description: str | None
    file_path: str


class SubsetsManager:
    """Manager class for task subset operations.

    Handles all subset-related operations including loading, exporting,
    listing, checksum recomputation, and creation.

    All methods raise exceptions on errors rather than returning status codes.
    Methods return data structures that the CLI can use for printing.
    """

    def __init__(self, config: WebArenaVerifiedConfig | None = None):
        """Initialize SubsetsManager.

        Args:
            config: WebArenaVerifiedConfig instance (if None, creates default)
        """
        self.config = config or WebArenaVerifiedConfig()
        self.subsets_dir = get_package_assets_path() / "dataset/subsets"

    def get_subset_path(self, name: str | None = None, path: str | None = None) -> Path:
        """Get subset file path from name or path.

        Args:
            name: Subset name (filename without .json)
            path: Direct path to subset file

        Returns:
            Path to subset file

        Raises:
            ValueError: If neither or both name and path are provided
        """
        if name and path:
            raise ValueError("Cannot specify both name and path")
        if not name and not path:
            raise ValueError("Must specify either name or path")

        if name:
            return self.subsets_dir / f"{name}.json"
        return Path(path)  # type: ignore

    def export_subset(self, subset_path: Path, output_path: Path) -> int:
        """Export subset tasks to JSON file.

        Args:
            subset_path: Path to subset file
            output_path: Output file path

        Returns:
            Number of tasks exported

        Raises:
            FileNotFoundError: If subset file doesn't exist
            ValueError: If subset is invalid
        """
        # Load subset
        subset = TaskSubset.from_file(subset_path)

        # Load config and tasks
        reader = WebArenaVerifiedDataReader(self.config, subset=subset)

        # Export tasks to JSON
        tasks_data = [task.model_dump(mode="json") for task in reader.tasks]
        assert len(tasks_data) == len(subset.task_ids), "Mismatch in task count while exporting subset"
        output_path.write_text(json.dumps(tasks_data, indent=2))  # TODO use the writer utility

        return len(tasks_data)

    def list_subsets(self) -> list[SubsetInfo]:
        """List all available subsets.

        Returns:
            List of subset information dictionaries

        Raises:
            Exception: If there's an error accessing the subsets directory
        """
        if not self.subsets_dir.exists():
            return []

        subset_files = sorted(self.subsets_dir.glob("*.json"))

        if not subset_files:
            return []

        result: list[SubsetInfo] = []

        for subset_file in subset_files:
            try:
                subset = TaskSubset.from_file(subset_file)
                result.append(
                    {
                        "name": subset_file.stem,
                        "description": subset.description or "(no description)",
                        "task_count": len(subset.task_ids),
                        "path": str(subset_file),
                        "error": None,
                    }
                )
            except Exception as e:
                result.append(
                    {
                        "name": subset_file.stem,
                        "description": "",
                        "task_count": 0,
                        "path": str(subset_file),
                        "error": str(e),
                    }
                )

        return result

    def _is_in_git_repo(self) -> bool:
        """Check if we are in a git repository.

        Returns:
            True if in a git repository, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def recompute_checksum(self, subset_path: Path) -> ChecksumInfo:
        """Recompute and update checksum for a subset.

        Args:
            subset_path: Path to subset file

        Returns:
            Dictionary with checksum information

        Raises:
            FileNotFoundError: If subset file doesn't exist
            ValueError: If subset file is invalid
        """
        had_uncommitted_changes = False

        # Check for uncommitted changes if in git repo
        if self._is_in_git_repo():
            try:
                result = subprocess.run(
                    ["git", "diff", "--name-only", str(subset_path)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                had_uncommitted_changes = bool(result.stdout.strip())
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Git command failed: {e}") from e

        # Load current subset using Pydantic model
        # We need to load the raw content first to get the old checksum,
        # then update using the model
        content = json.loads(subset_path.read_text())
        old_checksum = content.get("checksum", "")

        # Extract task_ids and description
        task_ids = content.get("task_ids", [])
        if not task_ids:
            raise ValueError("Subset file does not contain task_ids")

        description = content.get("description")

        # Create new subset with recomputed checksum
        new_checksum = TaskSubset.compute_checksum(task_ids)
        subset = TaskSubset(
            description=description,
            task_ids=task_ids,
            checksum=new_checksum,
        )

        # Write back using model
        subset_path.write_text(json.dumps(subset.to_dict(), indent=2))

        return {
            "old_checksum": old_checksum,
            "new_checksum": new_checksum,
            "file_path": str(subset_path),
            "had_uncommitted_changes": had_uncommitted_changes,
        }

    def create_subset(self, source_path: Path, name: str, description: str | None = None) -> CreationInfo:
        """Create new subset from source file.

        Args:
            source_path: Path to source JSON file
            name: Name for the new subset
            description: Optional description

        Returns:
            Dictionary with creation information

        Raises:
            FileNotFoundError: If source file doesn't exist
            FileExistsError: If subset file already exists
            ValueError: If source file format is invalid
        """
        # Load source file
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        source_data = json.loads(source_path.read_text())

        # Auto-detect format: array of task objects or array of integers
        if isinstance(source_data, list) and len(source_data) > 0:
            if isinstance(source_data[0], dict):
                # Array of task objects - extract task_ids
                task_ids = [task.get("task_id") for task in source_data]
                if None in task_ids:
                    raise ValueError("Source file contains tasks without task_id field")
            elif isinstance(source_data[0], int):
                # Array of integers
                task_ids = source_data
            else:
                raise ValueError("Source file format not recognized (expected array of objects or integers)")
        else:
            raise ValueError("Source file must be a non-empty array")

        # Create subset using Pydantic model
        checksum = TaskSubset.compute_checksum(task_ids)
        subset = TaskSubset(
            description=description,
            task_ids=task_ids,
            checksum=checksum,
        )

        # Determine output path
        self.subsets_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.subsets_dir / f"{name}.json"

        # Fail if file already exists
        if output_path.exists():
            raise FileExistsError(f"Subset file already exists: {output_path}")

        # Write subset file using model's to_dict method
        output_path.write_text(json.dumps(subset.to_dict(), indent=2))

        return {
            "name": name,
            "task_count": len(task_ids),
            "description": description,
            "file_path": str(output_path),
        }
