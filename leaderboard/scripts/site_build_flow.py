from __future__ import annotations

_DEFAULT_MANIFEST_URL = (
    "https://raw.githubusercontent.com/ServiceNow/webarena-verified/leaderboard-submissions/leaderboard/latest.json"
)


def _resolve_manifest_url(*, manifest_url_override: str, configured_manifest_url: str) -> str:
    override = manifest_url_override.strip()
    if override:
        return override

    configured = configured_manifest_url.strip()
    if configured:
        return configured

    return _DEFAULT_MANIFEST_URL
