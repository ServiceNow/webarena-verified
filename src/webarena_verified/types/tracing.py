from pathlib import Path
from types import MappingProxyType
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, field_serializer

from webarena_verified.core.utils.network_event_utils import (
    load_har_trace,
    load_playwright_trace,
    load_trace_from_content,
    parse_har_content,
)


class NetworkEvent(BaseModel):
    data: MappingProxyType

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    @property
    def url(self) -> str:
        return self.data["request"]["url"]

    @property
    def url_path(self) -> str:
        """Get the path component of the URL (without query parameters).

        Returns:
            str: URL path (e.g., '/path/to/resource')
        """
        from urllib.parse import urlparse

        parsed = urlparse(self.url)
        return parsed.path

    @property
    def referer(self) -> str | None:
        for header in self.data["request"]["headers"]:
            if header["name"].lower() == "referer":
                return header["value"]
        return None

    @property
    def http_method(self) -> str:
        return self.data["request"]["method"]

    @property
    def post_data(self) -> dict[str, Any] | None:
        """Get POST data parsed based on content type.

        Returns parsed POST data from request.postData:
        - application/x-www-form-urlencoded: dict with form parameters (first value only)
        - application/json: parsed JSON object (if it's a dict)
        - multipart/form-data: dict with form fields extracted from multipart boundaries
        - None: if postData not present, or unsupported mimeType, or JSON is not an object

        Returns:
            dict[str, Any] | None: Parsed POST data or None
        """
        post_data_obj = self.data["request"].get("postData")
        return parse_har_content(post_data_obj) if post_data_obj else None

    @property
    def response_content(self):
        """Get response content parsed based on content type.

        Returns:
            dict[str, Any] | None: Parsed response content or None
        """
        content = self.data["response"].get("content", None)
        return parse_har_content(content) if content else None

    @property
    def request_status(self) -> int:
        return self.data["response"]["status"]

    @property
    def redirect_url(self) -> str | None:
        if self.is_redirect:
            return self.data["response"]["redirectURL"]
        return None

    @property
    def is_redirect(self) -> bool:
        return self.request_status in range(300, 400) and self.data["response"]["redirectURL"].strip() != ""

    @property
    def is_request_success(self) -> bool:
        if self.request_status in range(200, 300):
            return True

        # Handle redirects
        return self.is_redirect

    @property
    def request_headers(self) -> dict[str, str]:
        """Get request headers as a case-insensitive map.

        Returns:
            dict[str, str]: Request headers with lowercased names
        """
        headers = {}
        for header in self.data["request"]["headers"]:
            headers[header["name"].lower()] = header["value"].lower()
        return headers

    @property
    def response_headers(self) -> dict[str, str]:
        """Get response headers as a case-insensitive map.

        Returns:
            dict[str, str]: Response headers with lowercased names
        """
        headers = {}
        for header in self.data["response"].get("headers", []):
            headers[header["name"].lower()] = header["value"].lower()
        return headers

    @property
    def response_cookies(self) -> dict[str, str]:
        """Get response cookies as a dict of name->value.

        Extracts from response.cookies array in HAR format.
        Values are URL-decoded for easier pattern matching.

        Returns:
            dict[str, str]: Cookie name to decoded value mapping
        """
        import urllib.parse

        cookies = {}
        for cookie in self.data["response"].get("cookies", []):
            name = cookie["name"]
            value = cookie.get("value", "")
            # URL decode the value for pattern matching
            decoded_value = urllib.parse.unquote(value)
            cookies[name] = decoded_value
        return cookies

    @property
    def is_evaluation_event(self) -> bool:
        return not self.url_path.endswith(
            (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".woff2", ".ttf", ".ico", ".webp")
        )

    @property
    def is_navigation_event(self) -> bool:
        """Check if this is a navigation event.

        Returns:
            bool: True if this is a navigation event
        """
        if self.http_method != "GET":
            return False

        headers = self.request_headers
        if "sec-fetch-user" in headers:
            return (
                headers.get("sec-fetch-dest") == "document"
                and headers.get("sec-fetch-mode") == "navigate"
                and headers.get("sec-fetch-user") == "?1"
                and "text/html" in headers.get("accept", "")
            )

        return headers.get("accept", "").startswith("text/html")

    @field_serializer("data")
    def serialize_data(self, value: MappingProxyType) -> dict:
        return dict(value)

    def __str__(self):
        return f"<NetworkEvent(method={self.http_method}, url={self.url}, status={self.request_status} )>"

    def __repr__(self):
        return self.__str__()


class NetworkTrace(BaseModel):
    is_playwright: bool
    src_file: Path
    events: tuple[NetworkEvent, ...]

    @property
    def evaluation_events(self) -> tuple[NetworkEvent, ...]:
        """Get events relevant for evaluation.

        Filters out static assets (CSS, JS, images, fonts) and returns only
        events that are relevant for validation (navigation and mutation events).

        Returns:
            Tuple of NetworkEvent objects excluding static asset requests
        """
        return tuple([event for event in self.events if event.is_evaluation_event])

    @classmethod
    def from_playwright_trace(cls, trace_path: Path) -> Self:
        events = load_playwright_trace(trace_path)
        return cls.model_construct(is_playwright=True, src_file=trace_path, events=events)

    @classmethod
    def from_har(cls, har_path: Path) -> Self:
        """
        Create NetworkTrace from HAR (HTTP Archive) file.

        HAR format: {"log": {"entries": [{"request": {...}, "response": {...}}, ...]}}

        Args:
            har_path: Path to HAR file (.har or .json)

        Returns:
            NetworkTrace instance with events from HAR file
        """
        events = load_har_trace(har_path)
        return cls.model_construct(is_playwright=False, src_file=har_path, events=events)

    @classmethod
    def from_content(cls, content: list[dict[str, Any]] | Path) -> Self:
        """
        Create NetworkTrace from either a file path or raw content.
        Autodetects the input type and delegates to the appropriate parser.

        Supports:
        - Path: Playwright trace (.zip or directory) or HAR file (.har/.json)
        - List: Playwright trace events or HAR entries

        Args:
            content: Either a Path to a trace file, or a list of trace event dictionaries

        Returns:
            NetworkTrace instance
        """
        if isinstance(content, Path):
            # Auto-detect format based on file extension
            if content.suffix in [".har", ".json"]:
                # Could be HAR or Playwright - try HAR first
                try:
                    return cls.from_har(content)
                except (ValueError, KeyError):
                    # Not HAR, try Playwright
                    return cls.from_playwright_trace(content)
            else:
                # .zip or directory - assume Playwright format
                return cls.from_playwright_trace(content)

        # Handle list of event dictionaries
        is_playwright, events = load_trace_from_content(content)
        return cls.model_construct(is_playwright=is_playwright, src_file=Path("<from_content>"), events=events)
