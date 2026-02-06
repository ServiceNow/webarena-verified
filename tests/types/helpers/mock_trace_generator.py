"""Mock network trace generator for integration tests.

This module generates mock Playwright network traces by using a real trace template
and replacing URLs with task-specific values.
"""

import json
import random
from copy import deepcopy
from functools import lru_cache
from http import HTTPStatus
from pathlib import Path
from typing import Any, TypedDict

from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.task import WebArenaSite, WebArenaVerifiedTask


class URLData(TypedDict):
    """URL metadata for generating navigation events."""

    url: str
    status_code: int
    referer: str | None


def _first_url_template(value: Any) -> str:
    """Extract a URL template string from supported structures."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and value:
        candidate = value[0]
        if isinstance(candidate, str):
            return candidate
    return str(value)


def _infer_site_from_url_template(url_template: str, task_sites: tuple[WebArenaSite | str, ...]) -> WebArenaSite:
    """Infer the site from a URL template by checking for site templates.

    Args:
        url_template: URL template that may contain site template (e.g., "__GITLAB__/api")
        task_sites: Sites associated with the task to check against (can be WebArenaSite enums or strings)

    Returns:
        The first site whose template matches the URL template

    Raises:
        ValueError: If no matching site found in task_sites
    """
    for site in task_sites:
        # Convert string to WebArenaSite enum if needed
        site_enum = WebArenaSite(site) if isinstance(site, str) else site

        if site_enum.url_name_template in url_template:
            return site_enum

    # If no match found, return first site as fallback (for plain URLs without templates)
    if task_sites:
        first_site = task_sites[0]
        return WebArenaSite(first_site) if isinstance(first_site, str) else first_site

    raise ValueError(f"Cannot infer site from URL template: {url_template}")


@lru_cache(maxsize=1)
def load_trace_template(assets_dir: Path) -> list[dict[str, Any]]:
    """Load the Playwright trace template from tests/assets.

    The template is a real trace from task 157 with navigation events removed.
    Cached to avoid re-reading on every test.

    Args:
        assets_dir: Path to test assets directory

    Returns:
        List of trace event dictionaries in Playwright format
    """
    template_path = assets_dir / "playwright-trace.network"

    if not template_path.exists():
        raise FileNotFoundError(f"Trace template not found: {template_path}")

    events = []
    for line in template_path.read_text().splitlines():
        if line.strip():
            events.append(json.loads(line))

    return events


@lru_cache(maxsize=1)
def load_navigation_event_template(assets_dir: Path) -> dict[str, Any]:
    """Load the navigation event template from tests/assets.

    The template is a single navigation event extracted from the original trace.
    Cached to avoid re-reading on every test.

    Args:
        assets_dir: Path to test assets directory

    Returns:
        A navigation event dictionary in Playwright format
    """
    template_path = assets_dir / "playwright-trace-nav-template.json"

    if not template_path.exists():
        raise FileNotFoundError(f"Navigation template not found: {template_path}")

    return json.loads(template_path.read_text())


def is_document_navigation_event(event: dict[str, Any]) -> bool:
    """Check if an event is a document navigation event.

    Document navigation events have:
    - type: resource-snapshot
    - request.headers contains Sec-Fetch-Dest: document
    - request.headers contains Sec-Fetch-Mode: navigate

    Args:
        event: Playwright trace event dictionary

    Returns:
        True if this is a document navigation event
    """
    if event.get("type") != "resource-snapshot":
        return False

    snapshot = event.get("snapshot", {})
    headers = snapshot.get("request", {}).get("headers", [])

    has_fetch_dest_document = False
    has_fetch_mode_navigate = False

    for header in headers:
        name = header.get("name", "").lower()
        value = header.get("value", "").lower()

        if name == "sec-fetch-dest" and value == "document":
            has_fetch_dest_document = True
        elif name == "sec-fetch-mode" and value == "navigate":
            has_fetch_mode_navigate = True

    return has_fetch_dest_document and has_fetch_mode_navigate


def extract_target_urls(
    task: WebArenaVerifiedTask, config: WebArenaVerifiedConfig, render: bool = True
) -> list[URLData]:
    """Extract target URLs with metadata from task evaluators.

    Note: NavigationURLEvaluatorCfg has been removed as it's unused in the dataset.
    This function now returns an empty list.

    Args:
        task: WebArenaVerified task
        config: WebArenaVerifiedConfig for rendering URL templates

    Returns:
        List of URLData with url, status_code, and referer. Empty if not a navigation task.
    """
    # NavigationURLEvaluatorCfg has been removed - no evaluators to check
    return []


def collect_task_urls(task: WebArenaVerifiedTask, config: WebArenaVerifiedConfig) -> list[URLData]:
    """Collect all URLs for a task (start URLs + target URLs).

    Args:
        task: WebArenaVerified task
        config: WebArenaVerifiedConfig for rendering URL templates

    Returns:
        List of URLData with url, status_code, and referer metadata
    """
    task_urls: list[URLData] = []

    # Add start URLs with default metadata
    for url_template in task.start_urls:
        template = _first_url_template(url_template)
        site = _infer_site_from_url_template(template, task.sites)
        rendered_url = config.render_url(template, sites=(site,))
        assert isinstance(rendered_url, str), "Expected string URL from render_url with string template"
        task_urls.append({"url": rendered_url, "status_code": 200, "referer": None})

    # Add target URLs for navigate tasks (with metadata from evaluator config)
    target_urls = extract_target_urls(task, config)
    task_urls.extend(target_urls)

    return task_urls


def update_referer_header(headers: list[dict[str, str]], referer: str) -> None:
    """Update or add Referer header in request headers.

    Args:
        headers: List of header dictionaries with 'name' and 'value' keys
        referer: Referer value to set
    """
    # Try to find and update existing Referer header
    for header in headers:
        if header.get("name", "").lower() == "referer":
            header["value"] = referer
            return

    # If not found, add new Referer header
    headers.append({"name": "Referer", "value": referer})


def create_navigation_event(nav_template: dict[str, Any], url_data: URLData) -> dict[str, Any]:
    """Create a navigation event from template and URL data.

    Args:
        nav_template: Navigation event template
        url_data: URL data with url, status_code, and referer

    Returns:
        Navigation event dictionary with updated URL, status, and referer
    """
    # Deep copy the navigation template
    nav_event = deepcopy(nav_template)

    # Set the URL
    nav_event["snapshot"]["request"]["url"] = url_data["url"]

    # Set the status code and status text
    if "response" in nav_event["snapshot"]:
        nav_event["snapshot"]["response"]["status"] = url_data["status_code"]
        try:
            nav_event["snapshot"]["response"]["statusText"] = HTTPStatus(url_data["status_code"]).phrase
        except ValueError:
            nav_event["snapshot"]["response"]["statusText"] = ""

        # Clear redirectURL if status is 200, otherwise keep it
        if url_data["status_code"] == 200:
            nav_event["snapshot"]["response"]["redirectURL"] = ""

    # Set referer if provided
    if url_data["referer"] is not None:
        headers = nav_event["snapshot"]["request"].get("headers", [])
        update_referer_header(headers, url_data["referer"])

    return nav_event


def inject_events_into_trace(
    template_events: list[dict[str, Any]], nav_events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Inject navigation events at random positions in the trace template.

    Args:
        template_events: Base trace events from template
        nav_events: Navigation events to inject

    Returns:
        Modified trace with navigation events injected at random positions
    """
    # If template is empty, just return navigation events
    if not template_events:
        return nav_events

    # Deep copy to avoid modifying the original
    modified_events = deepcopy(template_events)

    # Generate random positions for injecting navigation events
    positions = sorted([random.randint(0, len(modified_events)) for _ in range(len(nav_events))])

    # Inject navigation events at the generated positions
    # Insert in reverse order to maintain correct positions
    for i in reversed(range(len(nav_events))):
        modified_events.insert(positions[i], nav_events[i])

    return modified_events


def generate_mock_trace_for_task(
    task: WebArenaVerifiedTask, config: WebArenaVerifiedConfig, assets_dir: Path
) -> list[dict[str, Any]]:
    """Generate a mock Playwright trace for a task.

    Uses a real trace template and injects navigation events at random positions
    with task-specific URLs (start URLs and target URLs for navigate tasks).

    Args:
        task: WebArenaVerified task
        config: WebArenaVerifiedConfig for rendering URL templates
        assets_dir: Path to test assets directory

    Returns:
        List of trace event dictionaries in Playwright format
    """
    # Load templates
    template_events = load_trace_template(assets_dir)
    nav_template = load_navigation_event_template(assets_dir)

    # Validate templates
    assert len(template_events) > 0, "Template events must exist and contain at least 1 item"

    # Collect task-specific URLs (start URLs + target URLs)
    task_urls = collect_task_urls(task, config)
    assert task_urls, "No URLs extracted for task. At least start URLs should be present."

    # Create navigation events from URL data
    nav_events = [create_navigation_event(nav_template, url_data) for url_data in task_urls]

    # Inject navigation events into trace and return
    return inject_events_into_trace(template_events, nav_events)
