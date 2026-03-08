from __future__ import annotations

import hashlib
import json
from urllib.request import urlopen

_DEFAULT_BASE_URL = "https://servicenow.github.io/webarena-verified/leaderboard/data"


def _fetch_bytes(url: str) -> bytes:
    with urlopen(url) as response:
        return response.read()


def _fetch_json_object(url: str) -> dict:
    payload = json.loads(_fetch_bytes(url).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {url}")
    return payload


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _require_string(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing or invalid '{key}' in manifest")
    return value


def _run_leaderboard_smoke_check(*, leaderboard_base_url: str) -> dict[str, str]:
    base_url = leaderboard_base_url.strip() or _DEFAULT_BASE_URL
    base_url = base_url.rstrip("/")

    manifest_url = f"{base_url}/leaderboard/latest.json"
    manifest = _fetch_json_object(manifest_url)

    generation_id = _require_string(manifest, "generation_id")
    full_file = _require_string(manifest, "full_file")
    hard_file = _require_string(manifest, "hard_file")
    full_sha = _require_string(manifest, "full_sha256")
    hard_sha = _require_string(manifest, "hard_sha256")

    full_bytes = _fetch_bytes(f"{base_url}/{full_file}")
    hard_bytes = _fetch_bytes(f"{base_url}/{hard_file}")

    if _sha256(full_bytes) != full_sha:
        raise ValueError("Full leaderboard file checksum mismatch")
    if _sha256(hard_bytes) != hard_sha:
        raise ValueError("Hard leaderboard file checksum mismatch")

    full_payload = json.loads(full_bytes.decode("utf-8"))
    hard_payload = json.loads(hard_bytes.decode("utf-8"))
    if full_payload.get("leaderboard") != "full" or not isinstance(full_payload.get("rows"), list):
        raise ValueError("Invalid full leaderboard payload")
    if hard_payload.get("leaderboard") != "hard" or not isinstance(hard_payload.get("rows"), list):
        raise ValueError("Invalid hard leaderboard payload")

    return {
        "base_url": base_url,
        "generation_id": generation_id,
        "full_file": full_file,
        "hard_file": hard_file,
    }
