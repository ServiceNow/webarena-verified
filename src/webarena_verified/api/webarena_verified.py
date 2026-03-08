"""Simplified entry point for WebArena Verified evaluation."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from webarena_verified.core.utils import logger
from webarena_verified.environments import MAGENTO_ADMIN_AUTO_LOGIN_HEADER
from webarena_verified.submission import SubmissionPackager, SubmissionUploader
from webarena_verified.submission.models import SubmissionMode
from webarena_verified.types.agent_response import MainObjectiveType
from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.data import TaskSubset
from webarena_verified.types.eval import TaskEvalResult
from webarena_verified.types.submission import PackagedTaskStats, SubmissionResult
from webarena_verified.types.submit_result import SubmitResult
from webarena_verified.types.task import WebArenaSite, WebArenaVerifiedTask
from webarena_verified.types.tracing import NetworkTrace
from webarena_verified.utils import get_package_assets_path

from .internal.data_reader import WebArenaVerifiedDataReader
from .internal.evaluator import WebArenaVerifiedEvaluator


class WebArenaVerified:
    """Facade for WebArena Verified evaluation framework.

    This class provides a stable, high-level API.
    It is the recommended interface for all WebArena Verified operations,
    as it maintains API stability across versions.

    Example:
        ```python
        from webarena_verified.api import WebArenaVerified
        from webarena_verified.types.config import WebArenaVerifiedConfig

        # Initialize with custom config
        config = WebArenaVerifiedConfig(
            environments={
                "__GITLAB__": {
                    "urls": ["http://localhost:8012"],
                    "credentials": {"username": "root", "password": "demopass"}
                }
            }
        )
        wa = WebArenaVerified(config=config)

        # Evaluate a task
        result = wa.evaluate_task(
            task_id=44,
            agent_response=Path("output/44/agent_response.json"),
            network_trace=Path("output/44/network.har")
        )
        ```
    """

    def __init__(self, *, config: Path | WebArenaVerifiedConfig | None = None) -> None:
        """Initialize evaluator with config and load dataset.

        Args:
            config: Optional configuration. Can be:
                - Path to config JSON file
                - WebArenaVerifiedConfig instance
                - None (uses default configuration)

        Raises:
            TypeError: If config type is invalid
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid

        Note:
            Dataset is loaded upfront during initialization for efficient reuse.
        """
        self._config = WebArenaVerified._load_config(config)
        self._reader = WebArenaVerifiedDataReader(self._config)
        self._evaluator = WebArenaVerifiedEvaluator(config=self._config, reader=self._reader)

        logger.info("WebArenaVerified initialized successfully")

    @property
    def config(self) -> WebArenaVerifiedConfig:
        """Access the configuration."""
        return self._config

    def get_task(self, task_id: int) -> WebArenaVerifiedTask:
        """Get a single task by its ID.

        Args:
            task_id: Task ID to retrieve

        Returns:
            WebArenaVerifiedTask instance

        Raises:
            ValueError: If task not found

        Example:
            ```python
            wa = WebArenaVerified()
            task = wa.get_task(42)
            print(task.intent)
            ```
        """
        return self._reader.get_task_by_id(task_id)

    def get_tasks(
        self,
        sites: list[WebArenaSite] | None = None,
        template_id: int | None = None,
        action: MainObjectiveType | None = None,
    ) -> list[WebArenaVerifiedTask]:
        """Get all tasks, optionally filtered by criteria.

        Args:
            sites: Filter by sites (default: None = no filter)
            template_id: Filter by template ID (default: None = no filter)
            action: Filter by action type (default: None = no filter)

        Returns:
            List of tasks matching all filter criteria (AND logic).
            If all parameters are None, returns all tasks.

        Examples:
            Get all tasks:
            ```python
            wa = WebArenaVerified()
            all_tasks = wa.get_tasks()
            print(f"Total tasks: {len(all_tasks)}")
            ```

            Filter by site:
            ```python
            shopping_tasks = wa.get_tasks(sites=[WebArenaSite.SHOPPING])
            ```

            Filter by multiple criteria:
            ```python
            mutate_shopping = wa.get_tasks(
                sites=[WebArenaSite.SHOPPING],
                action=MainObjectiveType.MUTATE
            )
            ```
        """
        if sites is None and template_id is None and action is None:
            return self._reader.tasks
        return self._reader.get_tasks_by_value_filter(sites, template_id, action)

    def evaluate_task(
        self,
        *,
        task_id: int,
        agent_response: Any,
        network_trace: list[dict] | Path | NetworkTrace,
    ) -> TaskEvalResult:
        """Evaluate a single task with automatic format detection.

        Args:
            task_id: ID of the task to evaluate
            agent_response: Agent's response in any of these formats:
                - str: Raw response text (e.g., "answer: 42" or "navigate: https://example.com")
                - dict: Parsed response dict (e.g., {"action": "retrieve", "value": "42"})
                - list: List of values (may result in validation failure)
                - None: No response (may result in validation failure)
                - Path: File path to read response from
            network_trace: Network trace in any of these formats:
                - Path: HAR file path
                - list: Pre-parsed list of network events/requests
                - NetworkTrace: Pre-constructed NetworkTrace object

        Returns:
            TaskEvalResult with status, score, and detailed evaluation results.
            Errors are captured in result.status = EvalStatus.ERROR with result.error_msg.

        Examples:
            String response with HAR file:
            ```python
            wa = WebArenaVerified()
            result = wa.evaluate_task(
                task_id=1,
                agent_response="answer: 42",
                network_trace=Path("trace.har")
            )
            ```

            Dict response with pre-parsed trace:
            ```python
            result = wa.evaluate_task(
                task_id=1,
                agent_response={"action": "retrieve", "value": "42"},
                network_trace=network_events
            )
            ```

            Response from file:
            ```python
            result = wa.evaluate_task(
                task_id=1,
                agent_response=Path("response.txt"),
                network_trace=Path("trace.har")
            )
            ```
        """
        return self._evaluator.evaluate_task(
            task_id=task_id,
            agent_response=agent_response,
            network_trace=network_trace,
        )

    def get_custom_auth_header_name(self, site: str | WebArenaSite) -> str | None:
        """Get custom authentication header name for a given site.

        Args:
            site: Site identifier (string or WebArenaSite enum value)

        Returns:
            Custom authentication header name if the site requires one, None otherwise.
            Currently returns the Magento admin auto-login header for shopping_admin site.

        Example:
            ```python
            wa = WebArenaVerified()

            # Using string
            header = wa.get_custom_auth_header_name("shopping_admin")
            # Returns: "X-M2-Admin-Auto-Login-User"

            # Using enum
            header = wa.get_custom_auth_header_name(WebArenaSite.SHOPPING_ADMIN)
            # Returns: "X-M2-Admin-Auto-Login-User"

            # Other sites
            header = wa.get_custom_auth_header_name("reddit")
            # Returns: None
            ```
        """
        # Normalize to WebArenaSite if it's a string
        if isinstance(site, str):
            site = WebArenaSite(site)

        if site == WebArenaSite.SHOPPING_ADMIN:
            return MAGENTO_ADMIN_AUTO_LOGIN_HEADER
        return None

    def create_submission(
        self,
        output_dirs: list[Path],
        output_dir: Path,
        *,
        leaderboard: str = "both",
        force: bool = False,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> "SubmissionResult":
        """Create submission package from task outputs.

        Args:
            output_dirs: List of output directories to scan
            output_dir: Output directory where submission package will be created
            leaderboard: Target leaderboard scope (hard, full, both)
            force: Whether to overwrite output_dir if it already exists
            progress_callback: Optional callback for progress updates (current, total, task_id)

        Returns:
            SubmissionResult with packaging stats:
                - output_path: Final output path
                - tasks_packaged: List of task IDs successfully packaged
                - packaged_tasks: Coverage counts per leaderboard

        Raises:
            ValueError: If leaderboard is invalid or hard subset is inconsistent
            FileExistsError: If output path already exists and force is False

        Example:
            ```python
            wa = WebArenaVerified()
            result = wa.create_submission(
                output_dirs=[Path("./run1"), Path("./run2")],
                output_dir=Path("./my-submission"),
                leaderboard="both",
                force=True,
            )
            print(f"Packaged {len(result.tasks_packaged)} tasks")
            print(result.packaged_tasks)
            ```
        """
        mode = SubmissionMode(leaderboard)
        packager = SubmissionPackager(run_output_dirs=output_dirs, evaluator_config=self._config)
        result = packager.create_package(output_dir=output_dir, mode=mode, force=force)

        hard_subset_path = get_package_assets_path() / "dataset" / "subsets" / "webarena-verified-hard.json"
        hard_task_ids = set(TaskSubset.from_file(hard_subset_path).task_ids)
        all_task_ids = {task.task_id for task in self.get_tasks()}
        packaged_task_ids = set(result.tasks_packaged)

        packaged_tasks: dict[str, PackagedTaskStats] = {}
        if mode in {SubmissionMode.FULL, SubmissionMode.BOTH}:
            full_expected = len(all_task_ids)
            full_valid = len(packaged_task_ids & all_task_ids)
            packaged_tasks["full"] = PackagedTaskStats(
                valid=full_valid,
                incomplete=0,
                missing=max(full_expected - full_valid, 0),
                expected=full_expected,
            )
        if mode in {SubmissionMode.HARD, SubmissionMode.BOTH}:
            hard_expected = len(all_task_ids & hard_task_ids)
            hard_valid = len(packaged_task_ids & hard_task_ids)
            packaged_tasks["hard"] = PackagedTaskStats(
                valid=hard_valid,
                incomplete=0,
                missing=max(hard_expected - hard_valid, 0),
                expected=hard_expected,
            )

        return SubmissionResult(
            output_path=result.output_path,
            tasks_packaged=result.tasks_packaged,
            packaged_tasks=packaged_tasks,
        )

    def submit(
        self,
        submission_dir: Path,
        *,
        hf_repo: str | None = None,
        hf_token: str | None = None,
    ) -> "SubmitResult":
        import os

        resolved_repo = hf_repo or os.environ.get(
            "WEBARENA_VERIFIED_LEADERBOARD_SUBMISSION_HF_REPO",
            "AmineHA/WebArena-Verified-Submissions-dev",
        )
        uploader = SubmissionUploader(submission_dir=submission_dir, hf_repo=resolved_repo, hf_token=hf_token)
        uploaded = uploader.upload()
        return SubmitResult(
            pr_url=uploaded.pr_url,
            pr_number=uploaded.pr_number,
            submission_uid=uploaded.submission_uid,
            hf_repo=uploaded.hf_repo,
            submission_dir=uploaded.submission_dir,
            tasks_submitted=uploaded.tasks_submitted,
        )

    @staticmethod
    def _load_config(config: Path | WebArenaVerifiedConfig | None = None) -> WebArenaVerifiedConfig:
        """Load or create a configuration instance.

        This static method provides a reusable way to load configurations without
        instantiating the WebArenaVerified class.

        Args:
            config: Optional configuration. Can be:
                - Path to config JSON file
                - WebArenaVerifiedConfig instance
                - None (uses default configuration)

        Returns:
            WebArenaVerifiedConfig instance

        Raises:
            TypeError: If config type is invalid
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid

        Examples:
            Load from file:
            ```python
            config = WebArenaVerified.load_config(Path("config.json"))
            ```

            Pass through existing config:
            ```python
            existing = WebArenaVerifiedConfig()
            config = WebArenaVerified.load_config(existing)
            ```
        """
        if config is None:
            logger.info("No config provided, using default configuration")
            return WebArenaVerifiedConfig()
        if isinstance(config, Path):
            logger.info(f"Loading config from: {config}")
            return WebArenaVerifiedConfig.from_file(config)
        if isinstance(config, WebArenaVerifiedConfig):
            return config
        raise TypeError(f"Config must be Path, WebArenaVerifiedConfig, or None, got {type(config)}")
