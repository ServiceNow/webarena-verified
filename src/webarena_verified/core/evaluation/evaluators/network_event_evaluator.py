"""NetworkEventEvaluator for validating network request details.

This evaluator validates network events by checking URL, headers, query parameters,
and response status against expected criteria using four-step architecture.
"""

import re
from functools import partial
from types import MappingProxyType
from typing import Any, cast

from webarena_verified.core.evaluation.data_types import URL
from webarena_verified.core.utils import logger
from webarena_verified.core.utils.jsonpath_utils import extract_jsonpath_value, is_jsonpath_key
from webarena_verified.types.common import SerializableMappingProxyType
from webarena_verified.types.eval import EvalAssertion, EvalStatus, TaskEvalContext
from webarena_verified.types.task import NetworkEventEvaluatorCfg, NetworkEventSpec
from webarena_verified.types.tracing import NetworkEvent

from .base import BaseEvaluator


class NetworkEventEvaluator(BaseEvaluator[NetworkEventEvaluatorCfg]):
    """Validates network events using four-step architecture.

    The evaluator:
    - Searches for network events matching URL and headers criteria
    - Validates all fields in the expected block (url, headers, query_string, response_status, post_data)
    - Supports checking the last matching event or any matching event
    - Respects ignored query parameters during comparison
    - Supports alternatives in expected values

    Architecture:
    - Step 1: Filter and extract event data from network trace
    - Step 2: Get expected event data from config (with alternatives)
    - Step 3: Normalize both using schema-based normalization
    - Step 4: Compare normalized values structurally
    """

    def _get_actual_value(self, context: TaskEvalContext, config: NetworkEventEvaluatorCfg) -> list[NetworkEventSpec]:
        """Extract and navigate to actual value from network events.

        Steps:
        1. Filter network events based on config criteria (URL pattern, method, event_type, headers)
        2. Select event(s) based on config (last event only, or all matching)
        3. Extract relevant data from selected events

        Args:
            context: Task evaluation context
            config: Evaluator configuration

        Returns:
            Raw actual value before normalization (single event data dict or list of event data dicts)
            Returns None if no matching events found

        Raises:
            ValueError: If no events match the criteria
        """
        # Step 1: Filter events based on config criteria (search through all evaluation events)
        matching_events = self._filter_events_by_criteria(context.network_trace.evaluation_events, context, config)

        if not matching_events:
            return []

        # Step 2: Select event(s)
        selected_events = [matching_events[-1]] if config.last_event_only else matching_events

        # Step 3: Extract relevant data from events
        extracted_data = []
        for event in selected_events:
            event_data = self._extract_event_data(event, config, context)
            extracted_data.append(event_data)

        return [extracted_data[0]] if config.last_event_only else extracted_data

    def _get_expected_value(self, config: NetworkEventEvaluatorCfg) -> NetworkEventSpec:
        """Get expected value from config.

        Returns:
            Expected network event data as dict with alternatives support
        """
        return config.expected

    def _normalized_expected_value(self, expected_raw: Any, config: NetworkEventEvaluatorCfg, context: TaskEvalContext):
        """Normalize expected value using _normalize_value helper.

        Args:
            expected_raw: Raw expected value from config
            config: Evaluator configuration
            context: Task evaluation context

        Returns:
            Normalized expected value
        """
        return self._normalize_value(
            expected_raw,
            strict=True,
            config=config,
            context=context,
        )

    def _normalized_actual_value(
        self, actual_raw: Any, normalized_expected: Any, config: NetworkEventEvaluatorCfg, context: TaskEvalContext
    ):
        post_data = normalized_expected.get("post_data")
        post_keys = post_data.keys() if post_data else None
        if post_keys is not None:
            post_keys = tuple(k.strip() for k in post_keys)

        response_content = normalized_expected.get("response_content")
        response_content_keys = response_content.keys() if response_content else None
        if response_content_keys is not None:
            response_content_keys = tuple(k.strip() for k in response_content_keys)

        # TODO: Move this at BaseModel level
        expected_keys = []
        for key in normalized_expected:
            if normalized_expected[key] is not None:
                expected_keys.append(key)

        return self._normalize_value(
            actual_raw,
            strict=False,
            config=config,
            context=context,
            post_keys=post_keys,
            response_content_keys=response_content_keys,
            expected_keys=tuple(expected_keys),
        )

    def _normalize_response_content_field(
        self,
        normalized: dict,
        *,
        strict: bool,
        response_content_keys: tuple[str, ...] | None = None,
    ) -> None:
        """Normalize response_content field by extracting JSONPath values.

        Modifies the normalized dict in-place, replacing response_content with normalized version.

        Args:
            normalized: Dictionary containing network event data
            strict: Whether to use strict mode
            response_content_keys: Expected response_content keys (may include JSONPath expressions)
        """
        response_content_dict = normalized.get("response_content")
        if not response_content_dict:
            normalized["response_content"] = None
            return

        # Handle JSONPath extraction if response_content_keys contains JSONPath expressions
        if response_content_keys:
            # Separate regular keys from JSONPath keys
            regular_keys = [k for k in response_content_keys if not is_jsonpath_key(k)]
            jsonpath_keys = [k for k in response_content_keys if is_jsonpath_key(k)]

            flattened_actual = {}

            # Extract regular keys (existing logic)
            for key in regular_keys:
                if key in response_content_dict:
                    flattened_actual[key] = response_content_dict[key]

            # Extract JSONPath keys (new logic)
            for jsonpath_key in jsonpath_keys:
                value = extract_jsonpath_value(response_content_dict, jsonpath_key, strict=strict)
                flattened_actual[jsonpath_key] = value

            response_content_dict = flattened_actual

        normalized["response_content"] = response_content_dict

    def _normalize_response_cookies_field(
        self,
        normalized: dict,
        *,
        strict: bool,
    ) -> None:
        """Normalize response_cookies field using NormalizedString for pattern matching.

        Cookie values are already URL-decoded during extraction.
        Use NormalizedString for case-insensitive regex pattern matching.

        Args:
            normalized: Dictionary containing network event data
            strict: Whether to use strict mode
        """
        cookies_dict = normalized.get("response_cookies")
        if not cookies_dict:
            normalized["response_cookies"] = None
            return

        # Normalize each cookie value as a string (supports regex patterns)
        normalized_cookies = {}
        for cookie_name, cookie_value in cookies_dict.items():
            # NormalizedString handles regex pattern matching (^.*pattern.*$)
            normalized_cookies[cookie_name] = self.value_normalizer.normalize_single(
                cookie_value, "string", strict=strict
            )
        normalized["response_cookies"] = normalized_cookies

    def _normalize_post_data_field(
        self,
        normalized: dict,
        *,
        config: NetworkEventEvaluatorCfg,
        strict: bool,
        post_keys: tuple[str, ...] | None = None,
        context: TaskEvalContext,
    ) -> None:
        """Normalize post_data field by filtering, extracting JSONPath, and applying schema.

        Modifies the normalized dict in-place, replacing post_data with normalized version.

        Args:
            normalized: Dictionary containing network event data
            config: Evaluator configuration
            strict: Whether to use strict mode
            post_keys: Expected post_data keys (may include JSONPath expressions)
        """
        post_data_dict = normalized.get("post_data")
        if not post_data_dict:
            normalized["post_data"] = None
            return

        # Apply ignored params filtering first, immediately after confirming post_data_dict is present
        if config.ignored_post_data_params_patterns:
            post_data_dict = {k: v for k, v in post_data_dict.items() if not self._should_ignore_post_param(k, config)}

        # Handle JSONPath extraction if post_keys contains JSONPath expressions
        if post_keys:
            # Separate regular keys from JSONPath keys
            regular_keys = [k for k in post_keys if not is_jsonpath_key(k)]
            jsonpath_keys = [k for k in post_keys if is_jsonpath_key(k)]

            flattened_actual = {}

            # Extract regular keys (existing logic)
            for key in regular_keys:
                flattened_actual[key] = post_data_dict.get(key)

            # Extract JSONPath keys (new logic)
            for jsonpath_key in jsonpath_keys:
                value = extract_jsonpath_value(post_data_dict, jsonpath_key, strict=strict)
                flattened_actual[jsonpath_key] = value

            post_data_dict = flattened_actual

        # Normalize post_data values with schema (for type-aware comparison)
        if post_data_dict:
            post_data_schema = config.post_data_schema or {}

            _derender_url_fct = partial(context.config.derender_url, sites=context.task.sites, strict=strict)
            normalized["post_data"] = self.value_normalizer.normalize(
                post_data_dict, post_data_schema, strict=strict, derender_url_fct=_derender_url_fct
            )
        else:
            normalized["post_data"] = post_data_dict

    def _normalize_headers_field(
        self,
        normalized: dict,
        *,
        context: TaskEvalContext,
        config: NetworkEventEvaluatorCfg,
        strict: bool,
    ) -> None:
        """Normalize headers field by derendering URL values.

        Modifies the normalized dict in-place, replacing headers with derendered versions.

        Args:
            normalized: Dictionary containing network event data
            context: Task evaluation context
            config: Evaluator configuration
            strict: Whether to use strict mode
        """
        headers_dict = normalized.get("headers")
        if headers_dict is None:
            return

        derendered_headers = {}
        task_sites = context.task.sites
        for header_name, header_value in headers_dict.items():
            if header_name in ["redirect_url", "referer"] and header_value:
                _normalized_url = self._normalized_url(
                    url=header_value,
                    context=context,
                    config=config,
                    strict=strict,
                    query_params=None,  # redirect_url has query params embedded in the URL string
                )
                derendered_headers[header_name] = _normalized_url
            else:
                try:
                    # Try to derender (e.g., referer URLs) and handle strings/regexp
                    _derendered = context.config.derender_url(header_value, sites=task_sites, strict=False)
                    derendered_headers[header_name] = self.value_normalizer.normalize_single(
                        _derendered, "string", strict=strict
                    )
                except Exception as e:
                    # Keep original if derendering fails
                    logger.info(f"Failed to derender header '{header_name}': {e}")
                    derendered_headers[header_name] = header_value
        normalized["headers"] = derendered_headers

    def _normalize_url_field(
        self,
        normalized: dict,
        *,
        context: TaskEvalContext,
        config: NetworkEventEvaluatorCfg,
        strict: bool,
    ) -> None:
        """Normalize URL field with query params.

        Modifies the normalized dict in-place, replacing the URL with normalized version.

        Args:
            normalized: Dictionary containing network event data
            context: Task evaluation context
            config: Evaluator configuration
            strict: Whether to use strict mode
        """
        url_value = normalized["url"]
        query_params = normalized.get("query_params")

        # Normalize URL with query_params and all URL-specific config
        # This handles: filtering, derendering, base64 decoding
        _normalized_url = self._normalized_url(
            url=url_value,
            context=context,
            config=config,
            strict=strict,
            query_params=query_params,
        )
        normalized["url"] = _normalized_url

    def _convert_to_dict_list(self, value: Any) -> tuple[list[dict], bool]:
        """Convert NetworkEventSpec value(s) to list of dictionaries.

        Args:
            value: NetworkEventSpec or list of NetworkEventSpec objects

        Returns:
            Tuple of (list of dicts, is_list_input flag)
        """
        is_list_input = False
        if isinstance(value, (list, tuple)):
            normalized_list = [
                v.model_dump(mode="json", exclude_none=True) if isinstance(v, NetworkEventSpec) else dict(v)
                for v in value
            ]
            is_list_input = True
        else:
            normalized = (
                value.model_dump(mode="json", exclude_none=True) if isinstance(value, NetworkEventSpec) else dict(value)
            )
            normalized_list = [normalized]
        return normalized_list, is_list_input

    def _normalize_value(
        self,
        value: Any,
        *,
        strict: bool,
        config: NetworkEventEvaluatorCfg,
        context: TaskEvalContext,
        post_keys: tuple[str, ...] | None = None,
        response_content_keys: tuple[str, ...] | None = None,
        expected_keys: tuple[str, ...] | None = None,
    ) -> list[MappingProxyType] | MappingProxyType | None:
        """Normalize NetworkEventSpec using data type classes.
        Returns:
            Normalized network event data as MappingProxyType or None
        """
        if not value:
            if strict:
                raise ValueError("Cannot normalize empty network event data in strict mode.")
            return None

        # Convert NetworkEventSpec to dict
        normalized_list, is_list_input = self._convert_to_dict_list(value)

        final = []
        for normalized in normalized_list:
            # Normalize each field using helper methods
            self._normalize_url_field(normalized, context=context, config=config, strict=strict)
            self._normalize_headers_field(normalized, context=context, config=config, strict=strict)
            self._normalize_post_data_field(
                normalized, config=config, strict=strict, post_keys=post_keys, context=context
            )
            self._normalize_response_content_field(
                normalized, strict=strict, response_content_keys=response_content_keys
            )
            self._normalize_response_cookies_field(normalized, strict=strict)

            # Remove query_params key as it's now embedded in normalized URL
            if "query_params" in normalized:
                del normalized["query_params"]

            final.append(MappingProxyType(normalized))

        if is_list_input:
            return final  # type: ignore
        else:
            assert len(final) == 1
            return final[0]

    # ========================================================================
    # Event Comparison
    # ========================================================================

    def _compare_values(
        self,
        actual_normalized: list[MappingProxyType] | None,
        expected_normalized: MappingProxyType,
        config: NetworkEventEvaluatorCfg,
        context: TaskEvalContext,
        ordered: bool = False,
    ) -> list[EvalAssertion]:
        """Compare normalized actual vs expected using ValueComparator.

        Args:
            actual_normalized: List of normalized actual network events
            expected_normalized: Normalized expected network event
            ordered: Whether order matters (always False for network events)
            config: Evaluator configuration

        Returns:
            List of EvalAssertion objects (empty list = success)
        """
        # Check should_not_exist mode first
        if config.should_not_exist:
            if not actual_normalized:
                # Success: no events found (as expected)
                return []
            else:
                # Failure: events found when they shouldn't exist
                return [
                    EvalAssertion(
                        status=EvalStatus.FAILURE,
                        assertion_name="unexpected_navigation_event",
                        assertion_msgs=(
                            f"Found {len(actual_normalized)} matching event(s) "
                            f"when none were expected (should_not_exist=True).",
                        ),
                    )
                ]

        # Normal comparison mode
        if not actual_normalized:
            return [
                EvalAssertion(
                    status=EvalStatus.FAILURE,
                    assertion_name="missing_navigation_event",
                    assertion_msgs=("No matching network event found that satisfies all expected criteria.",),
                )
            ]

        # Compare each actual event against expected using full object comparison
        for actual in actual_normalized:
            # Use comparator.compare for full event comparison
            assertions = self.value_comparator.compare(
                actual=actual,
                expected=expected_normalized,
                ordered=ordered,
                value_name="network_event",
                ignore_extra_keys=True,  # Ignore extra fields in actual that aren't in expected
            )

            # If no assertions (empty list), we found a perfect match
            if not assertions:
                return []

        # No matching event found - return failure with summary
        return [
            EvalAssertion(
                status=EvalStatus.FAILURE,
                assertion_name="missing_navigation_event",
                assertion_msgs=(
                    f"No matching network event found. Checked {len(actual_normalized)} event(s) "
                    f"but none matched all expected criteria.",
                ),
            )
        ]

    # ========================================================================
    # Helper Methods - Event Filtering and Extraction
    # ========================================================================

    def _extract_event_data(
        self, event: NetworkEvent, config: NetworkEventEvaluatorCfg, context: TaskEvalContext
    ) -> NetworkEventSpec:
        """Extract raw data from network event (pure extraction, no transformations).

        All transformations (filtering, derendering, base64 decoding, normalization)
        happen during the normalization step, not here.

        Args:
            event: Network event to extract data from
            config: Evaluator configuration
            context: Task evaluation context

        Returns:
            NetworkEventSpec with raw extracted event data
        """
        # Extract raw URL (no decoding, no reconstruction, no derendering)
        url = event.url

        # Extract headers (case-insensitive matching, no derendering)
        headers = None
        if config.expected.headers:
            event_headers_lower = {
                header["name"].lower(): header["value"] for header in event.data["request"]["headers"]
            }
            extracted_headers = {}
            for expected_header_name in config.expected.headers:
                expected_header_lower = expected_header_name.lower()
                if expected_header_lower in event_headers_lower:
                    extracted_headers[expected_header_name] = event_headers_lower[expected_header_lower]
            headers = MappingProxyType(extracted_headers) if extracted_headers else None

        # Extract post_data if expected
        # Cast to SerializableMappingProxyType for type checking (Pydantic will validate/convert)
        post_data = cast(SerializableMappingProxyType | None, event.post_data if config.expected.post_data else None)

        # Extract response content if expected
        # Cast to SerializableMappingProxyType for type checking (Pydantic will validate/convert)
        response_content = cast(
            SerializableMappingProxyType | None, event.response_content if config.expected.response_content else None
        )

        # Extract response_cookies if expected
        response_cookies = None
        if config.expected.response_cookies:
            # Get decoded cookie values
            event_cookies = event.response_cookies
            extracted_cookies = {}
            for expected_cookie_name in config.expected.response_cookies:
                if expected_cookie_name in event_cookies:
                    extracted_cookies[expected_cookie_name] = event_cookies[expected_cookie_name]
            response_cookies = MappingProxyType(extracted_cookies) if extracted_cookies else None

        # Return NetworkEventSpec object with raw data
        # Note: query_params will be extracted from URL during normalization
        return NetworkEventSpec(
            url=url,
            headers=headers,
            response_status=event.request_status,
            query_params=None,
            post_data=post_data,
            http_method=event.http_method,
            response_content=response_content,
            response_cookies=response_cookies,
        )

    def _filter_events_by_criteria(
        self, events: tuple[NetworkEvent, ...], context: TaskEvalContext, config: NetworkEventEvaluatorCfg
    ) -> tuple[NetworkEvent, ...]:
        """Filter events by URL and headers criteria.

        Args:
            events: Events to filter
            context: Task evaluation context
            config: Evaluator configuration

        Returns:
            Filtered list of events matching URL and headers criteria
        """

        if not events:
            return ()

        # Handle navigate tasks (We only care about the last navigation event)
        # For cases where we check navigation events via subsequent XHR/fetch requests,
        # we use the normal filtering logic below.
        if context.task.is_navigate_task and config.expected.http_method == "GET":
            last_navigation_event = [e for e in events if e.is_navigation_event]
            matched_events = (last_navigation_event[-1],) if last_navigation_event else ()
            return matched_events

        matches = []
        try:
            expected_url: URL = self._normalized_url(config.expected.url, context=context, config=config, strict=True)  # type: ignore
            expected_referer_url: URL | None = None
            if config.expected.headers and "referer" in config.expected.headers:
                expected_referer_url = self._normalized_url(
                    config.expected.headers["referer"], context=context, config=config, strict=True
                )  # type: ignore
        except Exception as e:
            logger.error(f"Error normalizing expected URL or referer for filtering: {e}")
            raise

        for event in events:
            # Check HTTP method
            if config.expected.http_method and event.http_method.lower() != config.expected.http_method.lower():
                continue

            # Check URL path match
            try:
                event_url: URL = self._normalized_url(event.url, context=context, config=config, strict=False)  # type: ignore
                if isinstance(event_url, str):
                    raise ValueError(
                        f"Event URL '{event.url}' normalized to string ('{event_url}') instead of URL object."
                    )
            except Exception as e:
                logger.info(f"Failed to normalize event URL '{event.url}' during filtering: {e}")
                raise

            if not expected_url.compare_path(event_url):
                continue

            # Check referer header if expected
            event_referer = event.request_headers.get("referer")
            if expected_referer_url and event_referer:
                normalized_event_referer: URL = self._normalized_url(
                    event_referer, context=context, config=config, strict=False
                )  # type: ignore
                if not expected_referer_url.compare_path(normalized_event_referer):
                    continue

            matches.append(event)

        return tuple(matches)

    def _normalized_url(
        self,
        url: str | list[str],
        context: TaskEvalContext,
        config: NetworkEventEvaluatorCfg,
        strict: bool,
        query_params: dict[str, str | list[str]] | None = None,
    ) -> URL | list[URL]:
        _render_url_fct = partial(context.config.render_url, sites=context.task.sites, strict=strict)
        _derender_url_fct = partial(context.config.derender_url, sites=context.task.sites, strict=strict)
        _normalized_query_params_fct = (
            partial(self.value_normalizer.normalize, schema=config.query_params_schema, strict=strict)
            if config.query_params_schema
            else None
        )

        normalized_url: URL = self.value_normalizer.normalize_single(
            url,
            "url",
            strict=strict,
            decode_base64_query=config.decode_base64_query,
            ignored_query_parameters=config.ignored_query_params,
            ignored_query_parameters_patterns=config.ignored_query_params_patterns,
            render_url_fct=_render_url_fct,
            derender_url_fct=_derender_url_fct,
            normalize_query_params_fct=_normalized_query_params_fct,
            query_params=query_params,
        )  # type: ignore

        return normalized_url

    def _should_ignore_post_param(self, param_name: str, config: NetworkEventEvaluatorCfg) -> bool:
        """Check if a POST data parameter should be ignored based on config.

        Args:
            param_name: Name of the POST data parameter
            config: Evaluator configuration

        Returns:
            True if parameter should be ignored, False otherwise
        """
        # Check regex pattern matches
        if config.ignored_post_data_params_patterns:
            for pattern in config.ignored_post_data_params_patterns:
                try:
                    if re.search(pattern, param_name):
                        return True
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{pattern}' in ignored_post_data_params_patterns: {e}")
                    continue

        return False
