from __future__ import annotations

import datetime as dt
from pathlib import Path

from webarena_verified.api import WebArenaVerified
from webarena_verified.types.data import TaskSubset
from webarena_verified.types.eval import (
    WEBARENA_VERIFIED_VERSION,
    EvalStatus,
    TaskEvalResult,
    compute_evaluator_checksum,
)
from webarena_verified.types.task import WebArenaVerifiedTask
from webarena_verified.utils import get_package_assets_path

from .config import SubmissionFlowConfig
from .models import (
    EvaluationScores,
    EvaluationSummaryCounts,
    EvaluationSummaryPayload,
    OverallCounts,
    SiteCounts,
    SubmissionMetadata,
    SubmissionMode,
)


class SubmissionEvaluator:
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
        task_dirs = sorted(path for path in submission_dir.iterdir() if path.is_dir() and path.name.isdigit())
        results: list[TaskEvalResult] = []
        for task_dir in task_dirs:
            task_id = int(task_dir.name)
            result = self._wa.evaluate_task(
                task_id=task_id,
                agent_response=task_dir / self._flow_config.task_agent_response_file_name,
                network_trace=task_dir / self._flow_config.task_network_file_name,
            )
            results.append(result)

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

        for site_key, site_counts in per_site.items():
            site_counts.missing_count = max(site_counts.expected_total - site_counts.total, 0)

        return EvaluationSummaryCounts(overall=overall, per_site=per_site)

    def _build_scores(
        self, *, results: list[TaskEvalResult], expected_tasks: list[WebArenaVerifiedTask]
    ) -> EvaluationScores:
        expected_total = len(expected_tasks)
        success_total = sum(1 for result in results if result.status == EvalStatus.SUCCESS)

        expected_bucket_total = {
            "shopping": 0,
            "shopping_admin": 0,
            "gitlab": 0,
            "map": 0,
            "reddit": 0,
            "multisite": 0,
            "gitlab_reddit": 0,
        }
        bucket_success = dict.fromkeys(expected_bucket_total, 0)

        for task in expected_tasks:
            site_values = {site.value for site in task.sites}
            if len(site_values) > 1:
                expected_bucket_total["multisite"] += 1
            if site_values == {"gitlab", "reddit"}:
                expected_bucket_total["gitlab_reddit"] += 1
            for site_name in ("shopping", "shopping_admin", "gitlab", "map", "reddit"):
                if site_name in site_values:
                    expected_bucket_total[site_name] += 1

        for result in results:
            site_values = {site.value for site in result.sites}
            if result.status == EvalStatus.SUCCESS:
                if len(site_values) > 1:
                    bucket_success["multisite"] += 1
                if site_values == {"gitlab", "reddit"}:
                    bucket_success["gitlab_reddit"] += 1

            for site_name in ("shopping", "shopping_admin", "gitlab", "map", "reddit"):
                if site_name in site_values and result.status == EvalStatus.SUCCESS:
                    bucket_success[site_name] += 1

        def ratio(success_count: int, total_count: int) -> float:
            return 0.0 if total_count == 0 else success_count / total_count

        return EvaluationScores(
            overall=ratio(success_total, expected_total),
            shopping=ratio(bucket_success["shopping"], expected_bucket_total["shopping"]),
            shopping_admin=ratio(bucket_success["shopping_admin"], expected_bucket_total["shopping_admin"]),
            gitlab=ratio(bucket_success["gitlab"], expected_bucket_total["gitlab"]),
            map=ratio(bucket_success["map"], expected_bucket_total["map"]),
            reddit=ratio(bucket_success["reddit"], expected_bucket_total["reddit"]),
            multisite=ratio(bucket_success["multisite"], expected_bucket_total["multisite"]),
            gitlab_reddit=ratio(bucket_success["gitlab_reddit"], expected_bucket_total["gitlab_reddit"]),
        )

    def _tasks_for_expected_ids(self, expected_task_ids: set[int]) -> list[WebArenaVerifiedTask]:
        return [task for task in self._all_tasks if task.task_id in expected_task_ids]

    @staticmethod
    def _now_utc_z() -> str:
        return dt.datetime.now(tz=dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
