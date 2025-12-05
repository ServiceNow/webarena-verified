import datetime
from enum import StrEnum
from importlib.metadata import version
from types import MappingProxyType
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_serializer

from ..core.utils.checksum import compute_evaluator_checksum
from .common import SerializableMappingProxyType
from .config import WebArenaVerifiedConfig
from .task import WebArenaSite, WebArenaVerifiedTask
from .tracing import NetworkTrace

WEBARENA_VERIFIED_VERSION = version("webarena-verified")  # Read from pyproject metadata


class SiteEvalResultsSummary(BaseModel):
    total: int = 0
    success_count: int = 0
    failure_count: int = 0
    error_count: int = 0
    failed_or_error_count: int = 0
    success_task_ids: list[int] = []
    failed_task_ids: list[int] = []
    error_task_ids: list[int] = []


class OverallEvalSummary(BaseModel):
    total: int = 0
    success_count: int = 0
    failure_count: int = 0
    error_count: int = 0
    failed_or_error_count: int = 0


class EvalResultsSummary(BaseModel):
    overall: OverallEvalSummary
    per_site: dict[str, SiteEvalResultsSummary]


class EvalStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL_MATCH = "partial_match"
    FAILURE = "failure"
    ERROR = "error"


class EvalAssertion(BaseModel):
    assertion_name: str
    status: EvalStatus
    assertion_msgs: tuple[str, ...] | None = None
    error_msg: str | None = None

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    @property
    def is_success(self) -> bool:
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
        if status == EvalStatus.ERROR:
            assert error_msg is not None, "Error message must be provided for ERROR status"

        return cls(
            assertion_name=assertion_name,
            status=status,
            assertion_msgs=tuple(assertion_msgs) if assertion_msgs else None,
            error_msg=error_msg,
        )


class EvaluatorResult(BaseModel):
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
        from webarena_verified.core.evaluation.data_types import NormalizedType

        def convert_to_serializable(obj: Any) -> Any:
            if isinstance(obj, (MappingProxyType, dict)):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_to_serializable(item) for item in obj]
            elif isinstance(obj, NormalizedType):
                # Extract normalized value from NormalizedType instances
                return obj.normalized
            else:
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
    def create(
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
    def create(
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
        if is_error:
            # Case where the task eval encountered an error
            assert error_msg is not None, "Error message must be provided for ERROR status"
            status = EvalStatus.ERROR
            score = 0.0
            evaluators_results = evaluators_results or []
        else:
            assert evaluators_results is not None and len(evaluators_results) > 0, (
                "At least one evaluator result is required to create task eval result."
            )
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


class TasksEvalResults(BaseModel):
    timestamp: str
    webarena_verified_version: str = WEBARENA_VERIFIED_VERSION
    webarena_verified_evaluator_checksum: str = compute_evaluator_checksum()
    webarena_verified_data_checksum: str
    summary: EvalResultsSummary
    task_results: tuple[TaskEvalResult, ...]

    model_config = ConfigDict(frozen=True)

    @classmethod
    def create(cls, *, task_results: list[TaskEvalResult] | tuple[TaskEvalResult], data_checksum: str) -> Self:
        timestamp = datetime.datetime.now(datetime.UTC).isoformat()
        summary = cls._compute_summary(task_results)

        return cls(
            timestamp=timestamp,
            summary=summary,
            task_results=tuple(task_results),
            webarena_verified_data_checksum=data_checksum,
        )

    @staticmethod
    def _compute_summary(
        task_results: list[TaskEvalResult] | tuple[TaskEvalResult, ...],
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

        return EvalResultsSummary(overall=overall, per_site=per_site)


class TransformedAgentResponse(BaseModel):
    """Used when an agent response is transformed before evaluation."""

    original_response: Any
    transformed_response: SerializableMappingProxyType | None = None

    @classmethod
    def create(cls, *, original_response: Any, transformed_response: dict[str, Any] | MappingProxyType) -> Self:
        assert isinstance(transformed_response, (dict, MappingProxyType))
        return cls(
            original_response=original_response,
            transformed_response=transformed_response,  # type: ignore
        )


class TaskEvalContext(BaseModel):
    task: WebArenaVerifiedTask
    agent_response_raw: Any | TransformedAgentResponse | None = None
    network_trace: NetworkTrace
    config: WebArenaVerifiedConfig

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)
