"""Leaderboard generation and atomic publish helpers for maintainer workflows."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from webarena_verified.types.leaderboard import (
    LeaderboardManifest,
    LeaderboardRow,
    LeaderboardTableFile,
    SubmissionRecord,
    SubmissionStatus,
)

LEADERBOARD_DATA_DIR = Path("leaderboard/data")
LEADERBOARD_MANIFEST_FILE = "leaderboard_manifest.json"

# Required fields for publishing a leaderboard row from a processed submission record.
_REQUIRED_ROW_FIELDS = [
    "name",
    "overall_score",
    "shopping_score",
    "reddit_score",
    "gitlab_score",
    "wikipedia_score",
    "map_score",
    "shopping_admin_score",
    "success_count",
    "failure_count",
    "error_count",
    "missing_count",
    "webarena_verified_version",
    "checksum",
]


def _utc_now_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_generation_id() -> str:
    return f"gen-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_unique_submission_ids(rows: list[dict], *, board_name: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        submission_id = str(row["submission_id"])
        if submission_id in seen:
            duplicates.add(submission_id)
        seen.add(submission_id)

    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise ValueError(f"duplicate submission_id(s) in {board_name}: {duplicate_list}")


def rank_rows(rows: list[dict], *, board_name: str = "leaderboard") -> list[dict]:
    """Return rows sorted and ranked by deterministic spec order."""
    _assert_unique_submission_ids(rows, board_name=board_name)
    sorted_rows = sorted(rows, key=lambda row: (-float(row["overall_score"]), str(row["submission_id"])))
    ranked_rows = []
    for index, row in enumerate(sorted_rows, start=1):
        ranked_rows.append({**row, "rank": index})
    return ranked_rows


def _write_table_file(
    *,
    output_dir: Path,
    filename: str,
    generation_id: str,
    generated_at_utc: str,
    leaderboard: str,
    rows: list[dict],
) -> Path:
    ranked_rows = rank_rows(rows, board_name=leaderboard)
    table = LeaderboardTableFile(
        schema_version="1.0",
        generation_id=generation_id,
        generated_at_utc=generated_at_utc,
        leaderboard=leaderboard,
        rows=[LeaderboardRow(**row) for row in ranked_rows],
    )
    file_path = output_dir / filename
    file_path.write_text(table.model_dump_json(indent=2), encoding="utf-8")
    return file_path


def generate_leaderboard_staging(
    *,
    staging_dir: Path,
    generation_id: str,
    generated_at_utc: str,
    full_rows: list[dict],
    hard_rows: list[dict],
) -> LeaderboardManifest:
    """Generate full/hard files and manifest in a staging directory."""
    staging_dir.mkdir(parents=True, exist_ok=True)

    full_file = f"leaderboard_full.{generation_id}.json"
    hard_file = f"leaderboard_hard.{generation_id}.json"

    full_path = _write_table_file(
        output_dir=staging_dir,
        filename=full_file,
        generation_id=generation_id,
        generated_at_utc=generated_at_utc,
        leaderboard="full",
        rows=full_rows,
    )
    hard_path = _write_table_file(
        output_dir=staging_dir,
        filename=hard_file,
        generation_id=generation_id,
        generated_at_utc=generated_at_utc,
        leaderboard="hard",
        rows=hard_rows,
    )

    manifest = LeaderboardManifest(
        schema_version="1.0",
        generation_id=generation_id,
        generated_at_utc=generated_at_utc,
        full_file=full_file,
        hard_file=hard_file,
        full_sha256=_sha256_file(full_path),
        hard_sha256=_sha256_file(hard_path),
    )
    (staging_dir / LEADERBOARD_MANIFEST_FILE).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def _load_manifest(staging_dir: Path) -> LeaderboardManifest:
    manifest_path = staging_dir / LEADERBOARD_MANIFEST_FILE
    return LeaderboardManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))


def _validate_staging_bundle(staging_dir: Path, manifest: LeaderboardManifest) -> None:
    allowed_files = {
        LEADERBOARD_MANIFEST_FILE,
        manifest.full_file,
        manifest.hard_file,
    }
    files_in_staging = {path.name for path in staging_dir.iterdir() if path.is_file()}
    if files_in_staging != allowed_files:
        raise ValueError("staging bundle must contain exactly manifest + full/hard generation files")

    full_path = staging_dir / manifest.full_file
    hard_path = staging_dir / manifest.hard_file

    # Ensure staged files parse against canonical table schema.
    LeaderboardTableFile(**json.loads(full_path.read_text(encoding="utf-8")))
    LeaderboardTableFile(**json.loads(hard_path.read_text(encoding="utf-8")))

    if _sha256_file(full_path) != manifest.full_sha256:
        raise ValueError("staged full file hash does not match manifest")
    if _sha256_file(hard_path) != manifest.hard_sha256:
        raise ValueError("staged hard file hash does not match manifest")


def publish_staged_leaderboard(*, staging_dir: Path, gh_pages_root: Path) -> LeaderboardManifest:
    """Publish a validated staging bundle with rollback-safe atomic swap semantics."""
    manifest = _load_manifest(staging_dir)
    _validate_staging_bundle(staging_dir, manifest)

    live_dir = gh_pages_root / LEADERBOARD_DATA_DIR
    live_parent = live_dir.parent
    live_parent.mkdir(parents=True, exist_ok=True)

    nonce = uuid4().hex
    replacement_dir = live_parent / f".leaderboard-data.new.{nonce}"
    backup_dir = live_parent / f".leaderboard-data.old.{nonce}"

    try:
        replacement_dir.mkdir(parents=True, exist_ok=False)

        # Upload generation assets first.
        shutil.copy2(staging_dir / manifest.full_file, replacement_dir / manifest.full_file)
        shutil.copy2(staging_dir / manifest.hard_file, replacement_dir / manifest.hard_file)

        if _sha256_file(replacement_dir / manifest.full_file) != manifest.full_sha256:
            raise ValueError("published full file hash mismatch")
        if _sha256_file(replacement_dir / manifest.hard_file) != manifest.hard_sha256:
            raise ValueError("published hard file hash mismatch")

        # Switch manifest last by writing it after both assets are present and verified.
        (replacement_dir / LEADERBOARD_MANIFEST_FILE).write_text(
            (staging_dir / LEADERBOARD_MANIFEST_FILE).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        if live_dir.exists():
            live_dir.rename(backup_dir)
        replacement_dir.rename(live_dir)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

    except Exception:
        # Never leave a failed publish with a switched manifest.
        if not live_dir.exists() and backup_dir.exists():
            backup_dir.rename(live_dir)
        if replacement_dir.exists():
            shutil.rmtree(replacement_dir)
        raise

    return manifest


def _load_submission_record(record_path: Path) -> tuple[SubmissionRecord, dict]:
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    return SubmissionRecord(**raw), raw


def _row_from_submission_record(record: SubmissionRecord, raw: dict) -> dict:
    missing_fields = [field for field in _REQUIRED_ROW_FIELDS if field not in raw]
    if missing_fields:
        missing_list = ", ".join(missing_fields)
        raise ValueError(
            f"accepted submission '{record.submission_id}' is missing leaderboard fields: {missing_list}"
        )

    row_payload = {
        "submission_id": record.submission_id,
        "name": raw["name"],
        "overall_score": raw["overall_score"],
        "shopping_score": raw["shopping_score"],
        "reddit_score": raw["reddit_score"],
        "gitlab_score": raw["gitlab_score"],
        "wikipedia_score": raw["wikipedia_score"],
        "map_score": raw["map_score"],
        "shopping_admin_score": raw["shopping_admin_score"],
        "success_count": raw["success_count"],
        "failure_count": raw["failure_count"],
        "error_count": raw["error_count"],
        "missing_count": raw["missing_count"],
        "webarena_verified_version": raw["webarena_verified_version"],
        "checksum": raw["checksum"],
        "submission_timestamp": raw.get("submission_timestamp") or record.processed_at_utc or record.updated_at_utc,
    }

    return LeaderboardRow(rank=1, **row_payload).model_dump(mode="python")


def _select_boards(raw: dict, *, submission_id: str) -> set[str]:
    selection = raw.get("leaderboard", "both")
    if selection == "both":
        return {"full", "hard"}
    if selection in {"full", "hard"}:
        return {selection}
    raise ValueError(
        f"accepted submission '{submission_id}' has invalid leaderboard value '{selection}', expected hard|full|both"
    )


def _rows_from_processed_dir(processed_dir: Path) -> tuple[list[dict], list[dict]]:
    full_rows: list[dict] = []
    hard_rows: list[dict] = []

    if not processed_dir.exists():
        return full_rows, hard_rows

    for record_path in sorted(processed_dir.glob("*.json")):
        record, raw = _load_submission_record(record_path)
        if record.status != SubmissionStatus.ACCEPTED:
            continue

        row = _row_from_submission_record(record, raw)
        boards = _select_boards(raw, submission_id=record.submission_id)
        if "full" in boards:
            full_rows.append(row)
        if "hard" in boards:
            hard_rows.append(row)

    return full_rows, hard_rows


def publish_from_processed(
    *,
    gh_pages_root: Path,
    processed_dir: Path,
    staging_dir: Path,
    generation_id: str | None = None,
    generated_at_utc: str | None = None,
    dry_run: bool = False,
) -> LeaderboardManifest:
    """Build and publish leaderboard artifacts from processed submission records."""
    generation_id = generation_id or _default_generation_id()
    generated_at_utc = generated_at_utc or _utc_now_z()

    full_rows, hard_rows = _rows_from_processed_dir(processed_dir)
    manifest = generate_leaderboard_staging(
        staging_dir=staging_dir,
        generation_id=generation_id,
        generated_at_utc=generated_at_utc,
        full_rows=full_rows,
        hard_rows=hard_rows,
    )
    if dry_run:
        return manifest

    return publish_staged_leaderboard(staging_dir=staging_dir, gh_pages_root=gh_pages_root)
