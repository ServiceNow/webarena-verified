"""Simplified entry point for WebArena Verified evaluation."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from webarena_verified.core.utils import logger
from webarena_verified.environments import MAGENTO_ADMIN_AUTO_LOGIN_HEADER
from webarena_verified.types.agent_response import MainObjectiveType
from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.eval import TaskEvalResult
from webarena_verified.types.task import WebArenaSite, WebArenaVerifiedTask
from webarena_verified.types.tracing import NetworkTrace

from .internal.data_reader import WebArenaVerifiedDataReader
from .internal.evaluator import WebArenaVerifiedEvaluator

if TYPE_CHECKING:
    from .internal.submission_handler import SubmissionResult


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

    def __init__(self, *, config: Path | WebArenaVerifiedConfig | None = None):
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
            TaskEvalResult with status, score, and detailed evaluation results. Errors are captured in result.status = EvalStatus.ERROR with result.error_msg.

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

    def apply_patches_for_site(self, site: str, exec_patch: Callable[[Callable, str, Any], bool]) -> bool:
        """Apply all patches for a given site using the provided executor.

        This method discovers and applies all patches for the specified site in order.
        Patches are organized by site (reddit, shopping, shopping_admin, etc.) and
        applied based on filename prefix (p01_, p02_, etc.).

        Args:
            site: Site identifier to apply patches for. Valid values:
                  - "reddit": Reddit environment patches
                  - "shopping": Shopping/Magento environment patches
                  - "shopping_admin": Shopping admin environment patches
            exec_patch: Function to execute patches with Docker operations.
                       Should have signature: exec_patch(patch_fn, site, **kwargs) -> bool
                       The executor is responsible for:
                       - Resolving the Docker container name for the site
                       - Calling patch_fn(container_name)
                       - Handling errors and returning success/failure

        Returns:
            True if all patches applied successfully, False if any patch failed

        Example:
            ```python
            from webarena_verified.api import WebArenaVerified

            def my_exec_patch(patch_fn, site: str, **kwargs) -> bool:
                try:
                    container_name = get_container_name(site)
                    return patch_fn(container_name)
                except Exception as e:
                    logger.error(f"Failed to execute patch: {e}")
                    return False

            wa = WebArenaVerified()
            success = wa.apply_patches_for_site("reddit", my_exec_patch)
            if success:
                print("All Reddit patches applied successfully")
            ```
        """
        from .internal.patch_manager import PatchManager

        patch_manager = PatchManager(exec_patch)
        return patch_manager.apply_patches_for_site(site)

    def create_submission(
        self,
        output_dirs: list[Path],
        output_root: Path,
        *,
        no_tar: bool = False,
        custom_name: str | None = None,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> "SubmissionResult":
        """Create submission package from task outputs.

        Never fails - always creates a package with summary.json documenting issues.

        Args:
            output_dirs: List of output directories to scan
            output_root: Root directory where submission will be created
            no_tar: If True, output as folder instead of tar.gz
            custom_name: Optional custom name for submission package (auto-generates timestamp if None)
            progress_callback: Optional callback for progress updates (current, total, task_id)

        Returns:
            SubmissionResult with comprehensive issue tracking:
                - output_path: Final output path (with timestamp)
                - is_tar: True for tar.gz, False for folder
                - tasks_packaged: List of task IDs successfully packaged
                - missing_agent_response: Task IDs missing only agent_response.json
                - missing_network_har: Task IDs missing only network.har
                - missing_both_files: Task IDs missing both required files
                - invalid_har_files: Task IDs with invalid or empty HAR files
                - empty_agent_response: Task IDs with empty agent response files
                - duplicate_task_ids: Task IDs found in multiple directories
                - unknown_task_ids: Task IDs not in reader's dataset
                - missing_task_ids: Valid task IDs with no output directory
                - archive_size: Size in bytes (tar only, None for folder)
                - summary_file: Path to summary.json with detailed issue info

        Raises:
            ValueError: If custom_name contains invalid characters
            FileExistsError: If output path already exists

        Example:
            ```python
            wa = WebArenaVerified()
            result = wa.create_submission(
                output_dirs=[Path("./run1"), Path("./run2")],
                output_root=Path("./submissions"),
                custom_name="experiment-001",  # Optional custom name
            )
            print(f"Packaged {len(result.tasks_packaged)} tasks")
            print(f"Issues: {len(result.duplicate_task_ids)} duplicates")
            print(f"See details: {result.summary_file}")
            ```
        """
        from .internal.submission_handler import SubmissionHandler

        valid_task_ids = set(self._reader.task_id_map.keys())
        handler = SubmissionHandler(output_dirs, self._config, valid_task_ids)
        return handler.create_submission(
            output_root, no_tar=no_tar, custom_name=custom_name, progress_callback=progress_callback
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
        elif isinstance(config, Path):
            logger.info(f"Loading config from: {config}")
            return WebArenaVerifiedConfig.from_file(config)
        elif isinstance(config, WebArenaVerifiedConfig):
            return config
        else:
            raise TypeError(f"Config must be Path, WebArenaVerifiedConfig, or None, got {type(config)}")
