from __future__ import annotations

import logging
from pathlib import Path  # noqa: TC003

from webarena_verified.api import WebArenaVerified
from webarena_verified.submission.config import SubmissionFlowConfig
from webarena_verified.submission.models import SubmissionMetadata, SubmissionMode
from webarena_verified.types.data import TaskSubset
from webarena_verified.types.eval import (
    TaskEvalResult,
    TasksEvalResults,
)
from webarena_verified.types.task import WebArenaVerifiedTask  # noqa: TC001
from webarena_verified.utils import get_package_assets_path

from .models import EvaluationSummaryPayload

logger = logging.getLogger(__name__)


class SubmissionEvaluator:
    """Runs WebArena-Verified evaluators on a submission and produces scoring summaries.

    Delegates individual task evaluation to ``WebArenaVerified.evaluate_task``
    and batch aggregation to ``TasksEvalResults.create``.  Returns
    ``EvaluationSummaryPayload`` instances ready for the leaderboard builder.
    """

    def __init__(self, flow_config: SubmissionFlowConfig | None = None) -> None:
        self._flow_config = flow_config or SubmissionFlowConfig()
        self._wa = WebArenaVerified()
        hard_subset_path = (
            get_package_assets_path() / "dataset" / "subsets" / f"{self._flow_config.hard_subset_name}.json"
        )
        self._hard_task_ids = set(TaskSubset.from_file(hard_subset_path).task_ids)
        self._all_tasks = tuple(self._wa.get_tasks())
        self._all_task_ids = {task.task_id for task in self._all_tasks}

    def evaluate_submission(
        self,
        *,
        submission_dir: Path,
        submission: SubmissionMetadata,
        submission_mode: SubmissionMode,
    ) -> dict[SubmissionMode, EvaluationSummaryPayload]:
        """Evaluate all tasks in a submission and return per-mode summaries."""
        task_dirs = sorted(path for path in submission_dir.iterdir() if path.is_dir() and path.name.isdigit())
        logger.info(
            "Evaluating %d task directories in %s (mode=%s)", len(task_dirs), submission_dir.name, submission_mode
        )
        results: list[TaskEvalResult] = []
        for task_dir in task_dirs:
            task_id = int(task_dir.name)
            result = self._wa.evaluate_task(
                task_id=task_id,
                agent_response=task_dir / self._flow_config.task_agent_response_file_name,
                network_trace=task_dir / self._flow_config.task_network_file_name,
            )
            results.append(result)

        logger.info("Evaluation finished: %d tasks evaluated", len(results))
        summaries: dict[SubmissionMode, EvaluationSummaryPayload] = {}
        if submission_mode in {SubmissionMode.FULL, SubmissionMode.BOTH}:
            full_eval = TasksEvalResults.create(
                task_results=results,
                data_checksum=results[0].webarena_verified_data_checksum if results else "",
                expected_tasks=self._tasks_for_expected_ids(self._all_task_ids),
            )
            full_scores = full_eval.scores
            if full_scores is None:
                raise ValueError("Missing full leaderboard scores in evaluation results")
            summaries[SubmissionMode.FULL] = EvaluationSummaryPayload(
                timestamp=full_eval.timestamp,
                webarena_verified_version=full_eval.webarena_verified_version,
                webarena_verified_evaluator_checksum=full_eval.webarena_verified_evaluator_checksum,
                webarena_verified_data_checksum=full_eval.webarena_verified_data_checksum,
                summary=full_eval.summary,
                scores=full_scores,
            )

        if submission_mode in {SubmissionMode.HARD, SubmissionMode.BOTH}:
            hard_results = [result for result in results if result.task_id in self._hard_task_ids]
            if not hard_results:
                raise ValueError("No hard-subset tasks found in submission package for hard leaderboard evaluation")
            hard_expected_ids = self._all_task_ids & self._hard_task_ids
            hard_eval = TasksEvalResults.create(
                task_results=hard_results,
                data_checksum=hard_results[0].webarena_verified_data_checksum if hard_results else "",
                expected_tasks=self._tasks_for_expected_ids(hard_expected_ids),
            )
            hard_scores = hard_eval.scores
            if hard_scores is None:
                raise ValueError("Missing hard leaderboard scores in evaluation results")
            summaries[SubmissionMode.HARD] = EvaluationSummaryPayload(
                timestamp=hard_eval.timestamp,
                webarena_verified_version=hard_eval.webarena_verified_version,
                webarena_verified_evaluator_checksum=hard_eval.webarena_verified_evaluator_checksum,
                webarena_verified_data_checksum=hard_eval.webarena_verified_data_checksum,
                summary=hard_eval.summary,
                scores=hard_scores,
            )

        return summaries

    def _tasks_for_expected_ids(self, expected_task_ids: set[int]) -> list[WebArenaVerifiedTask]:
        return [task for task in self._all_tasks if task.task_id in expected_task_ids]
