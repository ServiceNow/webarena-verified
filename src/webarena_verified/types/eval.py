import datetime
from enum import StrEnum
from importlib.metadata import version
from types import MappingProxyType
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from ..core.utils.checksum import compute_evaluator_checksum
from .common import SerializableMappingProxyType
from .config import WebArenaVerifiedConfig
from .task import WebArenaSite, WebArenaVerifiedTask
from .tracing import NetworkTrace

WEBARENA_VERIFIED_VERSION = version("webarena-verified")  # Read from pyproject metadata


class SiteEvalResultsSummary(BaseModel):
    """Evaluation summary for a single site."""

    total: int = 0
    success_count: int = 0
    failure_count: int = 0
    error_count: int = 0
    failed_or_error_count: int = 0
    expected_total: int = 0
    missing_count: int = 0
    success_task_ids: list[int] = []
    failed_task_ids: list[int] = []
    error_task_ids: list[int] = []


class OverallEvalSummary(BaseModel):
    """Overall evaluation summary across all sites."""

    total: int = 0
    success_count: int = 0
    failure_count: int = 0
    error_count: int = 0
    failed_or_error_count: int = 0
    expected_total: int = 0
    missing_count: int = 0


class EvalResultsSummary(BaseModel):
    """Combined evaluation summary with overall and per-site breakdowns."""

    overall: OverallEvalSummary
    per_site: dict[str, SiteEvalResultsSummary]


class EvalStatus(StrEnum):
    """Evaluation result status."""

    SUCCESS = "success"
    PARTIAL_MATCH = "partial_match"
    FAILURE = "failure"
    ERROR = "error"


class EvalAssertion(BaseModel):
    """Single assertion result within an evaluation."""

    assertion_name: str
    status: EvalStatus
    assertion_msgs: tuple[str, ...] | None = None
    error_msg: str | None = None

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    @property
    def is_success(self) -> bool:
        """Check if assertion passed."""
        return self.status == EvalStatus.SUCCESS

    @classmethod
    def create(
        cls,
        *,
        assertion_name: str,
        assertion_msgs: list[str] | None = None,
        status: EvalStatus,
        error_msg: str | None = None,
    ) -> Self:
        """Create an EvalAssertion instance."""
        if status == EvalStatus.ERROR:
            assert error_msg is not None, "Error message must be provided for ERROR status"

        return cls(
            assertion_name=assertion_name,
            status=status,
            assertion_msgs=tuple(assertion_msgs) if assertion_msgs else None,
            error_msg=error_msg,
        )


class EvaluatorResult(BaseModel):
    """Result from a single evaluator."""

    evaluator_name: str
    status: EvalStatus
    score: float
    actual: Any | None = None
    actual_normalized: Any | None = None
    expected: Any | None = None
    assertions: tuple[EvalAssertion, ...] | None = None
    error_msg: str | None = None
    should_not_exist: bool | None = None

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    @model_serializer
    def _serialize_model(self) -> dict[str, Any]:
        """Custom serializer to handle MappingProxyType and NormalizedType instances.

        Converts both MappingProxyType (to dict) and NormalizedType instances (to their
        normalized values) for JSON serialization. These types can appear nested in dicts
        or lists where Pydantic's type-based serialization doesn't automatically apply.
        """
        from webarena_verified.core.evaluation.data_types import NormalizedType  # noqa: PLC0415 (circular import)

        def convert_to_serializable(obj: Any) -> Any:
            if isinstance(obj, (MappingProxyType, dict)):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [convert_to_serializable(item) for item in obj]
            if isinstance(obj, NormalizedType):
                # Extract normalized value from NormalizedType instances
                return obj.normalized
            return obj

        return {
            "evaluator_name": self.evaluator_name,
            "status": self.status,
            "score": self.score,
            "actual": convert_to_serializable(self.actual),
            "actual_normalized": convert_to_serializable(self.actual_normalized),
            "expected": convert_to_serializable(self.expected),
            "assertions": self.assertions,
            "error_msg": self.error_msg,
            "should_not_exist": self.should_not_exist,
        }

    @classmethod
    def create(  # noqa: PLR0913
        cls,
        *,
        evaluator_name: str,
        assertions: list[EvalAssertion] | None = None,
        error_msg: str | None = None,
        is_error: bool = False,
        actual: Any | None = None,
        actual_normalized: Any | None = None,
        expected: Any | None = None,
        should_not_exist: bool | None = None,
    ) -> Self:
        """Create an EvaluatorResult with computed status and score."""
        if is_error:
            # Case where the evaluator itself encountered an error
            assert error_msg is not None, "Error message must be provided for ERROR status"
            status = EvalStatus.ERROR
            score = 0.0
        else:
            # Empty assertion list means all validations passed (no differences found)
            if assertions is None or len(assertions) == 0:
                status = EvalStatus.SUCCESS
                score = 1.0
            elif any(a.status == EvalStatus.ERROR for a in assertions):
                # Case where one or more assertions resulted in an error
                status = EvalStatus.ERROR
                score = 0.0
            else:
                # All assertions are either SUCCESS or FAILURE
                score = 1.0 if all(a.is_success for a in assertions) else 0.0
                status = EvalStatus.SUCCESS if score == 1.0 else EvalStatus.FAILURE

        return cls(
            evaluator_name=evaluator_name,
            status=status,
            score=score,
            actual=actual,
            actual_normalized=actual_normalized,
            expected=expected,
            assertions=tuple(assertions) if assertions else None,
            error_msg=error_msg,
            should_not_exist=should_not_exist,
        )


class TaskEvalResult(BaseModel):
    """Evaluation result for a single task."""

    task_id: int
    intent_template_id: int
    sites: tuple[WebArenaSite, ...]
    task_revision: int
    status: EvalStatus
    score: float
    evaluators_results: tuple[EvaluatorResult, ...]
    error_msg: str | None = None
    webarena_verified_version: str = WEBARENA_VERIFIED_VERSION
    webarena_verified_evaluator_checksum: str = compute_evaluator_checksum()
    webarena_verified_data_checksum: str

    @classmethod
    def create(  # noqa: PLR0913
        cls,
        *,
        task_id: int,
        intent_template_id: int,
        sites: tuple[WebArenaSite, ...],
        task_revision: int,
        data_checksum: str,
        evaluators_results: list[EvaluatorResult] | None = None,
        error_msg: str | None = None,
        is_error: bool = False,
    ) -> Self:
        """Create a TaskEvalResult with computed status and score."""
        if is_error:
            # Case where the task eval encountered an error
            assert error_msg is not None, "Error message must be provided for ERROR status"
            status = EvalStatus.ERROR
            score = 0.0
            evaluators_results = evaluators_results or []
        else:
            assert evaluators_results is not None, "Evaluator results cannot be None."
            assert len(evaluators_results) > 0, "At least one evaluator result is required."
            if any(er.status == EvalStatus.ERROR for er in evaluators_results):
                # Case where one or more evaluators resulted in an error
                status = EvalStatus.ERROR
                score = 0.0
            else:
                score = 1.0 if all(er.score == 1.0 for er in evaluators_results) else 0.0
                status = EvalStatus.SUCCESS if score == 1.0 else EvalStatus.FAILURE

        return cls(
            task_id=task_id,
            intent_template_id=intent_template_id,
            sites=sites,
            task_revision=task_revision,
            status=status,
            score=score,
            evaluators_results=tuple(evaluators_results),
            error_msg=error_msg,
            webarena_verified_data_checksum=data_checksum,
        )


class EvaluationScores(BaseModel):
    """Per-site success-rate scores (0.0-1.0) for a batch evaluation."""

    overall: float = Field(default=0.0, ge=0.0, le=1.0)
    shopping: float = Field(default=0.0, ge=0.0, le=1.0)
    shopping_admin: float = Field(default=0.0, ge=0.0, le=1.0)
    gitlab: float = Field(default=0.0, ge=0.0, le=1.0)
    map: float = Field(default=0.0, ge=0.0, le=1.0)
    reddit: float = Field(default=0.0, ge=0.0, le=1.0)
    multisite: float = Field(default=0.0, ge=0.0, le=1.0)
    gitlab_reddit: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class TasksEvalResults(BaseModel):
    """Collection of evaluation results for multiple tasks."""

    timestamp: str
    webarena_verified_version: str = WEBARENA_VERIFIED_VERSION
    webarena_verified_evaluator_checksum: str = compute_evaluator_checksum()
    webarena_verified_data_checksum: str
    summary: EvalResultsSummary
    scores: EvaluationScores | None = None
    task_results: tuple[TaskEvalResult, ...]

    model_config = ConfigDict(frozen=True)

    @classmethod
    def create(
        cls,
        *,
        task_results: list[TaskEvalResult] | tuple[TaskEvalResult, ...],
        data_checksum: str,
        expected_tasks: list[WebArenaVerifiedTask] | tuple[WebArenaVerifiedTask, ...] | None = None,
    ) -> Self:
        """Create TasksEvalResults with computed summary."""
        timestamp = datetime.datetime.now(tz=datetime.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        summary = cls._compute_summary(task_results, expected_tasks=expected_tasks)
        scores = (
            cls._compute_scores(task_results, expected_tasks=expected_tasks) if expected_tasks is not None else None
        )

        return cls(
            timestamp=timestamp,
            summary=summary,
            scores=scores,
            task_results=tuple(task_results),
            webarena_verified_data_checksum=data_checksum,
        )

    @staticmethod
    def _compute_scores(
        task_results: list[TaskEvalResult] | tuple[TaskEvalResult, ...],
        expected_tasks: list[WebArenaVerifiedTask] | tuple[WebArenaVerifiedTask, ...],
    ) -> EvaluationScores:
        bucket_keys = (
            "shopping",
            "shopping_admin",
            "gitlab",
            "map",
            "reddit",
            "multisite",
            "gitlab_reddit",
        )

        def tally_site_buckets(
            items: list[TaskEvalResult]
            | tuple[TaskEvalResult, ...]
            | list[WebArenaVerifiedTask]
            | tuple[WebArenaVerifiedTask, ...],
        ) -> dict[str, int]:
            buckets = dict.fromkeys(bucket_keys, 0)

            for item in items:
                site_values = {site.value for site in item.sites}

                for site_name in ("shopping", "shopping_admin", "gitlab", "map", "reddit"):
                    if site_name in site_values:
                        buckets[site_name] += 1

                if len(site_values) > 1:
                    buckets["multisite"] += 1

                if site_values == {"gitlab", "reddit"}:
                    buckets["gitlab_reddit"] += 1

            return buckets

        successful_results = [result for result in task_results if result.status == EvalStatus.SUCCESS]
        denominator_buckets = tally_site_buckets(expected_tasks)
        numerator_buckets = tally_site_buckets(successful_results)

        def compute_ratio(numerator: int, denominator: int) -> float:
            return numerator / denominator if denominator > 0 else 0.0

        return EvaluationScores(
            overall=compute_ratio(len(successful_results), len(expected_tasks)),
            shopping=compute_ratio(numerator_buckets["shopping"], denominator_buckets["shopping"]),
            shopping_admin=compute_ratio(numerator_buckets["shopping_admin"], denominator_buckets["shopping_admin"]),
            gitlab=compute_ratio(numerator_buckets["gitlab"], denominator_buckets["gitlab"]),
            map=compute_ratio(numerator_buckets["map"], denominator_buckets["map"]),
            reddit=compute_ratio(numerator_buckets["reddit"], denominator_buckets["reddit"]),
            multisite=compute_ratio(numerator_buckets["multisite"], denominator_buckets["multisite"]),
            gitlab_reddit=compute_ratio(numerator_buckets["gitlab_reddit"], denominator_buckets["gitlab_reddit"]),
        )

    @staticmethod
    def _compute_summary(
        task_results: list[TaskEvalResult] | tuple[TaskEvalResult, ...],
        expected_tasks: list[WebArenaVerifiedTask] | tuple[WebArenaVerifiedTask, ...] | None = None,
    ) -> EvalResultsSummary:
        """Compute overall and per-site summary statistics from task results."""
        per_site: dict[str, SiteEvalResultsSummary] = {}
        overall = OverallEvalSummary()

        for result in task_results:
            site_key = "-".join(sorted(result.sites))

            if site_key not in per_site:
                per_site[site_key] = SiteEvalResultsSummary()

            per_site[site_key].total += 1
            overall.total += 1

            if result.status == EvalStatus.SUCCESS:
                per_site[site_key].success_count += 1
                per_site[site_key].success_task_ids.append(result.task_id)
                overall.success_count += 1
            elif result.status == EvalStatus.FAILURE:
                per_site[site_key].failure_count += 1
                per_site[site_key].failed_task_ids.append(result.task_id)
                overall.failure_count += 1
            elif result.status == EvalStatus.ERROR:
                per_site[site_key].error_count += 1
                per_site[site_key].error_task_ids.append(result.task_id)
                overall.error_count += 1

            if result.status != EvalStatus.SUCCESS:
                per_site[site_key].failed_or_error_count += 1
                overall.failed_or_error_count += 1

        if expected_tasks is not None:
            expected_by_site: dict[str, int] = {}
            for expected_task in expected_tasks:
                expected_site_key = "-".join(sorted(site.value for site in expected_task.sites))
                expected_by_site[expected_site_key] = expected_by_site.get(expected_site_key, 0) + 1

                if expected_site_key not in per_site:
                    per_site[expected_site_key] = SiteEvalResultsSummary()

            overall.expected_total = len(expected_tasks)
            overall.missing_count = max(overall.expected_total - overall.total, 0)

            for site_key, expected_total in expected_by_site.items():
                per_site[site_key].expected_total = expected_total
                per_site[site_key].missing_count = max(expected_total - per_site[site_key].total, 0)

        return EvalResultsSummary(overall=overall, per_site=per_site)


class TransformedAgentResponse(BaseModel):
    """Used when an agent response is transformed before evaluation."""

    original_response: Any
    transformed_response: SerializableMappingProxyType | None = None

    @classmethod
    def create(cls, *, original_response: Any, transformed_response: dict[str, Any] | MappingProxyType) -> Self:
        """Create a TransformedAgentResponse instance."""
        assert isinstance(transformed_response, (dict, MappingProxyType))
        return cls(
            original_response=original_response,
            transformed_response=transformed_response,  # type: ignore
        )


class TaskEvalContext(BaseModel):
    """Context passed to evaluators during task evaluation."""

    task: WebArenaVerifiedTask
    agent_response_raw: Any | TransformedAgentResponse | None = None
    network_trace: NetworkTrace
    config: WebArenaVerifiedConfig

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)
