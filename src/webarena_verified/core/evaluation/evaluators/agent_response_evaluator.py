import json
import logging
import re
from contextlib import suppress
from functools import partial
from types import MappingProxyType
from typing import Any

from webarena_verified.core.evaluation.data_types import NormalizedString
from webarena_verified.types.agent_response import _FinalAgentResponse
from webarena_verified.types.eval import (
    EvalAssertion,
    EvalStatus,
    TaskEvalContext,
    TransformedAgentResponse,
)
from webarena_verified.types.task import AgentResponseEvaluatorCfg

from .base import BaseEvaluator

logger = logging.getLogger(__name__)


class AgentResponseEvaluator(BaseEvaluator[AgentResponseEvaluatorCfg]):
    """Evaluator for agent responses using four-step architecture.

    Validates the agent's response structure, task type, status,
    and retrieved data against expected values with alternatives support.

    Architecture:
    - Step 1: Extract agent response from context (parse JSON, validate format)
    - Step 2: Get expected response from config (with alternatives)
    - Step 3: Normalize both using schema-based normalization
    - Step 4: Compare normalized values structurally
    """

    def _get_actual_value(self, context: TaskEvalContext, config: AgentResponseEvaluatorCfg) -> Any:
        return context.agent_response_raw

    def _get_expected_value(self, config: AgentResponseEvaluatorCfg) -> Any:
        """Get expected value from config.

        Returns:
            Expected agent response as dict with alternatives support
        """
        return config.expected

    def _normalized_expected_value(
        self, expected_raw: _FinalAgentResponse, config: AgentResponseEvaluatorCfg, context: TaskEvalContext
    ):
        if not isinstance(expected_raw, _FinalAgentResponse):
            raise TypeError(f"Expected value must be of type _FinalAgentResponse, got {type(expected_raw).__name__}")
        normalized_retrieved_data = self._normalized_retrieved_data(
            retrieved_data_raw=expected_raw.retrieved_data,
            strict=True,
            context=context,
            config=config,
        )
        return MappingProxyType(
            {
                "task_type": NormalizedString(expected_raw.task_type),
                "status": NormalizedString(expected_raw.status),
                "retrieved_data": normalized_retrieved_data,
            }
        )

    def _get_actual_agent_response_dict(self, actual_raw: Any) -> Any:
        value = actual_raw
        if isinstance(value, str):
            value = value.strip()

        if isinstance(actual_raw, TransformedAgentResponse):
            value = actual_raw.transformed_response
        elif isinstance(actual_raw, str):
            # Extract JSON from code blocks (```json ... ``` or ``` ... ```)
            code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
            match = re.search(code_block_pattern, actual_raw, re.DOTALL)
            if match:
                value = match.group(1).strip()

            with suppress(json.JSONDecodeError):
                value = json.loads(value)

        return value or None

    def _normalized_actual_value(
        self, actual_raw: Any, normalized_expected: Any, config: AgentResponseEvaluatorCfg, context: TaskEvalContext
    ):
        value = self._get_actual_agent_response_dict(actual_raw=actual_raw)
        if not isinstance(value, (dict, MappingProxyType)):
            return value

        _normalized_values = {}
        for k in config.expected.model_fields_set:
            if k == "task_type" and k not in value and "performed_operation" in value:
                k = "performed_operation"  # Support legacy field name

            if k not in value:
                continue

            if k == "retrieved_data":
                _attr_value = value.get(k, "")
                _normalized_value = (
                    self._normalized_retrieved_data(
                        retrieved_data_raw=_attr_value,
                        strict=False,
                        context=context,
                        config=config,
                    )
                    if context.task.is_retrieve_task
                    else None
                )
            else:
                _normalized_value = None
                # All other fields are normalized as NormalizedString
                if _attr_value := value.get(k, "").strip():
                    _normalized_value = _attr_value
                    with suppress(ValueError):
                        _normalized_value = NormalizedString(_attr_value)

                if k == "performed_operation":
                    k = "task_type"  # Store under new field name

            if k in _normalized_values:
                raise ValueError(f"Duplicate key '{k}' found during normalization.")

            _normalized_values[k] = _normalized_value or None

        return MappingProxyType(_normalized_values)

    def _normalized_retrieved_data(
        self, *, retrieved_data_raw: Any, strict: bool, context: TaskEvalContext, config: AgentResponseEvaluatorCfg
    ) -> Any:
        if not retrieved_data_raw and not isinstance(retrieved_data_raw, (int, float, bool)):
            # None and empty cases
            return None

        retrieved_data_raw = (
            (retrieved_data_raw,) if not isinstance(retrieved_data_raw, (list, tuple)) else tuple(retrieved_data_raw)
        )
        _derender_url_fct = partial(context.config.derender_url, sites=context.task.sites, strict=strict)
        # TODO: Maybe call normalize array directly here
        _normalized_value = self.value_normalizer.normalize_array(
            retrieved_data_raw,
            config.results_schema,
            strict=strict,
            derender_url_fct=_derender_url_fct,
        )
        return _normalized_value

    def _compare_values(
        self,
        *,
        actual_normalized: Any,
        expected_normalized: MappingProxyType,
        config: AgentResponseEvaluatorCfg,
        context: TaskEvalContext,
        **kwargs,
    ) -> list[EvalAssertion]:
        """Compare normalized actual vs expected using ValueComparator."""
        # Compare all keys except the value of retrieved_data
        assertions = []

        assertions.extend(
            self.value_comparator.compare(
                expected=expected_normalized,
                actual=actual_normalized,
                ignored_values_keys={"retrieved_data"},
                value_name="agent_response",
            )
        )

        if not isinstance(actual_normalized, (dict, MappingProxyType)):
            return assertions

        # Compare retrieved_data
        actual_retrieved_data = actual_normalized.get("retrieved_data", None)
        if not context.task.is_retrieve_task or not actual_normalized:
            # Ignore retrieved_data comparison for non-retrieve tasks or invalid actual response
            return assertions

        expected_retrieved_data = expected_normalized.get("retrieved_data", None)
        if expected_retrieved_data is None:
            raise ValueError("Expected retrieved_data must be set in config for retrieve tasks.")

        # Handle None actual_retrieved_data - should fail if expected is not None
        if actual_retrieved_data is None and expected_retrieved_data is not None:
            assertions.append(
                EvalAssertion.create(
                    assertion_name="retrieved_data_missing_or_null",
                    status=EvalStatus.FAILURE,
                    assertion_msgs=[f"Expected retrieved_data to be {expected_retrieved_data}, but got None or empty"],
                )
            )
            return assertions

        assertions.extend(
            self.value_comparator.compare(
                expected=tuple(expected_retrieved_data),
                actual=tuple(actual_retrieved_data),
                value_name="retrieved_data",
                ordered=config.ordered,
            )
        )

        return assertions
