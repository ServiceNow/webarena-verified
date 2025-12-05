from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from webarena_verified.core.evaluation.evaluators import EVALUATOR_REGISTRY
from webarena_verified.core.utils import logger
from webarena_verified.core.utils.checksum import compute_data_file_checksum
from webarena_verified.types.config import EnvironmentConfig, WebArenaVerifiedConfig
from webarena_verified.types.eval import EvaluatorResult, TaskEvalContext, TaskEvalResult, TransformedAgentResponse
from webarena_verified.types.task import WebArenaSite
from webarena_verified.types.tracing import NetworkTrace

from .data_reader import WebArenaVerifiedDataReader


class WebArenaVerifiedEvaluator:
    """Programmatic interface for evaluating WebArena tasks.

    Simplified API: Evaluate tasks by providing TaskEvalContext directly.
    """

    def __init__(self, *, config: WebArenaVerifiedConfig, reader: WebArenaVerifiedDataReader):
        self.config = config
        self.reader = reader

    def evaluate_task(
        self,
        *,
        context: TaskEvalContext | None = None,
        task_id: int | None = None,
        agent_response: Any = None,
        network_trace: Any = None,
    ) -> TaskEvalResult:
        """Evaluate a single task with automatic format detection.

        This method supports two calling patterns:
        1. With context: evaluate_task(context=TaskEvalContext(...))
        2. With individual parameters: evaluate_task(task_id=1, agent_response=..., network_trace=...)

        Args:
            context: Pre-built TaskEvalContext (mutually exclusive with task_id/agent_response/network_trace)
            task_id: ID of the task to evaluate (required if context is None)
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

        Raises:
            ValueError: If both calling patterns are used or neither is used

        Examples:
            Using context (backward compatible):
            >>> context = TaskEvalContext(...)
            >>> result = evaluator.evaluate_task(context=context)

            Using individual parameters:
            >>> result = evaluator.evaluate_task(
            ...     task_id=1,
            ...     agent_response="answer: 42",
            ...     network_trace=Path("trace.har")
            ... )
        """
        has_context = context is not None
        has_individual_params = task_id is not None

        if has_context and has_individual_params:
            raise ValueError(
                "Cannot provide both 'context' and individual parameters "
                "(task_id, agent_response, network_trace). Use one calling pattern only."
            )

        if not has_context and not has_individual_params:
            raise ValueError("Must provide either 'context' or task_id (with agent_response and network_trace).")

        if has_context:
            return self._evaluate_with_context(context=context)

        assert task_id is not None, "task_id must be provided when using individual parameters"

        logger.info(f"Evaluating task {task_id}")
        try:
            task = self.reader.get_task_by_id(task_id)

            agent_response_raw = self._parse_agent_response(agent_response)
            network_trace_obj = self._parse_network_trace(network_trace)

            eval_context = TaskEvalContext(
                task=task,
                agent_response_raw=agent_response_raw,
                network_trace=network_trace_obj,
                config=self.config,
            )

            result = self._evaluate_with_context(context=eval_context)
            return result

        except Exception as e:
            error_msg = f"Failed to evaluate task {task_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return self._create_eval_error_result(task_id, error_msg)

    def _evaluate_with_context(self, *, context: TaskEvalContext) -> TaskEvalResult:
        """Evaluate a single task.

        Args:
            context: TaskEvalContext with task definition, agent response, network trace, and URL map

        Returns:
            TaskEvalResult with evaluation score, status, and detailed assertions

        Examples:
            >>> evaluator = WebArenaVerifiedEvaluator(config=config, reader=reader)
            >>> task = reader.get_task_by_id(1)
            >>> context = TaskEvalContext(
            ...     task=task,
            ...     agent_response_raw=agent_response_json,
            ...     network_trace=NetworkTrace.from_content(trace_file),
            ...     url_map=config.url_map
            ... )
            >>> result = evaluator.evaluate_task(context=context)
            >>> print(f"Score: {result.score}, Status: {result.status}")
        """

        validated_config = self._validate_config_for_eval(context=context)
        context = context.model_copy(update={"config": validated_config})

        task_id = context.task.task_id
        intent_template_id = context.task.intent_template_id
        sites = context.task.sites
        revision = context.task.revision

        logger.info(f"Starting evaluation for task_id={task_id}, intent_template_id={intent_template_id}")
        evaluators_results: list[EvaluatorResult] = []
        data_checksum = compute_data_file_checksum(self.config.test_data_file)

        try:
            for eval_cfg in context.task.eval:
                evaluator_class = EVALUATOR_REGISTRY.get(eval_cfg.evaluator)
                if evaluator_class is None:
                    raise KeyError(
                        f"Evaluator '{eval_cfg.evaluator}' not found. "
                        f"Available evaluators: {list(EVALUATOR_REGISTRY.keys())}"
                    )
                evaluator = evaluator_class()
                evaluator_result = evaluator.evaluate(context=context, config=eval_cfg)
                evaluators_results.append(evaluator_result)

            assert len(context.task.eval) == len(evaluators_results), (
                f"Number of evaluator results ({len(evaluators_results)}) does not match number of evaluators "
                f"in task config ({len(context.task.eval)}) for task {task_id}"
            )
            return TaskEvalResult.create(
                task_id=task_id,
                intent_template_id=intent_template_id,
                sites=sites,
                task_revision=revision,
                evaluators_results=evaluators_results,
                data_checksum=data_checksum,
            )

        except Exception as e:
            error_msg = f"Error during evaluation orchestration for task {task_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return TaskEvalResult.create(
                task_id=task_id,
                intent_template_id=intent_template_id,
                sites=sites,
                task_revision=revision,
                data_checksum=data_checksum,
                error_msg=error_msg,
                is_error=True,
                evaluators_results=evaluators_results,
            )

    def _parse_agent_response(self, agent_response: Any) -> Any:
        """Parse agent response to the format expected by evaluators.

        Args:
            agent_response: Response in str, dict, list, None, or Path format

        Returns:
            Raw agent response (str, dict, list, or None) ready for evaluation

        Raises:
            TypeError: If agent_response type is not supported
            FileNotFoundError: If Path does not exist
            ValueError: If file content is invalid
        """
        if isinstance(agent_response, (str, dict, list, type(None), TransformedAgentResponse)):
            return agent_response
        elif isinstance(agent_response, Path):
            logger.info(f"Loading agent response from file: {agent_response}")
            if not agent_response.exists():
                raise FileNotFoundError(f"Agent response file not found: {agent_response}")

            content = agent_response.read_text()
            return content
        else:
            raise TypeError(f"agent_response must be str, dict, list, None, or Path, got {type(agent_response)}")

    def _parse_network_trace(self, network_trace: Any) -> NetworkTrace:
        """Parse network trace to NetworkTrace object.

        Args:
            network_trace: Trace in list, Path, or NetworkTrace format

        Returns:
            NetworkTrace object ready for evaluation

        Raises:
            TypeError: If network_trace type is not supported
            FileNotFoundError: If Path does not exist
            ValueError: If content is invalid HAR format
        """
        if isinstance(network_trace, NetworkTrace) or network_trace is None:
            return network_trace

        elif isinstance(network_trace, Path):
            logger.info(f"Loading network trace from file: {network_trace}")
            if not network_trace.exists():
                raise FileNotFoundError(f"Network trace file not found: {network_trace}")
            return NetworkTrace.from_content(network_trace)

        elif isinstance(network_trace, (list, tuple)):
            return NetworkTrace.from_content(list(network_trace) if isinstance(network_trace, tuple) else network_trace)

        else:
            raise TypeError(f"network_trace must be list, Path, or NetworkTrace, got {type(network_trace)}")

    def _create_eval_error_result(self, task_id: int, error_msg: str) -> TaskEvalResult:
        """Create an error result for unhandled evaluation errors.

        Args:
            task_id: Task ID that failed
            error_msg: Error message describing the failure

        Returns:
            TaskEvalResult with ERROR status and error message
        """
        try:
            task = self.reader.get_task_by_id(task_id)
            intent_template_id = task.intent_template_id
            sites = task.sites
            revision = task.revision
        except Exception:
            intent_template_id = -1
            sites = ()
            revision = -1

        try:
            data_checksum = compute_data_file_checksum(self.config.test_data_file)
        except Exception:
            data_checksum = "error"

        return TaskEvalResult.create(
            task_id=task_id,
            intent_template_id=intent_template_id,
            sites=sites,
            task_revision=revision,
            data_checksum=data_checksum,
            error_msg=error_msg,
            is_error=True,
        )

    def _validate_config_for_eval(self, *, context: TaskEvalContext) -> WebArenaVerifiedConfig | None:
        """Try to correct eval config by extracting URL from network trace as fallback.

        If config.environments is None, this function attempts to extract the base URL
        from the first network event in the trace and create a minimal EnvironmentConfig.

        Args:
            context: TaskEvalContext with network trace and task information

        Returns:
            Updated config with environments populated from network trace, or original config if:
            - config.environments already exists
            - network_trace is None
            - network_trace has no events
            - URL extraction fails

        Note:
            This is a fallback mechanism for cases where config doesn't include environments.
            It creates a minimal EnvironmentConfig using the base URL from the first network event.
        """

        is_valid_config = True
        if context.config.environments:
            is_valid_config = all(
                site in context.config.environments and context.config.environments[site].urls
                for site in context.task.sites
            )
        else:
            is_valid_config = False

        if is_valid_config:
            return context.config

        logger.info("Attempting to correct eval config from network trace if needed due to empty environment urls")

        # Can't extract URL without trace
        if context.network_trace is None or not context.network_trace.evaluation_events:
            raise ValueError("Invalid config: environments missing and network trace unavailable")

        try:
            # Best effort: extract base URL from a network event per site
            environments = {}
            for idx, site in enumerate(context.task.sites):
                # Use event at index if available, otherwise fall back to first event
                event_idx = min(idx, len(context.network_trace.evaluation_events) - 1)
                first_event = context.network_trace.evaluation_events[event_idx]
                first_url = first_event.url
                parsed_url = urlparse(first_url)
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                logger.info(f"Config auto correct using base URL from network trace: {base_url}")

                # For admin sites, append /admin path
                if site == WebArenaSite.SHOPPING_ADMIN:
                    site_url = f"{base_url}/admin"
                else:
                    site_url = base_url

                environments[site] = EnvironmentConfig(urls=[site_url])

            # Create new config with corrected environments
            corrected_config = context.config.model_copy(deep=True)
            corrected_config.environments = environments

            logger.warning(
                f"Auto-corrected config using best-effort URL extraction from trace for sites: {[s.name for s in context.task.sites]}. "
                "This is not recommended - please provide a proper config with environment URLs."
            )
            return corrected_config

        except Exception as e:
            raise ValueError(f"Failed to correct eval config from network trace: {e}") from e
