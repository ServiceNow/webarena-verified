from abc import ABC, abstractmethod
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from webarena_verified.core.evaluation.data_types import NormalizedType
from webarena_verified.core.evaluation.value_comparator import ValueComparator
from webarena_verified.core.evaluation.value_normalizer import ValueNormalizer
from webarena_verified.core.utils import logger
from webarena_verified.types.eval import EvalAssertion, EvaluatorResult, TaskEvalContext
from webarena_verified.types.task import BaseEval

EvalConfigT = TypeVar("EvalConfigT", bound=BaseEval[Any])


class BaseEvaluator(ABC, Generic[EvalConfigT]):
    def __init__(self) -> None:
        self.value_comparator = ValueComparator()
        self.value_normalizer = ValueNormalizer()

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def evaluate(self, *, context: TaskEvalContext, config: EvalConfigT) -> EvaluatorResult:
        """Main evaluation flow using four-step process.

        Steps:
        1. Get actual value (evaluator-specific extraction)
        2. Get expected value (from config)
        3. Normalize both values (using ValueNormalizer)
        4. Compare normalized values (using ValueComparator)

        Args:
            context: Task evaluation context
            config: Evaluator configuration

        Returns:
            EvaluatorResult with assertions and normalized values
        """
        # Sanity check
        assert self.name == config.evaluator, f"Evaluator name mismatch: {self.name} != {config.evaluator}"  # type: ignore

        # TODO: Rename config to eval_cfg for clarity
        assertions = None
        error_occurred = False
        error_msg = None
        actual_raw = None
        expected_raw = None
        actual_normalized = None
        expected_normalized = None

        try:
            # Step 1: Get actual value (evaluator-specific)
            actual_raw = self._get_actual_value(context, config)

            # Step 2: Get expected value (from task expected data in config)
            expected_raw = self._get_expected_value(config)

            # Step 3: Normalize both values
            expected_normalized = self._normalized_expected_value(
                expected_raw,
                config=config,
                context=context,
            )
            actual_normalized = self._normalized_actual_value(
                actual_raw,
                expected_normalized,
                config=config,
                context=context,
            )

            # Step 4: Compare normalized values
            assertions = self._compare_values(
                actual_normalized=actual_normalized,
                expected_normalized=expected_normalized,
                config=config,
                context=context,
                ordered=False,
            )

        except Exception as e:
            error_msg = f"Error during evaluation with evaluator {self.name} for task {context.task.task_id}: {e}"
            logger.exception(error_msg)
            error_occurred = True

        return EvaluatorResult.create(
            evaluator_name=self.name,
            assertions=assertions,
            is_error=error_occurred,
            error_msg=error_msg,
            actual=actual_raw,
            actual_normalized=self._parse_normalized_value_for_reporting(actual_normalized),
            expected=self._parse_normalized_value_for_reporting(expected_normalized),
            should_not_exist=getattr(config, "should_not_exist", None),
        )

    # ========================================================================
    # Abstract Methods (Must be implemented by subclasses)
    # ========================================================================

    @abstractmethod
    def _get_actual_value(self, context: TaskEvalContext, config: EvalConfigT) -> Any:
        """Extract and navigate to the actual value from evaluation context.

        **Step 1: Get Actual Value**

        Purpose: Extract raw value from context before normalization.

        Evaluator-Specific Implementation:
        - AgentResponseEvaluator: Extract from context.agent_response
        - NetworkEventEvaluator: Extract from context.network_trace.events

        May include navigation to specific field using value_path:
        - Example: 'retrieved_data' from agent response
        - Example: 'headers.referer' from network event

        Args:
            context: Task evaluation context
            config: Evaluator configuration

        Returns:
            Raw value (before normalization) which can be:
            - Simple value (string, number, boolean)
            - Array of simple values
            - Object (dictionary)
            - Array of objects

        Note:
            This is the ONLY step that is evaluator-specific. All other steps
            (get expected, normalize, compare) use the same logic across evaluators.
        """
        pass

    @abstractmethod
    def _normalized_expected_value(self, expected_raw: Any, config: EvalConfigT, context: TaskEvalContext):
        """Normalize expected value.

        **Step 3a: Normalize Expected Value**

        Purpose: Convert expected value to normalized form for comparison.

        Args:
            expected_raw: Raw expected value from config
            config: Evaluator configuration
            context: Task evaluation context

        Returns:
            Normalized value (NormalizedType, list, or dict)
        """
        ...

    @abstractmethod
    def _normalized_actual_value(
        self, actual_raw: Any, normalized_expected: Any, config: EvalConfigT, context: TaskEvalContext
    ):
        """Normalize actual value.

        **Step 3b: Normalize Actual Value**

        Purpose: Convert actual value to normalized form for comparison.

        Args:
            actual_raw: Raw actual value from context
            normalized_expected: Already normalized expected value (for context)
            config: Evaluator configuration
            context: Task evaluation context

        Returns:
            Normalized value (NormalizedType, list, or dict)
        """
        ...

    @abstractmethod
    def _compare_values(
        self,
        *,
        actual_normalized: NormalizedType | list[NormalizedType] | dict | MappingProxyType | None,
        expected_normalized: NormalizedType | list[NormalizedType] | dict | MappingProxyType | None,
        config: EvalConfigT,
        context: TaskEvalContext,
        ordered: bool = False,
    ) -> list[EvalAssertion]:
        """Compare normalized actual vs expected values.

        Must be implemented by subclasses to provide context-aware comparison logic.

        Args:
            actual_normalized: Normalized actual value (can be None)
            expected_normalized: Normalized expected value (can be None)
            config: Evaluator configuration (required for subclass-specific logic)
            context: Task evaluation context (required for context-aware comparison)
            ordered: Whether array order matters for comparison

        Returns:
            List of EvalAssertion objects (empty list = success)
        """
        ...

    # ========================================================================
    # Helper Methods (Can be overridden by subclasses)
    # ========================================================================

    def _get_expected_value(self, config: EvalConfigT) -> Any:
        """Get expected value from evaluator configuration.

        **Step 2: Get Expected Value**

        Purpose: Extract expected value(s) from config.expected field.

        Source: Always comes from config.expected

        Supports Alternatives at Individual Value Level:
        - Single value: "success"
        - Single value with alternatives: ["success", "ok", "completed"]
        - Array with element-level alternatives: [[10, 17], 15]
        - Object with property-level alternatives: {"status": ["success", "ok"], "code": 200}

        Key Pattern: When a value is a list, it means "any of these alternatives is valid"
        - At root level: ["success", "ok"] → single value with alternatives
        - In array: [[10, 17], 15] → first element has alternatives
        - In object: {status: ["success", "ok"]} → property has alternatives

        Args:
            config: Evaluator configuration

        Returns:
            Raw expected value(s) (before normalization)

        Note:
            This method can be overridden by subclasses if they need custom
            logic for extracting expected values from config.
        """
        return config.expected

    def _parse_normalized_value_for_reporting(self, value: Any) -> Any:
        if isinstance(value, NormalizedType):
            return value.normalized
        elif isinstance(value, (list, tuple)):
            return [self._parse_normalized_value_for_reporting(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._parse_normalized_value_for_reporting(v) for k, v in value.items()}

        return value
