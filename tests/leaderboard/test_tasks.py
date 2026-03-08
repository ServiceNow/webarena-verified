from leaderboard.scripts.tasks import _resolve_manifest_url


def test_resolve_manifest_url_prefers_override() -> None:
    resolved = _resolve_manifest_url(
        manifest_url_override="https://override.example/manifest.json",
        configured_manifest_url="https://configured.example/manifest.json",
    )
    assert resolved == "https://override.example/manifest.json"


def test_resolve_manifest_url_falls_back_to_configured_value() -> None:
    resolved = _resolve_manifest_url(
        manifest_url_override="",
        configured_manifest_url="https://configured.example/manifest.json",
    )
    assert resolved == "https://configured.example/manifest.json"


def test_resolve_manifest_url_uses_repo_default_when_unset() -> None:
    resolved = _resolve_manifest_url(
        manifest_url_override="",
        configured_manifest_url="",
    )
    assert resolved.endswith("leaderboard-submissions/leaderboard/latest.json")
