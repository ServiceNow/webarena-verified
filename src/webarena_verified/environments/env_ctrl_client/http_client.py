"""HTTP client for the environment control REST API.

This module provides a stdlib-only HTTP client for interacting with the
environment control server running inside Docker containers.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class HttpClient:
    """HTTP client for interacting with the environment control REST API.

    Args:
        base_url: Base URL of the server (e.g., "http://localhost:8080").
                  Defaults to http://localhost:8080.
        timeout: Request timeout in seconds. Defaults to 30.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        timeout: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the server.

        Args:
            method: HTTP method (GET or POST).
            endpoint: API endpoint (e.g., "/status").
            params: Optional query parameters.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            ConnectionError: If unable to connect to the server.
            RuntimeError: If the server returns an error response.
        """
        url = f"{self._base_url}{endpoint}"

        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"

        req = urllib.request.Request(url, method=method)
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                data = response.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode("utf-8")
                return json.loads(error_body)
            except Exception:
                raise RuntimeError(f"Server error: HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise ConnectionError(f"Cannot connect to server: {e.reason}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response: {e}") from e

    def init(self) -> dict[str, Any]:
        """Initialize the environment.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        return self._request("POST", "/init")

    def status(self) -> dict[str, Any]:
        """Get environment status.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        return self._request("GET", "/status")

    def start(self, wait: bool = False) -> dict[str, Any]:
        """Start the environment.

        Args:
            wait: If True, wait until environment is ready.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        params = {"wait": "1"} if wait else None
        return self._request("POST", "/start", params=params)

    def stop(self) -> dict[str, Any]:
        """Stop the environment.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        return self._request("POST", "/stop")

    def wait_until_ready(
        self,
        timeout: float = 60.0,
        interval: float = 1.0,
    ) -> dict[str, Any]:
        """Poll until the environment is ready or timeout is reached.

        Args:
            timeout: Maximum time to wait in seconds.
            interval: Time between polls in seconds.

        Returns:
            Dict with 'success', 'message', and 'details'.
        """
        start_time = time.time()
        last_result: dict[str, Any] = {
            "success": False,
            "message": "Timeout waiting for environment",
            "details": {},
        }

        while time.time() - start_time < timeout:
            try:
                result = self.status()
                if result.get("success"):
                    return result
                last_result = result
            except (ConnectionError, RuntimeError) as e:
                last_result = {
                    "success": False,
                    "message": str(e),
                    "details": {},
                }

            time.sleep(interval)

        elapsed = time.time() - start_time
        return {
            "success": False,
            "message": f"Timeout after {elapsed:.1f}s waiting for environment",
            "details": {
                "last_result": last_result,
                "timeout": timeout,
                "elapsed": elapsed,
            },
        }
