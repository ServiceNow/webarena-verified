"""URL normalization with query parameter handling."""

import re
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Self
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, model_serializer
from url_normalize import url_normalize

from webarena_verified.core.utils import is_regexp
from webarena_verified.core.utils.url_utils import extract_base64_query, normalize_query
from webarena_verified.types.common import QueryParams

from .base import NormalizedType


class _NormalizedUrlValues(BaseModel):
    base_url: str
    query_params: QueryParams
    is_regex: bool = False

    def __str__(self) -> str:
        query_string = ""
        if self.query_params:
            parts = []
            for k, values in sorted(self.query_params.items()):
                for v in values:
                    parts.append(f"{k}={v}")
            query_string = "&".join(parts)

        # Parse base_url to reconstruct with query
        parsed = urlparse(self.base_url)
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                "",  # params not used in urlunparse
                query_string,
                parsed.fragment,
            )
        )

    @model_serializer
    def _serialize(self) -> dict:
        """Serialize to JSON as an object with base_url and query_params."""

        def convert_to_serializable(obj: Any) -> Any:
            """Recursively convert NormalizedType instances to plain values."""
            if isinstance(obj, (MappingProxyType, dict)):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return type(obj)(convert_to_serializable(item) for item in obj)
            elif isinstance(obj, NormalizedType):
                return obj.normalized
            else:
                return obj

        return {
            "base_url": self.base_url,
            "query_params": convert_to_serializable(self.query_params),
        }

    def __hash__(self) -> int:
        """Make hashable by converting query_params to frozenset."""
        query_frozen = frozenset(self.query_params.items()) if self.query_params else frozenset()
        return hash((self.base_url, query_frozen))

    def __deepcopy__(self, memo):
        """Custom deepcopy to handle MappingProxyType in query_params.

        Converts MappingProxyType query_params to regular dict to avoid pickling errors.
        Properly deepcopies nested structures in query_params.
        """
        # Convert MappingProxyType to dict and deepcopy to handle nested structures
        query_params_dict = deepcopy(dict(self.query_params), memo) if self.query_params else {}

        # Wrap the deepcopied dict back in MappingProxyType to preserve immutability
        # Note: base_url (str) and is_regex (bool) are immutable, no need to deepcopy
        return _NormalizedUrlValues(
            base_url=self.base_url, query_params=MappingProxyType(query_params_dict), is_regex=self.is_regex
        )

    def matches_base_path(self, other: "_NormalizedUrlValues", render_url_fct=None) -> bool:
        """Compare only base_url (ignore query_params), with regex support.

        Args:
            other: Another _NormalizedUrlValues instance to compare against
            render_url_fct: Optional function to render template placeholders (e.g., __GITLAB__ -> http://localhost:8023)

        Returns:
            True if base paths match (using regex if is_regex=True)

        Note:
            - Symmetric: works from either side (regex on left or right)
            - Rendering happens at comparison time for regex patterns and their target URLs
            - Used by NetworkEventEvaluator for filtering events by URL
        """
        if not isinstance(other, _NormalizedUrlValues):
            return False

        # Helper to render a URL if render_url_fct is provided
        def render_if_needed(url: str) -> str:
            if render_url_fct and url.startswith("__"):
                return render_url_fct(url)
            return url

        # TODO: Refactor to avoid code duplication below
        # Try matching from both directions for symmetry
        # Case 1: self is regex pattern, other is literal
        if self.is_regex:
            try:
                # Render pattern (may contain templates like ^__GITLAB__/...)
                # Extract content between ^ and $, render it, then add anchors back
                pattern = self.base_url
                if is_regexp(pattern):
                    pattern_content = pattern[1:-1]
                    rendered_pattern_content = render_if_needed(pattern_content)
                    rendered_pattern = f"^{rendered_pattern_content}$"
                else:
                    rendered_pattern = render_if_needed(pattern)

                # Render the other URL for comparison
                rendered_other = render_if_needed(other.base_url)

                if re.match(rendered_pattern, rendered_other):
                    return True
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{self.base_url}': {e}") from e

        # Case 2: other is regex pattern, self is literal (symmetric)
        if other.is_regex:
            try:
                # Render pattern
                pattern = other.base_url
                if is_regexp(pattern):
                    pattern_content = pattern[1:-1]
                    rendered_pattern_content = render_if_needed(pattern_content)
                    rendered_pattern = f"^{rendered_pattern_content}$"
                else:
                    rendered_pattern = render_if_needed(pattern)

                # Render self for comparison
                rendered_self = render_if_needed(self.base_url)

                if re.match(rendered_pattern, rendered_self):
                    return True
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{other.base_url}': {e}") from e

        # Case 3: both are literals - exact match (no rendering needed, compare as-is)
        if not self.is_regex and not other.is_regex:
            return self.base_url.lower().rstrip("/") == other.base_url.lower().rstrip("/")

        return False

    def __eq__(self, other: Any) -> bool:
        """Compare full URL including base_url and query_params, with regex support.

        Args:
            other: Another _NormalizedUrlValues instance to compare against

        Returns:
            True if both base_url and query_params match

        Note:
            - Symmetric: works from either side (regex on left or right)
            - URLs must be already rendered before comparison (no render_url_fct parameter)
            - This method is NOT used by URL.__eq__() which needs to pass render_url_fct
            - Used for direct _NormalizedUrlValues comparisons only
        """
        if not isinstance(other, _NormalizedUrlValues):
            return False

        # First check if base paths match (with regex support, but no rendering)
        if not self.matches_base_path(other):
            return False

        # Then check query params with regex and optional param support
        return self._compare_query_params(other)

    def _compare_query_params(self, other: "_NormalizedUrlValues") -> bool:
        """Compare query params, supporting regex and treating missing/None/empty as equivalent.

        Args:
            other: Another _NormalizedUrlValues instance to compare against

        Returns:
            True if all query params match (with regex support)

        Note:
            - Regex patterns (^...$) in expected values enable flexible matching
            - Missing params, None values, and empty strings are all treated as ""
            - Example: "^(opened|)$" matches both "opened" and "" (missing/None/empty)
        """
        # Get all param keys from both URLs
        all_keys = set(self.query_params.keys()) | set(other.query_params.keys())

        for key in all_keys:
            # Get values (empty tuple if missing)
            self_values = self.query_params.get(key, ())
            other_values = other.query_params.get(key, ())

            # Normalize to string: None or empty tuple -> "", else take first value
            self_val = self._normalize_query_value(self_values)
            other_val = self._normalize_query_value(other_values)

            # Check if self_val is a regex pattern
            # For NormalizedType instances, use is_regexp property
            # For strings, use is_regexp utility
            is_regex = False
            if isinstance(self_val, NormalizedType):
                is_regex = self_val.is_regexp
            elif isinstance(self_val, str):
                is_regex = is_regexp(self_val)
            # For other types (e.g., empty string ""), is_regex remains False

            if is_regex:
                # Regex comparison - convert both to strings for comparison
                try:
                    pattern_str = str(self_val)
                    other_str = str(other_val)
                    if not re.match(pattern_str, other_str):
                        return False
                except re.error as e:
                    raise ValueError(f"Invalid regex pattern in query param '{key}': '{self_val}': {e}") from e
            else:
                # Exact match (treating None and "" as equivalent)
                if not self._query_values_equal(self_val, other_val):
                    return False

        return True

    def _normalize_query_value(self, values: tuple[str | None, ...]) -> str:
        """Normalize query param value tuple to comparable string.

        Args:
            values: Tuple of query param values (may be empty, contain None, or strings)

        Returns:
            Normalized string value for comparison

        Note:
            - Missing param (empty tuple): ""
            - None value: ""
            - Empty string: ""
            - Normal value: the value itself (first item in tuple)
        """
        if not values:
            return ""
        val = values[0]  # Take first value (multi-value params use first)
        return "" if val is None else val

    def _query_values_equal(self, val1: str, val2: str) -> bool:
        """Check if two query param values are equal, treating None/"" as equivalent.

        Args:
            val1: First value to compare
            val2: Second value to compare

        Returns:
            True if values are equal (with None == "" semantics)
        """
        # Treat None and empty string as equivalent
        normalized1 = "" if val1 is None or val1 == "" else val1
        normalized2 = "" if val2 is None or val2 == "" else val2
        return normalized1 == normalized2


class URL(NormalizedType[_NormalizedUrlValues]):
    """URL with query parameter handling.

    Normalized to dict with scheme, netloc, path, query, fragment.

    Features:
    - Parse URL components using urllib.parse
    - Handle base64 encoded query parameters in path
    - Filter ignored query parameters
    - Normalize query parameter ordering
    - Case-insensitive scheme/netloc
    """

    def __init__(
        self,
        raw: Any,
        query_params: QueryParams | None = None,
        decode_base64_query: bool = False,
        url_map: dict[str, tuple[str, ...]] | None = None,
        ignored_query_parameters: tuple[str, ...] | None = None,
        ignored_query_parameters_patterns: tuple[str, ...] | None = None,
        render_url_fct=None,
        derender_url_fct=None,
        normalize_query_params_fct=None,
        **kwargs,
    ):
        """Initialize with optional metadata for URL comparison.

        Args:
            raw: Raw URL value
            query_params: Optional pre-parsed query parameters (replaces URL's query string if provided)
            decode_base64_query: bool - decode base64 in path
            url_map: dict mapping site templates to actual URLs
            ignored_query_parameters: tuple of query parameter names to ignore (literal matching)
            ignored_query_parameters_patterns: tuple of regex patterns for query parameter names to ignore
            **kwargs: Additional parameters (ignored, for compatibility)
        """
        self._query_params = query_params
        self._decode_base64_query = decode_base64_query
        self._ignored_query_parameters = set(ignored_query_parameters or ())
        self._ignored_query_parameters_patterns = ignored_query_parameters_patterns or ()
        self.render_url_fct = render_url_fct or (lambda x: x)
        self.derender_url_fct = derender_url_fct or (lambda x: x)
        self.normalize_query_params_fct = normalize_query_params_fct or (lambda x: x)
        # Pass derender_url_fct to parent so it doesn't get overwritten
        super().__init__(raw, derender_url_fct=self.derender_url_fct, **kwargs)

    def compare_path(self, other: Self | str) -> bool:
        """Compare URL base paths only (ignore query params). Auto-detects regex patterns via ^$ anchors.

        Args:
            other: URL instance (actual URL from network) or string to compare against

        Returns:
            True if any of self's alternatives match any of other's base paths

        Note:
            This method delegates to _NormalizedUrlValues.matches_base_path() for the actual comparison.
            Query parameters are ignored - only base URLs are compared.
            URLs are expected to be already rendered when passed to this method.
            Rendering happens at comparison time in matches_base_path().
        """
        assert isinstance(other, (type(self), str)), "Can only compare with another URL instance or raw URL string."

        # Get _NormalizedUrlValues from other (no rendering - URLs should already be in correct form)
        if isinstance(other, type(self)):
            # Other is a URL instance - use its alternatives directly
            other_alternatives = list(other.alternatives)
        else:
            # Other is a string - create a temporary _NormalizedUrlValues
            assert isinstance(other, str)
            other_alternatives = [_NormalizedUrlValues(base_url=other.rstrip("/"), query_params=MappingProxyType({}))]

        # Check if ANY of self's alternatives match ANY of other's alternatives
        # Pass render_url_fct so templates in regex patterns get rendered during comparison
        for self_alt in self.alternatives:
            for other_alt in other_alternatives:
                if self_alt.matches_base_path(other_alt, render_url_fct=self.render_url_fct):
                    return True

        return False

    def __eq__(self, other: Any) -> bool:
        """Support equality against other URL instances or raw URL strings.

        For URL instances: Compares both base_url (with regex support) and query_params.
        Passes render_url_fct to ensure templates in regex patterns are rendered.

        For strings: Compares string representation of alternatives (no regex support for strings).
        """
        if isinstance(other, URL):
            # Check if ANY of self's alternatives match ANY of other's alternatives
            # Use matches_base_path with render_url_fct for regex support, then check query params
            for self_alt in self.alternatives:
                for other_alt in other.alternatives:
                    # Check base path match (with regex and template rendering support) and query params
                    if self_alt.matches_base_path(
                        other_alt, render_url_fct=self.render_url_fct
                    ) and self_alt._compare_query_params(other_alt):
                        return True
            return False

        if isinstance(other, str):
            # Unparse each alternative to full URL string and check if any matches
            # No regex support for raw string comparison (strings are always literals)
            return any(str(alt) == other for alt in self.alternatives)

        return False

    def __hash__(self) -> int:
        """Align hash with string representation for cross-type equality consistency."""
        return hash(str(self.normalized))

    def _is_ssh_url(self, url: str) -> bool:
        """Check if URL uses SSH scheme or git@host:path format.

        Args:
            url: URL string to check

        Returns:
            True if URL is SSH format (ssh:// or git@host:path), False otherwise
        """
        # Check full SSH format: ssh://...
        if url.lower().startswith("ssh://"):
            return True

        # Check short SCP-like format: git@host:path
        # Must have git@ prefix and colon (indicating host:path)
        # Ensure it's not a URL scheme (no :// after the colon)
        # Use case-insensitive check for git@ prefix
        return bool(url.lower().startswith("git@") and ":" in url and "://" not in url)

    def _parse_git_scp_format(self, url: str) -> tuple[str, str, str]:
        """Parse git@ SCP-like format into components.

        Args:
            url: SCP-like URL (e.g., "git@localhost:path/to/repo.git")

        Returns:
            tuple of (user, host, path)

        Raises:
            ValueError: If URL format is invalid
        """
        if "@" not in url or ":" not in url:
            raise ValueError(f"Invalid SCP-like URL format: {url}")

        # Split on @ to get user and host:path
        user, host_path = url.split("@", 1)

        # Split host:path on first : to get host and path
        # The : should exist since we validated it above
        if ":" not in host_path:
            raise ValueError(f"Invalid SCP-like URL format (missing colon after @): {url}")
        colon_idx = host_path.index(":")
        host = host_path[:colon_idx]
        path = host_path[colon_idx + 1 :]

        # Ensure path starts with / for consistency with ssh:// format
        if not path.startswith("/"):
            path = "/" + path

        return user, host, path

    def _normalize_string(self, s: str) -> str:
        """Override to skip base class string normalization for URLs.

        URLs need their original case and structure preserved for proper parsing.
        Only strip whitespace.
        """
        return s.strip()

    def _type_normalize(self, value: str) -> _NormalizedUrlValues:
        """Parse and normalize URL.

        Args:
            value: URL string to parse

        Returns:
            Normalized URL values with base_url and query_params

        Raises:
            ValueError: If URL is empty or invalid
        """
        if not value:
            raise ValueError("Empty URL value")

        # Auto-detect regex pattern BEFORE any processing
        is_regex = is_regexp(value)
        if is_regex:
            # For regex patterns, store as-is with template placeholders
            # Rendering will happen at comparison time in matches_base_path()
            # E.g., "^__GITLAB__/projects/\d+$" is stored with __GITLAB__ template
            query_params = {} if self._query_params is None else self._normalize_query_params(self._query_params)
            return _NormalizedUrlValues(
                base_url=value.rstrip("/"),
                query_params=MappingProxyType(query_params),
                is_regex=True,
            )

        value = value.rstrip("/")

        # Replace template placeholders with actual URLs
        if value.startswith("__"):
            value = self.render_url_fct(value)

        # Handle SSH URLs (early return with minimal normalization)
        if self._is_ssh_url(value):
            return self._normalize_ssh_url(value)

        # Normalize HTTP(S) URL components
        scheme, netloc, path, fragment = self._normalize_http_url_components(value)

        # Need parsed URL for query extraction
        normalized_url = url_normalize(value)
        if normalized_url is None:
            raise ValueError(f"Invalid URL: {value!r}")
        parsed = urlparse(self.derender_url_fct(normalized_url))

        # Extract and normalize query parameters
        query_params, path = self._extract_query_params(parsed, path)
        query_params = self._normalize_query_params(query_params)

        # Build final base URL
        base_url = self._build_base_url(scheme, netloc, path, fragment)

        return _NormalizedUrlValues(
            base_url=base_url,
            query_params=query_params,
        )

    def _normalize_ssh_url(self, value: str) -> _NormalizedUrlValues:
        """Normalize SSH URL to short format with __SSH_HOST__ template. Supports both full and short formats.

        Args:
            value: SSH URL string to normalize (ssh://... or git@host:path)

        Returns:
            Normalized URL values for SSH URL in short format (git@__SSH_HOST__:path)

        Examples:
            ssh://git@localhost:2222/path/to/repo.git -> git@__SSH_HOST__:path/to/repo.git
            git@localhost:2222/path/to/repo.git -> git@__SSH_HOST__:path/to/repo.git
            git@somehost:3333/path -> git@__SSH_HOST__:path
            GIT@HOST:PATH/REPO.GIT -> git@__SSH_HOST__:path/repo.git  (case normalization)
        """
        # Extract user and path from either format
        if value.lower().startswith("ssh://"):
            # Parse full format: ssh://git@host:port/path
            parsed = urlparse(value)
            if "@" in parsed.netloc:
                user = parsed.netloc.split("@")[0].lower()  # Normalize user to lowercase
            else:
                user = "git"  # default
            path = parsed.path.lstrip("/").lower()  # Normalize path to lowercase
        else:
            # Parse short format: git@host:port/path or git@host:path
            user, host, path = self._parse_git_scp_format(value)
            path = path.lstrip("/").lower()  # Normalize path to lowercase
            user = user.lower()  # Normalize user to lowercase

        # Build short format with __SSH_HOST__ template (strip all hosts and ports)
        base_url = f"{user}@__SSH_HOST__:{path}"

        return _NormalizedUrlValues(
            base_url=base_url,
            query_params=MappingProxyType({}),
        )

    def _normalize_http_url_components(self, value: str) -> tuple[str, str, str, str]:
        """Normalize HTTP(S) URL components.

        Args:
            value: URL string to normalize

        Returns:
            Tuple of (scheme, netloc, path, fragment) with normalization applied

        Raises:
            ValueError: If URL is invalid
        """
        # Standard HTTP(S) URL normalization
        normalized_url = url_normalize(value)
        if normalized_url is None:
            raise ValueError(f"Invalid URL: {value!r}")

        normalized_url = self.derender_url_fct(normalized_url)

        # Parse URL
        parsed = urlparse(normalized_url)

        # Normalize scheme and netloc to lowercase (case-insensitive per RFC 3986)
        scheme = parsed.scheme.lower() if parsed.scheme else ""
        netloc = parsed.netloc.lower() if parsed.netloc else ""
        path = str(parsed.path) or ""
        # Preserve semicolons in path by concatenating params back (modern interpretation)
        if parsed.params:
            path = f"{path};{parsed.params}"
        fragment = parsed.fragment or ""

        # Drop default ports from netloc for canonical comparison
        if netloc:
            try:
                default_http = scheme == "http" and parsed.port == 80
                default_https = scheme == "https" and parsed.port == 443
            except ValueError:
                default_http = default_https = False

            if default_http or default_https:
                netloc = parsed.hostname.lower() if parsed.hostname else netloc

        return scheme, netloc, path, fragment

    def _extract_query_params(self, parsed: Any, path: str) -> tuple[QueryParams, str]:
        """Extract query parameters from URL.

        Args:
            parsed: Parsed URL result from urlparse
            path: URL path (may be modified if base64 query extraction is enabled)

        Returns:
            Tuple of (query_params, modified_path)
        """
        if self._query_params is not None:
            # Use provided query params (already in QueryParams format)
            return self._query_params, path

        # Collect all query string sources
        query_parts = []

        # Handle base64 encoded query parameters in path
        if self._decode_base64_query:
            path, base64_queries = extract_base64_query(path)
            if base64_queries:
                query_parts.extend(base64_queries)

        # Add regular query string from URL
        if parsed.query:
            query_parts.append(parsed.query.strip())

        # Merge and normalize all query strings
        merged_query_string = "&".join(query_parts)
        query_params = normalize_query(merged_query_string)

        return query_params, path

    def _normalize_query_params(self, query_params: QueryParams) -> QueryParams:
        """Normalize query parameters.

        Args:
            query_params: Query parameters to normalize

        Returns:
            Normalized query parameters with filtering and value normalization applied
        """
        # Filter ignored parameters (both literal and pattern matches)
        if self._ignored_query_parameters or self._ignored_query_parameters_patterns:
            query_params = MappingProxyType({k: v for k, v in query_params.items() if not self._should_ignore_param(k)})

        # Normalize query parameter values (lowercase, strip whitespace, sort)
        if query_params:
            normalized_query = {}
            for key, values in query_params.items():
                normalized_values = tuple(s.lower().strip() if isinstance(s, str) else s for s in values)
                normalized_query[key] = tuple(sorted(normalized_values))
            query_params = MappingProxyType(normalized_query)

        # Apply custom normalization function and ensure result is MappingProxyType
        query_params = self.normalize_query_params_fct(query_params)
        if not isinstance(query_params, MappingProxyType):
            query_params = MappingProxyType(query_params or {})

        return query_params

    def _build_base_url(self, scheme: str, netloc: str, path: str, fragment: str) -> str:
        """Build base URL without query parameters.

        Args:
            scheme: URL scheme (e.g., 'http', 'https')
            netloc: Network location (e.g., 'example.com:8080')
            path: URL path
            fragment: URL fragment

        Returns:
            Base URL string without query parameters
        """
        return urlunparse(
            (
                str(scheme),
                str(netloc),
                str(path),
                "",  # params not used
                "",  # no query string
                str(fragment) if fragment else "",
            )
        )

    def _should_ignore_param(self, param_name: str) -> bool:
        """Check if a query parameter should be ignored.

        Args:
            param_name: Name of the query parameter

        Returns:
            True if parameter should be ignored (literal match or pattern match), False otherwise
        """
        # Check literal matches
        if param_name in self._ignored_query_parameters:
            return True

        # Check regex pattern matches
        if self._ignored_query_parameters_patterns:
            for pattern in self._ignored_query_parameters_patterns:
                try:
                    if re.search(pattern, param_name, re.IGNORECASE):
                        return True
                except re.error:
                    # Skip invalid patterns silently (could log warning if logger available)
                    continue

        return False
