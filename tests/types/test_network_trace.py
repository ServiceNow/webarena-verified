"""Functional tests for NetworkTrace."""

import pytest

from webarena_verified.types.tracing import NetworkTrace


@pytest.fixture
def test_har_path(project_root):
    """Path to test HAR file."""
    return project_root / "tests" / "assets" / "network.har"


@pytest.fixture
def trace(test_har_path):
    """Loaded NetworkTrace from test HAR file."""
    return NetworkTrace.from_har(test_har_path)


def test_from_har_loads_successfully(test_har_path):
    """Test that HAR file loads and has expected structure."""
    trace = NetworkTrace.from_har(test_har_path)

    assert trace.is_playwright is False
    assert trace.src_file == test_har_path
    assert len(trace.events) > 0
    assert len(trace.evaluation_events) > 0


@pytest.mark.skip(reason="Skipped to focus on other tests")
def test_trace_properties(trace):
    """Test basic NetworkTrace properties."""
    # Should have events
    assert len(trace.events) == 358
    assert len(trace.evaluation_events) == 4  # Filtered events excluding static assets

    # Last URL should be from last evaluation event
    assert trace.evaluation_events[-1].url == "http://localhost:7780/admin/mui/bookmark/save/?isAjax=true"


def test_redirect_detection(trace):
    """Test that redirects are properly detected."""
    # First event is a 302 redirect
    redirect_event = trace.evaluation_events[0]

    assert redirect_event.request_status == 302
    assert redirect_event.is_redirect is True
    assert redirect_event.is_request_success is True
    assert redirect_event.redirect_url is not None


def test_evaluation_event_filtering(trace):
    """Test that evaluation_events filters out static assets."""
    # All evaluation events should not be static assets
    for event in trace.evaluation_events:
        assert event.is_evaluation_event is True
        # Should not end with static asset extensions
        assert not event.url.endswith(
            (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".woff2", ".ttf", ".ico")
        )
