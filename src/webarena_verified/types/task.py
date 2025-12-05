"""Data models for WebArena Verified tasks (version >= 2.0.0)."""

from enum import StrEnum
from typing import Annotated, Generic, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .agent_response import FinalAgentResponse, _FinalAgentResponse
from .common import NonEmptyStr, QueryParams, SerializableMappingProxyType


# ============================================================================
# Site Enum
# ============================================================================
class WebArenaSite(StrEnum):
    """Supported web platforms in the WebArena benchmark.

    Each site represents a different web application environment where tasks are executed.
    """

    GITLAB = "gitlab"
    MAP = "map"
    REDDIT = "reddit"
    SHOPPING_ADMIN = "shopping_admin"
    SHOPPING = "shopping"
    WIKIPEDIA = "wikipedia"
    HOMEPAGE = "homepage"

    @classmethod
    def _missing_(cls, value):
        # Strip underscores and try to match
        if isinstance(value, str):
            stripped = value.strip("_")
            for member in cls:
                if member.value == stripped or member.name == stripped:
                    return member
        return None

    @property
    def url_name_template(self) -> str:
        """The name that appears in the URL for this site."""
        return f"__{self.value.upper()}__"


# ============================================================================
# Evaluation Models
# ============================================================================
ExpectedT = TypeVar("ExpectedT")


class BaseEval(BaseModel, Generic[ExpectedT]):
    """Base class for all evaluation validators."""

    expected: ExpectedT

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )


class AgentResponseEvaluatorCfg(BaseEval[_FinalAgentResponse]):
    """Validates the agent's response structure, performed operation type, status, and retrieved data.

    Checks that the agent returns properly formatted responses with correct operation types
    (retrieve, navigate, mutate), status codes, and expected data values.

    Example:
        ```json
        {
            "evaluator": "AgentResponseEvaluator",
            "ordered": false,
            "results_schema": {"type": "array", "items": {"type": "string"}},
            "expected": {
                "task_type": "retrieve",
                "status": "SUCCESS",
                "retrieved_data": ["Product Name"]
            }
        }
        ```
    """

    evaluator: Literal["AgentResponseEvaluator"] = "AgentResponseEvaluator"

    ordered: bool = False
    """Whether the retrieved data must match the expected order."""

    results_schema: SerializableMappingProxyType
    """JSON schema defining the structure of the retrieved data array."""


class NetworkEventSpec(BaseModel):
    """Network event validation criteria.

    All fields in the expected block are validated against matching network events.

    Example (basic):
        ```json
        {
            "url": "__SHOPPING_ADMIN__/mui/index/render/?namespace=sales_order_grid",
            "headers": {
                "referer": "__SHOPPING_ADMIN__/sales/order/",
                "X-Requested-With": "XMLHttpRequest"
            },
            "query_string": {"namespace": "sales_order_grid", "filters[status]": "processing"},
            "response_status": 200,
            "http_method": "GET"
        }
        ```

    Example (with JSONPath in post_data):
        ```json
        {
            "url": "__GITLAB__/notes",
            "http_method": "POST",
            "post_data": {
                "$.note.note": "lgtm",
                "$.note.noteable_type": "MergeRequest"
            },
            "response_status": 200
        }
        ```

    Example (hybrid - regular + JSONPath keys):
        ```json
        {
            "url": "__GITLAB__/api/update",
            "http_method": "POST",
            "post_data": {
                "user_id": "123",
                "$.metadata.timestamp": "2024-01-01"
            },
            "response_status": 200
        }
        ```
    """

    url: NonEmptyStr | list[NonEmptyStr]
    """URL to search for and validate in network events (required)."""

    headers: SerializableMappingProxyType | None = None
    """Optional request headers to match and validate (case-insensitive names, exact values)."""

    query_params: QueryParams | None = None
    """Optional query parameters to validate in the network request."""

    post_data: SerializableMappingProxyType | None = None
    """Optional POST data to validate in the network request.

    Supports JSONPath expressions for extracting values from nested structures.
    Keys starting with '$' are treated as JSONPath expressions.
    Can mix regular top-level keys with JSONPath keys in the same dict.

    Examples:
        Regular keys: {"user_id": "123", "action": "update"}
        JSONPath keys: {"$.note.note": "lgtm", "$.note.noteable_type": "MergeRequest"}
        Hybrid: {"user_id": "123", "$.metadata.timestamp": "2024-01-01"}
    """

    response_content: SerializableMappingProxyType | None = None
    """Optional response content to validate in the network response.

    Supports JSONPath expressions for extracting values from nested structures.
    Keys starting with '$' are treated as JSONPath expressions.

    Examples:
        Regular keys: {"status": "success"}
        JSONPath keys: {"$.data.user.name": "Alice", "$.data.status": "success"}
    """

    response_status: int = 200
    """Expected HTTP status code (default: 200)."""

    http_method: str = "GET"
    """Expected HTTP method (default: GET for navigation events)."""

    response_cookies: SerializableMappingProxyType | None = None
    """Optional response cookies to validate in the network response.

    Cookie values are URL-decoded automatically for pattern matching.
    Supports regex patterns via NormalizedString (case-insensitive).

    Example:
        {"mage-messages": "^.*toothpaste.* has been added to your wish list.*$"}
    """


class NetworkEventEvaluatorCfg(BaseEval[NetworkEventSpec]):
    """Validates network events by checking URL, headers, query parameters, response status, event type, and HTTP method.

    Searches for network events matching the expected criteria and validates all fields
    in the expected block. Provides a cleaner API where all validation criteria are
    grouped under 'expected'.

    Example:
        ```json
        {
            "evaluator": "NetworkEventEvaluator",
            "site": "shopping_admin",
            "url_match_mode": "prefix",
            "last_event_only": true,
            "ignored_query_params_patterns": ["^paging", "^sorting", "isAjax"],
            "expected": {
                "url": "__SHOPPING_ADMIN__/mui/index/render/?namespace=sales_order_grid",
                "headers": {
                    "referer": "__SHOPPING_ADMIN__/sales/order/",
                    "X-Requested-With": "XMLHttpRequest"
                },
                "query_string": {
                    "namespace": "sales_order_grid",
                    "filters[status]": "processing"
                },
                "post_data": {
                    "report_type": "created_at_order",
                    "from": "02/1/2023"
                },
                "response_status": 200,
                "http_method": "GET"
            }
        }
        ```
    """

    evaluator: Literal["NetworkEventEvaluator"] = "NetworkEventEvaluator"

    last_event_only: bool = True
    """If True, validate only the last matching event. If False, validate if ANY event matches."""

    ignored_query_params: tuple[str, ...] | None = None
    """Query parameter names to ignore during comparison (literal matching)."""

    ignored_query_params_patterns: tuple[str, ...] | None = None
    """Regex patterns for query parameter names to ignore during comparison (case-sensitive)."""

    decode_base64_query: bool = False
    """If True, decode base64-encoded query strings from URL path before comparison."""

    query_params_schema: SerializableMappingProxyType | None = None
    """Optional JSON schema for type-aware query parameter comparison (e.g., dates, currency)."""

    post_data_schema: SerializableMappingProxyType | None = None
    """Optional JSON schema for type-aware post_data comparison (e.g., dates, currency)."""

    ignored_post_data_params_patterns: tuple[str, ...] | None = None
    """Regex patterns for POST data parameter names to ignore during comparison (case-sensitive)."""

    should_not_exist: bool = False
    """If True, validation succeeds when NO matching events are found (inverts default behavior)."""


EvaluatorCfg = Annotated[
    AgentResponseEvaluatorCfg | NetworkEventEvaluatorCfg,
    Field(discriminator="evaluator"),
]


# ============================================================================
# Task Model
# ============================================================================
class WebArenaVerifiedTask(BaseModel):
    """Pydantic model for a WebArena Verified task."""

    sites: tuple[WebArenaSite, ...]
    """List of platforms involved (e.g., gitlab, shopping_admin)."""

    task_id: int
    """Unique identifier for the task."""

    intent_template_id: int
    """Groups tasks from the same template."""

    start_urls: tuple[NonEmptyStr, ...]
    """Initial URLs where the task begins."""

    intent: NonEmptyStr
    """Natural language description of what to accomplish."""

    eval: tuple[EvaluatorCfg, ...]
    """Array of evaluator configurations."""

    intent_template: NonEmptyStr
    """Template with placeholders (e.g., 'Get top-{{n}} products')."""

    instantiation_dict: SerializableMappingProxyType
    """Values used to fill template placeholders."""

    revision: Annotated[int, Field(ge=1)]
    """Integer revision number tracking task changes (minimum 1)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    @model_validator(mode="after")
    def check_eval_has_agent_response(self) -> Self:
        """Validate that eval contains at least one AgentResponseEval item."""
        if not any(isinstance(item, AgentResponseEvaluatorCfg) for item in self.eval):
            raise ValueError("eval must contain at least one AgentResponseEval item")
        return self

    @property
    def expected_agent_response(self) -> FinalAgentResponse:
        """Return the expected agent response from the first AgentResponseEval."""
        for item in self.eval:
            if isinstance(item, AgentResponseEvaluatorCfg):
                return item.expected
        raise ValueError("No AgentResponseEval found in eval")

    @property
    def expected_action(self) -> str:
        """Return the expected task type from the expected agent response."""
        return self.expected_agent_response.task_type

    @property
    def network_event_evaluator_cfgs(self) -> tuple[NetworkEventEvaluatorCfg, ...]:
        """Return all NetworkEventEvaluatorCfg items in eval."""
        return tuple(item for item in self.eval if isinstance(item, NetworkEventEvaluatorCfg))

    @property
    def is_navigate_task(self) -> bool:
        """Check if this is a navigate task."""
        return self.expected_agent_response.is_navigate

    @property
    def is_mutate_task(self) -> bool:
        """Check if this is a mutate task."""
        return self.expected_agent_response.is_mutate

    @property
    def is_retrieve_task(self) -> bool:
        """Check if this is a retrieve task."""
        return self.expected_agent_response.is_retrieve

    @property
    def sites_str(self) -> str:
        """Return a comma-separated string of site names."""
        return "-".join(sorted([site.value for site in self.sites]))

    def __str__(self) -> str:
        """Pretty print task with key information."""
        return (
            f"WebArenaVerifiedTask(\n"
            f"  task_id={self.task_id},\n"
            f"  intent_template_id={self.intent_template_id},\n"
            f"  sites={list(self.sites)},\n"
            f"  intent={self.intent!r},\n"
            f"  start_urls={list(self.start_urls)},\n"
            f")"
        )

    def __repr__(self) -> str:
        """Repr with key information."""
        return f"WebArenaVerifiedTask(task_id={self.task_id}, intent_template_id={self.intent_template_id}, sites=[{self.sites_str}])"
