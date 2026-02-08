"""Shared HTTP helpers for leaderboard validators."""

from __future__ import annotations

import json
from typing import Any
from urllib import request


def http_get_json(url: str, token: str | None = None) -> dict[str, Any]:
    """Fetch a JSON payload from an HTTP endpoint."""
    req = request.Request(url)
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))
