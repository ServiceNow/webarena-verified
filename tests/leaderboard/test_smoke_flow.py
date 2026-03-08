import hashlib
import json

import pytest

from leaderboard.scripts import smoke_flow


def _as_bytes(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_smoke_check_validates_manifest_and_assets(monkeypatch) -> None:
    full_payload = {"leaderboard": "full", "rows": [{"submission_id": 1}]}
    hard_payload = {"leaderboard": "hard", "rows": [{"submission_id": 2}]}

    full_bytes = _as_bytes(full_payload)
    hard_bytes = _as_bytes(hard_payload)
    manifest = {
        "generation_id": "gen-1",
        "full_file": "leaderboard_full.gen-1.json",
        "hard_file": "leaderboard_hard.gen-1.json",
        "full_sha256": hashlib.sha256(full_bytes).hexdigest(),
        "hard_sha256": hashlib.sha256(hard_bytes).hexdigest(),
    }

    fixtures = {
        "https://example.test/leaderboard/data/leaderboard_manifest.json": _as_bytes(manifest),
        "https://example.test/leaderboard/data/leaderboard_full.gen-1.json": full_bytes,
        "https://example.test/leaderboard/data/leaderboard_hard.gen-1.json": hard_bytes,
    }

    monkeypatch.setattr(smoke_flow, "_fetch_bytes", lambda url: fixtures[url])

    result = smoke_flow._run_leaderboard_smoke_check(
        leaderboard_base_url="https://example.test/leaderboard/data",
    )

    assert result["generation_id"] == "gen-1"
    assert result["full_file"] == "leaderboard_full.gen-1.json"
    assert result["hard_file"] == "leaderboard_hard.gen-1.json"


def test_smoke_check_fails_on_checksum_mismatch(monkeypatch) -> None:
    manifest = {
        "generation_id": "gen-1",
        "full_file": "leaderboard_full.gen-1.json",
        "hard_file": "leaderboard_hard.gen-1.json",
        "full_sha256": "0" * 64,
        "hard_sha256": "0" * 64,
    }
    full_payload = {"leaderboard": "full", "rows": []}
    hard_payload = {"leaderboard": "hard", "rows": []}

    fixtures = {
        "https://example.test/leaderboard/data/leaderboard_manifest.json": _as_bytes(manifest),
        "https://example.test/leaderboard/data/leaderboard_full.gen-1.json": _as_bytes(full_payload),
        "https://example.test/leaderboard/data/leaderboard_hard.gen-1.json": _as_bytes(hard_payload),
    }

    monkeypatch.setattr(smoke_flow, "_fetch_bytes", lambda url: fixtures[url])

    with pytest.raises(ValueError, match="checksum mismatch"):
        smoke_flow._run_leaderboard_smoke_check(leaderboard_base_url="https://example.test/leaderboard/data")
