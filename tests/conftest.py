"""Pytest configuration for all tests."""

import json
import shutil
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from webarena_verified import WebArenaVerified
from webarena_verified.api import WebArenaVerifiedDataReader, WebArenaVerifiedEvaluator
from webarena_verified.core.utils.immutable_obj_helper import deserialize_to_immutable, serialize_to_mutable
from webarena_verified.types.config import EnvironmentConfig, WebArenaVerifiedConfig
from webarena_verified.types.task import WebArenaSite


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "docker: marks tests that require Docker")


@pytest.fixture(scope="session")
def docker():
    """Check that docker is available and return the CLI name."""
    docker_path = shutil.which("docker")
    if docker_path is None:
        raise RuntimeError("'docker' is missing or not available in PATH.")
    return "docker"


def pytest_addoption(parser):
    """Add custom CLI options."""
    parser.addoption(
        "--webarena-verified-docker-img",
        action="store",
        default="am1n3e/webarena-verified:latest",
        help="Docker image to test (default: am1n3e/webarena-verified:latest)",
    )
    parser.addoption(
        "--hf-dataset-ref",
        action="store",
        default="AmineHA/WebArena-Verified",
        help="HF dataset reference (repo id or local path) for HF dataset tests",
    )


@pytest.fixture(scope="session")
def project_root(request) -> Path:
    return Path(request.config.rootpath)


@pytest.fixture(scope="session")
def test_assets_dir(project_root: Path) -> Path:
    """Path to test assets directory.

    Args:
        project_root: Project root fixture

    Returns:
        Path to tests/assets/ directory containing test fixtures like HAR files,
        Playwright traces, and other test data files
    """
    return project_root / "tests" / "assets"


@pytest.fixture(scope="session")
def main_config(project_root: Path) -> WebArenaVerifiedConfig:
    """Create WebArenaVerifiedConfig for integration tests.

    Returns:
        WebArenaVerifiedConfig configured with the dataset file
    """
    # Path to dataset
    dataset_path = project_root / "assets" / "dataset" / "webarena-verified.json"

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    # Create config with environments
    return WebArenaVerifiedConfig(
        test_data_file=dataset_path,
        environments={
            WebArenaSite.SHOPPING: EnvironmentConfig(
                urls=["http://localhost:7780"],
                active_url_idx=0,
            ),
            WebArenaSite.SHOPPING_ADMIN: EnvironmentConfig(
                urls=["http://localhost:7780/admin"],
                active_url_idx=0,
            ),
            WebArenaSite.REDDIT: EnvironmentConfig(
                urls=["http://localhost:9999"],
                active_url_idx=0,
            ),
            WebArenaSite.GITLAB: EnvironmentConfig(
                urls=["http://localhost:8023"],
                active_url_idx=0,
            ),
            WebArenaSite.WIKIPEDIA: EnvironmentConfig(
                urls=["http://localhost:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"],
                active_url_idx=0,
            ),
            WebArenaSite.MAP: EnvironmentConfig(
                urls=["http://localhost:3000"],
                active_url_idx=0,
            ),
        },
    )


@pytest.fixture(scope="session")
def data_reader(main_config: WebArenaVerifiedConfig) -> WebArenaVerifiedDataReader:
    """Create WebArenaVerifiedDataReader instance.

    Args:
        main_config: Config fixture

    Returns:
        WebArenaVerifiedDataReader instance
    """
    return WebArenaVerifiedDataReader(main_config)


@pytest.fixture(scope="session")
def evaluator(
    main_config: WebArenaVerifiedConfig, data_reader: WebArenaVerifiedDataReader
) -> WebArenaVerifiedEvaluator:
    """Create WebArenaVerifiedEvaluator instance.

    Args:
        main_config: Config fixture
        data_reader: Data reader fixture

    Returns:
        WebArenaVerifiedEvaluator instance
    """
    return WebArenaVerifiedEvaluator(config=main_config, reader=data_reader)


@pytest.fixture(scope="session")
def wa(main_config) -> WebArenaVerified:
    """Create a WebArenaVerified interface instance for tests."""
    return WebArenaVerified(config=main_config)


@pytest.fixture(scope="session")
def har_file_example(test_assets_dir: Path) -> Path:
    template_path = test_assets_dir / "network.har"
    if not template_path.exists():
        raise FileNotFoundError(f"Trace template not found: {template_path}")
    return template_path


@pytest.fixture(scope="session")
def har_content(test_assets_dir: Path) -> MappingProxyType[str, Any]:
    template_path = test_assets_dir / "network.har"
    if not template_path.exists():
        raise FileNotFoundError(f"Trace template not found: {template_path}")
    content = json.loads(template_path.read_text())
    return MappingProxyType(content)


@pytest.fixture
def create_har_content_mock(har_content):
    """Create a function that returns a copy of the HAR content fixture.

    Args:
        har_content: HAR content fixture

    Returns:
        Function that returns a copy of the HAR content
    """

    def _create_har_content_mock(*, mock_entries: list[tuple[int, MappingProxyType]]) -> MappingProxyType[str, Any]:
        content = serialize_to_mutable(har_content)
        for idx, entry in mock_entries:
            _entry = deserialize_to_immutable(entry)
            content["log"]["entries"][idx] = _entry

        # # For debugging
        # Path(".current_test_har.json").write_text(json.dumps(serialize_to_mutable(content), indent=2))

        return deserialize_to_immutable(content)

    return _create_har_content_mock


@pytest.fixture
def har_entry_template(test_assets_dir: Path) -> MappingProxyType[str, Any]:
    template_path = test_assets_dir / "har_entry_template.json"
    if not template_path.exists():
        raise FileNotFoundError(f"HAR entry template not found: {template_path}")
    content = json.loads(template_path.read_text())
    return MappingProxyType(content)


@pytest.fixture
def create_navigation_network_event(har_entry_template):  # noqa: C901
    """Create a function that generates a navigation network event.

    Returns:
        Function that creates a navigation network event dict
    """

    def _create_navigation_network_event(
        *,
        url: str,
        query_params: dict[str, tuple[str, ...]] | None = None,
        headers: dict[str, str] | None = None,
        response_status: int = 200,
        response_text: str = "OK",
        http_method: str = "GET",
        post_data: dict[str, Any] | None = None,
    ) -> MappingProxyType[str, Any]:
        event = dict(har_entry_template)
        event["request"]["method"] = http_method

        # Build URL with query params if provided
        if query_params is not None:
            # Build query string for URL
            query_string_parts = []
            query_entries = []
            for key, values in query_params.items():
                for value in values:
                    query_string_parts.append(f"{key}={value}")
                    query_entries.append({"name": key, "value": value})

            # Append query string to URL
            separator = "&" if "?" in url else "?"
            url_with_query = url + separator + "&".join(query_string_parts)
            event["request"]["url"] = url_with_query
            event["request"]["queryString"] = query_entries
        else:
            event["request"]["url"] = url

        # Headers - set defaults based on HTTP method
        if http_method == "GET":
            # Navigation-specific headers for GET requests
            _headers = {
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-user": "?1",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "x-requested-with": "XMLHttpRequest",
            }
        else:
            # Basic headers for non-GET requests (POST, etc.)
            _headers = {
                "accept": "application/json",
                "content-type": "application/json",
            }

        if headers is not None:
            # Merge custom headers (they override defaults)
            _headers.update(dict(headers))

        event["request"]["headers"] = [{"name": k, "value": v} for k, v in _headers.items()]

        # POST data
        if post_data is not None:
            import json

            # Convert MappingProxyType to dict if needed
            _post_data = dict(post_data) if hasattr(post_data, "__getitem__") else post_data

            # Convert JSONPath keys to nested structure
            # E.g., {"$.note.type": "val"} -> {"note": {"type": "val"}}
            def jsonpath_to_nested(flat_dict):
                result = {}
                for key, value in flat_dict.items():
                    # Remove leading $. if present
                    path = key.lstrip("$.")
                    # Skip if not a path
                    if "." not in path:
                        result[path] = value
                        continue

                    # Split by .
                    parts = path.split(".")

                    # Navigate/create nested structure
                    current = result
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]

                    # Set the value
                    current[parts[-1]] = value

                return result

            nested_post_data = jsonpath_to_nested(_post_data)

            event["request"]["postData"] = {
                "mimeType": "application/json",
                "text": json.dumps(nested_post_data),
            }

        # Response
        event["response"]["status"] = response_status
        event["response"]["content"]["text"] = response_text

        return deserialize_to_immutable(event)

    return _create_navigation_network_event
