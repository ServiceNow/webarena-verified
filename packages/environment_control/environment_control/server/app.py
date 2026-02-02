"""REST API server with web dashboard for environment control."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from .._internal.config import Config
from .._internal.logging import configure_logging
from ..ops import BaseOps, Result, get_ops_class

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8080
_DASHBOARD_TEMPLATE_PATH = Path(__file__).parent / "assets" / "dashboard.html"

# Cache the dashboard template at module load time
_DASHBOARD_TEMPLATE: Optional[str] = None


def _get_dashboard_template() -> str:
    """Get the dashboard HTML template (cached)."""
    global _DASHBOARD_TEMPLATE
    if _DASHBOARD_TEMPLATE is None:
        _DASHBOARD_TEMPLATE = _DASHBOARD_TEMPLATE_PATH.read_text()
    return _DASHBOARD_TEMPLATE


def _create_handler(ops: type[BaseOps], env_name: str, site_url: Optional[str] = None) -> type:  # noqa: C901
    """Create a request handler class with access to the ops class.

    Args:
        ops: The Ops class to use for operations.
        env_name: Name of the environment for display.
        site_url: URL of the actual site (for external link in dashboard).

    Returns:
        A BaseHTTPRequestHandler subclass.
    """

    class EnvCtrlHandler(BaseHTTPRequestHandler):
        """HTTP request handler for environment control API."""

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Override to use our logger instead of stderr."""
            logger.info("%s - %s", self.address_string(), format % args)

        def _send_json(
            self,
            data: dict[str, Any],
            status_code: int = 200,
        ) -> None:
            """Send a JSON response."""
            body = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str, status_code: int = 200) -> None:
            """Send an HTML response."""
            body = html.encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _get_query_params(self) -> dict[str, str]:
            """Parse query parameters from the URL."""
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            # Return first value for each param
            return {k: v[0] for k, v in params.items()}

        def _get_dashboard_html(self) -> str:
            """Generate the HTML dashboard."""
            ready = ops.get_health()

            status_class = "ready" if ready.success else "not-ready"
            status_text = "Ready" if ready.success else "Not Ready"
            ready_message = "All services healthy" if ready.success else "Services not ready"

            template = _get_dashboard_template()
            return template.format(
                env_name=env_name,
                site_url=site_url or "",
                status_class=status_class,
                status_text=status_text,
                ready_message=ready_message,
            )

        def do_GET(self) -> None:
            """Handle GET requests."""
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/":
                self._send_html(self._get_dashboard_html())
            elif path == "/status":
                result = ops.get_health()
                self._send_json(result.to_dict())
            else:
                self._send_json(
                    {"success": False, "error": "Not found"},
                    404,
                )

        def do_POST(self) -> None:
            """Handle POST requests."""
            parsed = urlparse(self.path)
            path = parsed.path
            params = self._get_query_params()
            wait = params.get("wait") == "1"

            result: Optional[Result] = None

            if path == "/init":
                result = ops.init()
            elif path == "/stop":
                result = ops.stop()
            elif path == "/start":
                result = ops.start(wait=wait)
            else:
                self._send_json(
                    {"success": False, "error": "Not found"},
                    404,
                )
                return

            status_code = 200 if result.success else 500
            self._send_json(result.to_dict(), status_code)

    return EnvCtrlHandler


def run_server(
    env_type: Optional[str] = None,
    port: Optional[int] = None,
    host: str = "0.0.0.0",
    site_url: Optional[str] = None,
) -> None:
    """Run the environment control server.

    Args:
        env_type: Environment type to control. Defaults to WA_ENV_CTRL_TYPE env var.
        port: Port to listen on. Defaults to WA_ENV_CTRL_PORT env var or 8877.
        host: Host to bind to. Defaults to 0.0.0.0.
        site_url: URL of the actual site. Defaults to WA_ENV_CTRL_EXTERNAL_SITE_URL env var.
    """
    configure_logging()

    config = Config.from_env()

    if port is None:
        port = config.port

    if site_url is None:
        site_url = config.site_url

    ops = get_ops_class(env_type)
    env_name = env_type or config.env_type or "unknown"
    handler = _create_handler(ops, env_name, site_url)

    server = HTTPServer((host, port), handler)
    logger.info("Starting server for '%s' environment on %s:%d", env_name, host, port)
    print(f"Environment control server running at http://{host}:{port}")
    print(f"Dashboard: http://{host}:{port}/")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        print("\nServer stopped")
    finally:
        server.server_close()
