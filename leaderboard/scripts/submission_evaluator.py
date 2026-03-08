from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path  # noqa: TC003

from webarena_verified.api import WebArenaVerified
from webarena_verified.submission.config import SubmissionFlowConfig
from webarena_verified.submission.models import SubmissionMetadata, SubmissionMode
from webarena_verified.types.data import TaskSubset
from webarena_verified.types.eval import (
    WEBARENA_VERIFIED_VERSION,
    EvalStatus,
    TaskEvalResult,
    compute_evaluator_checksum,
)
from webarena_verified.types.task import WebArenaVerifiedTask  # noqa: TC001
from webarena_verified.utils import get_package_assets_path

from .models import (
    EvaluationScores,
    EvaluationSummaryCounts,
    EvaluationSummaryPayload,
    OverallCounts,
    SiteCounts,
)

logger = logging.getLogger(__name__)


class SubmissionEvaluator:
    """Runs WebArena-Verified evaluators on a submission and produces scoring summaries.

    Sits at stage 2 of the ingest pipeline, between submission validation
    (``SubmissionValidator``) and leaderboard building (``LeaderboardBuilder``).

    On construction, loads the full task dataset and the hard-subset task IDs
    so it can partition results into full and hard evaluation summaries.  For
    each task directory in the submission, it delegates to ``WebArenaVerified.
    evaluate_task`` and then aggregates the per-task ``TaskEvalResult`` objects
    into ``EvaluationSummaryPayload`` instances — one per requested mode
    (full, hard, or both).
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
        """Evaluate all tasks in a submission and return per-mode summaries.

        Iterates over numbered task directories inside ``submission_dir``,
        runs the WebArena-Verified evaluator on each, then builds
        ``EvaluationSummaryPayload`` objects for the requested modes.

        Called by ``submission_handler.ingest_hf_submission`` immediately
        after validation succeeds.

        Args:
            submission_dir: Root of the unpacked submission (contains ``0/``,
                ``1/``, … task directories).
            submission: Validated submission metadata.
            submission_mode: Which leaderboard(s) to score for (full, hard,
                or both).

        Returns:
            Mapping from ``SubmissionMode`` to the corresponding evaluation
            summary.

        Raises:
            ValueError: If ``submission_mode`` includes hard but the
                submission contains no hard-subset tasks.
        """
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
            summaries[SubmissionMode.FULL] = self._build_summary(
                results=results,
                expected_tasks=self._tasks_for_expected_ids(self._all_task_ids),
            )

        if submission_mode in {SubmissionMode.HARD, SubmissionMode.BOTH}:
            hard_results = [result for result in results if result.task_id in self._hard_task_ids]
            if not hard_results:
                raise ValueError("No hard-subset tasks found in submission package for hard leaderboard evaluation")
            hard_expected_ids = self._all_task_ids & self._hard_task_ids
            summaries[SubmissionMode.HARD] = self._build_summary(
                results=hard_results,
                expected_tasks=self._tasks_for_expected_ids(hard_expected_ids),
            )

        return summaries

    def _build_summary(
        self, *, results: list[TaskEvalResult], expected_tasks: list[WebArenaVerifiedTask]
    ) -> EvaluationSummaryPayload:
        counts = self._build_counts(results=results, expected_tasks=expected_tasks)
        scores = self._build_scores(results=results, expected_tasks=expected_tasks)
        return EvaluationSummaryPayload(
            timestamp=self._now_utc_z(),
            webarena_verified_version=WEBARENA_VERIFIED_VERSION,
            webarena_verified_evaluator_checksum=compute_evaluator_checksum(),
            webarena_verified_data_checksum=(results[0].webarena_verified_data_checksum if results else ""),
            summary=counts,
            scores=scores,
        )

    def _build_counts(
        self, *, results: list[TaskEvalResult], expected_tasks: list[WebArenaVerifiedTask]
    ) -> EvaluationSummaryCounts:
        expected_by_site: dict[str, int] = {}
        for task in expected_tasks:
            site_key = "-".join(sorted(site.value for site in task.sites))
            expected_by_site[site_key] = expected_by_site.get(site_key, 0) + 1

        per_site: dict[str, SiteCounts] = {
            key: SiteCounts(
                total=0,
                success_count=0,
                failure_count=0,
                error_count=0,
                failed_or_error_count=0,
                expected_total=expected_total,
                missing_count=expected_total,
            )
            for key, expected_total in expected_by_site.items()
        }
        overall = OverallCounts(
            total=len(results),
            success_count=0,
            failure_count=0,
            error_count=0,
            failed_or_error_count=0,
            expected_total=len(expected_tasks),
            missing_count=max(len(expected_tasks) - len(results), 0),
        )

        for result in results:
            site_key = "-".join(sorted(site.value for site in result.sites))
            if site_key not in per_site:
                per_site[site_key] = SiteCounts(
                    total=0,
                    success_count=0,
                    failure_count=0,
                    error_count=0,
                    failed_or_error_count=0,
                    expected_total=0,
                    missing_count=0,
                )

            per_site[site_key].total += 1
            if result.status == EvalStatus.SUCCESS:
                overall.success_count += 1
                per_site[site_key].success_count += 1
            elif result.status == EvalStatus.ERROR:
                overall.error_count += 1
                overall.failed_or_error_count += 1
                per_site[site_key].error_count += 1
                per_site[site_key].failed_or_error_count += 1
            else:
                overall.failure_count += 1
                overall.failed_or_error_count += 1
                per_site[site_key].failure_count += 1
                per_site[site_key].failed_or_error_count += 1

        for _site_key, site_counts in per_site.items():
            site_counts.missing_count = max(site_counts.expected_total - site_counts.total, 0)

        return EvaluationSummaryCounts(overall=overall, per_site=per_site)

    @staticmethod
    def _tally_site_buckets(
        items: list[TaskEvalResult] | list[WebArenaVerifiedTask],
        *,
        success_only: bool,
    ) -> dict[str, int]:
        single_sites = ("shopping", "shopping_admin", "gitlab", "map", "reddit")
        all_keys: tuple[str, ...] = (*single_sites, "multisite", "gitlab_reddit")
        buckets: dict[str, int] = {k: 0 for k in all_keys}  # noqa: C420
        for item in items:
            if success_only and getattr(item, "status", None) != EvalStatus.SUCCESS:
                continue
            site_values = {site.value for site in item.sites}
            if len(site_values) > 1:
                buckets["multisite"] += 1
            if site_values == {"gitlab", "reddit"}:
                buckets["gitlab_reddit"] += 1
            for site_name in single_sites:
                if site_name in site_values:
                    buckets[site_name] += 1
        return buckets

    def _build_scores(
        self, *, results: list[TaskEvalResult], expected_tasks: list[WebArenaVerifiedTask]
    ) -> EvaluationScores:
        expected_total = len(expected_tasks)
        success_total = sum(1 for result in results if result.status == EvalStatus.SUCCESS)

        expected_bucket_total = self._tally_site_buckets(expected_tasks, success_only=False)
        bucket_success = self._tally_site_buckets(results, success_only=True)

        def ratio(success_count: int, total_count: int) -> float:
            return 0.0 if total_count == 0 else success_count / total_count

        return EvaluationScores(
            overall=ratio(success_total, expected_total),
            **{key: ratio(bucket_success[key], expected_bucket_total[key]) for key in bucket_success},
        )

    def _tasks_for_expected_ids(self, expected_task_ids: set[int]) -> list[WebArenaVerifiedTask]:
        return [task for task in self._all_tasks if task.task_id in expected_task_ids]

    @staticmethod
    def _now_utc_z() -> str:
        return dt.datetime.now(tz=dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
