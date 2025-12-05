import json
from types import MappingProxyType

from webarena_verified.core.utils import logger
from webarena_verified.types.agent_response import MainObjectiveType
from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.data import TaskSubset
from webarena_verified.types.task import WebArenaSite, WebArenaVerifiedTask

TOTAL_TASK_COUNT = 812


class WebArenaVerifiedDataReader:
    def __init__(self, config: WebArenaVerifiedConfig, subset: TaskSubset | None = None):
        self.config = config
        self.subset = subset
        self._task_id_map: MappingProxyType[int, WebArenaVerifiedTask] = self._load_tasks()

    @property
    def tasks(self) -> list[WebArenaVerifiedTask]:
        return list(self._task_id_map.values())

    @property
    def task_id_map(self) -> MappingProxyType[int, WebArenaVerifiedTask]:
        return self._task_id_map

    @property
    def subset_name(self) -> str | None:
        """Return the subset name if a subset is loaded, otherwise None."""
        return None  # Name is derived from filename, not stored in subset

    def get_task_by_id(self, task_id: int) -> WebArenaVerifiedTask:
        """Get a task by its task_id."""
        if task_id not in self.task_id_map:
            raise ValueError(f"Task with id {task_id} not found")
        return self.task_id_map[task_id]

    def get_tasks_by_value_filter(
        self,
        sites: list[WebArenaSite] | None = None,
        template_id: int | None = None,
        action: MainObjectiveType | None = None,
    ) -> list[WebArenaVerifiedTask]:
        """Get tasks filtered by sites, template_id, and/or expected action."""
        filtered_tasks = []
        for task in self.tasks:
            if sites is not None and sorted(sites) != sorted(task.sites):
                continue
            if template_id is not None and task.intent_template_id != template_id:
                continue
            if action is not None and task.expected_agent_response.task_type != action:
                continue
            filtered_tasks.append(task)

        return filtered_tasks

    def _filter_tasks_by_subset(
        self, task_map: dict[int, WebArenaVerifiedTask]
    ) -> MappingProxyType[int, WebArenaVerifiedTask]:
        """Filter tasks by subset.

        Args:
            task_map: Dictionary of all loaded tasks

        Returns:
            Filtered mapping of tasks

        Raises:
            ValueError: If subset is None, contains invalid task IDs, or results in empty task list
        """
        if self.subset is None:
            raise ValueError("Cannot filter tasks: subset is None")

        logger.info(f"Filtering tasks using subset with {len(self.subset.task_ids)} task IDs")

        # Validate that all subset task_ids exist in dataset (fail fast)
        missing_ids = [tid for tid in self.subset.task_ids if tid not in task_map]
        if missing_ids:
            raise ValueError(
                f"Subset contains task IDs that don't exist in dataset: {missing_ids}. "
                f"Available task IDs range from 0 to {max(task_map.keys())}."
            )

        # Filter to only include tasks in subset
        filtered_map = {tid: task_map[tid] for tid in self.subset.task_ids}

        if not filtered_map:
            raise ValueError("Filtered task list is empty. Subset contains no valid tasks.")

        logger.info(f"Loaded {len(filtered_map)} tasks from subset successfully.")
        return MappingProxyType(filtered_map)

    def _load_tasks(self) -> MappingProxyType[int, WebArenaVerifiedTask]:
        """Load and return the test data as a list of VerifiedTask objects.

        If a subset is provided, only load tasks specified in the subset and skip
        the 812-task count validation. Validates that all subset task_ids exist in
        the dataset (fail fast).
        """
        logger.info(f"Loading tasks from: {str(self.config.test_data_file.resolve())!r}")
        raw_data = json.loads(self.config.test_data_file.read_text())

        task_map = {}
        for task in raw_data:
            try:
                validated_task = WebArenaVerifiedTask.model_validate(task)

                # Sanity check for duplicate task_ids
                if validated_task.task_id in task_map:
                    raise ValueError(f"Duplicate task_id found: {validated_task.task_id}")

                task_map[validated_task.task_id] = validated_task
            except Exception as e:
                raise ValueError(f"Failed to parse task with id {task.get('task_id', 'unknown')}: {e}") from e

        # If subset is provided, filter tasks and skip 812-task validation
        if self.subset is not None:
            return self._filter_tasks_by_subset(task_map)

        # No subset: validate full dataset has 812 tasks
        if len(task_map) != TOTAL_TASK_COUNT:
            # Sanity to avoid loading incomplete data
            raise ValueError(f"Expected {TOTAL_TASK_COUNT} tasks, but found {len(task_map)}")

        logger.info(f"Loaded {len(task_map)} tasks successfully.")
        return MappingProxyType(task_map)
