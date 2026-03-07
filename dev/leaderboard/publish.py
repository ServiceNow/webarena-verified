"""Leaderboard generation and atomic publish helpers for maintainer workflows."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from webarena_verified.types.leaderboard import (
    CanonicalSubmissionRecord,
    LeaderboardManifest,
    LeaderboardRow,
    LeaderboardTableFile,
)

# Leaderboard artifacts are published at branch root.
LEADERBOARD_DATA_DIR = Path(".")
LEADERBOARD_MANIFEST_FILE = "leaderboard_manifest.json"
_EMPTY_GENERATED_AT_UTC = "1970-01-01T00:00:00Z"

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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _coerce_submission_id(value: object, *, context: str) -> int:
    """Parse and validate submission_id as a positive integer."""
    if isinstance(value, bool):
        raise ValueError(f"{context}: submission_id must be a positive integer")
    if isinstance(value, int):
        if value >= 1:
            return value
        raise ValueError(f"{context}: submission_id must be >= 1")
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        if parsed >= 1:
            return parsed
    raise ValueError(f"{context}: submission_id must be a positive integer")


def _assert_unique_submission_ids(rows: list[dict], *, board_name: str) -> None:
    seen: set[int] = set()
    duplicates: set[int] = set()
    for row in rows:
        submission_id = _coerce_submission_id(row.get("submission_id"), context=f"{board_name} row")
        if submission_id in seen:
            duplicates.add(submission_id)
        seen.add(submission_id)

    if duplicates:
        duplicate_list = ", ".join(str(item) for item in sorted(duplicates))
        raise ValueError(f"duplicate submission_id(s) in {board_name}: {duplicate_list}")


def rank_rows(rows: list[dict], *, board_name: str = "leaderboard") -> list[dict]:
    """Return rows sorted and ranked by deterministic spec order."""
    _assert_unique_submission_ids(rows, board_name=board_name)
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            -float(row["overall_score"]),
            _coerce_submission_id(row.get("submission_id"), context=f"{board_name} row"),
        ),
    )
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
    leaderboard: Literal["full", "hard"],
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
    """Publish a validated staging bundle with manifest-last semantics."""
    manifest = _load_manifest(staging_dir)
    _validate_staging_bundle(staging_dir, manifest)

    live_dir = gh_pages_root / LEADERBOARD_DATA_DIR
    live_dir.mkdir(parents=True, exist_ok=True)

    nonce = uuid4().hex
    tmp_full = live_dir / f".{manifest.full_file}.tmp.{nonce}"
    tmp_hard = live_dir / f".{manifest.hard_file}.tmp.{nonce}"
    tmp_manifest = live_dir / f".{LEADERBOARD_MANIFEST_FILE}.tmp.{nonce}"

    full_dest = live_dir / manifest.full_file
    hard_dest = live_dir / manifest.hard_file
    manifest_dest = live_dir / LEADERBOARD_MANIFEST_FILE

    try:
        # Write generation assets first.
        shutil.copy2(staging_dir / manifest.full_file, tmp_full)
        shutil.copy2(staging_dir / manifest.hard_file, tmp_hard)

        if _sha256_file(tmp_full) != manifest.full_sha256:
            raise ValueError("published full file hash mismatch")
        if _sha256_file(tmp_hard) != manifest.hard_sha256:
            raise ValueError("published hard file hash mismatch")

        tmp_full.replace(full_dest)
        tmp_hard.replace(hard_dest)

        # Switch manifest last only after generation assets are present and verified.
        tmp_manifest.write_text((staging_dir / LEADERBOARD_MANIFEST_FILE).read_text(encoding="utf-8"), encoding="utf-8")
        tmp_manifest.replace(manifest_dest)

        # Remove stale generation files once manifest has switched.
        for stale_file in live_dir.glob("leaderboard_full.*.json"):
            if stale_file.name != manifest.full_file:
                stale_file.unlink(missing_ok=True)
        for stale_file in live_dir.glob("leaderboard_hard.*.json"):
            if stale_file.name != manifest.hard_file:
                stale_file.unlink(missing_ok=True)

    except Exception:
        # Never leave temp artifacts behind after a failed publish.
        for temp_file in (tmp_full, tmp_hard, tmp_manifest):
            temp_file.unlink(missing_ok=True)
        raise

    return manifest


def _load_submission_record(record_path: Path) -> tuple[CanonicalSubmissionRecord, dict]:
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    return CanonicalSubmissionRecord.model_validate(raw), raw


def _record_timestamp(record: CanonicalSubmissionRecord, raw: dict) -> str | None:
    """Resolve timestamp attached to exported leaderboard rows."""
    if raw.get("submission_timestamp"):
        return raw["submission_timestamp"]
    return record.eval_completed_at_utc


def _row_from_submission_record(record: CanonicalSubmissionRecord, raw: dict) -> dict:
    normalized_raw = {
        key: value for key, value in dict(raw).items() if key not in {"rank", "submission_id", "submission_timestamp"}
    }

    if "webarena_verified_version" not in normalized_raw:
        normalized_raw["webarena_verified_version"] = normalized_raw.get("evaluator_version", record.evaluator_version)

    missing_fields = [field for field in _REQUIRED_ROW_FIELDS if field not in normalized_raw]
    if missing_fields:
        missing_list = ", ".join(missing_fields)
        raise ValueError(f"accepted submission '{record.submission_id}' is missing leaderboard fields: {missing_list}")

    submission_id = _coerce_submission_id(
        raw.get("submission_id", record.submission_id),
        context=f"accepted submission '{record.submission_id}'",
    )

    validated = LeaderboardRow(
        rank=1,
        submission_id=submission_id,
        submission_timestamp=_record_timestamp(record, raw),
        **normalized_raw,
    )
    return validated.model_dump(mode="python")


def _select_boards(raw: dict, *, submission_id: int) -> set[str]:
    selection = raw.get("leaderboard", "both")
    if selection == "both":
        return {"full", "hard"}
    if selection in {"full", "hard"}:
        return {selection}
    raise ValueError(
        f"accepted submission '{submission_id}' has invalid leaderboard value '{selection}', expected hard|full|both"
    )


def _parse_utc_z_timestamp(value: str, *, field_name: str, submission_id: int | str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(
            f"canonical submission '{submission_id}' has invalid {field_name}: expected RFC3339 UTC ending with 'Z'"
        ) from exc
    return parsed.replace(tzinfo=UTC)


def _submission_id_as_int(submission_id: int | str) -> int:
    try:
        return int(submission_id)
    except ValueError as exc:
        raise ValueError(f"canonical submission_id must be numeric, got '{submission_id}'") from exc


def _load_canonical_entries(canonical_dir: Path) -> list[tuple[Path, CanonicalSubmissionRecord, dict, datetime, int]]:
    entries: list[tuple[Path, CanonicalSubmissionRecord, dict, datetime, int]] = []
    if not canonical_dir.exists():
        return entries

    for record_path in sorted(canonical_dir.glob("*.json")):
        record, raw = _load_submission_record(record_path)
        if record_path.stem != str(record.submission_id):
            raise ValueError(
                f"canonical file name '{record_path.name}' does not match submission_id '{record.submission_id}'"
            )
        eval_completed_at_utc = raw.get("eval_completed_at_utc")
        if not isinstance(eval_completed_at_utc, str) or not eval_completed_at_utc:
            raise ValueError(f"canonical submission '{record.submission_id}' is missing eval_completed_at_utc")
        eval_completed_at = _parse_utc_z_timestamp(
            eval_completed_at_utc,
            field_name="eval_completed_at_utc",
            submission_id=record.submission_id,
        )
        entries.append((record_path, record, raw, eval_completed_at, _submission_id_as_int(record.submission_id)))

    return entries


def _deterministic_generation_id(
    canonical_entries: list[tuple[Path, CanonicalSubmissionRecord, dict, datetime, int]],
) -> str:
    if not canonical_entries:
        return "gen-empty"

    digest = hashlib.sha256()
    for _, _, raw, _, _ in canonical_entries:
        canonical_json = json.dumps(raw, sort_keys=True, separators=(",", ":"))
        digest.update(canonical_json.encode("utf-8"))
        digest.update(b"\n")
    return f"gen-{digest.hexdigest()[:16]}"


def _default_generated_at_utc(
    canonical_entries: list[tuple[Path, CanonicalSubmissionRecord, dict, datetime, int]],
) -> str:
    if not canonical_entries:
        return _EMPTY_GENERATED_AT_UTC
    latest = max(entry[3] for entry in canonical_entries)
    return latest.strftime("%Y-%m-%dT%H:%M:%SZ")


def _rows_from_canonical_entries(
    canonical_entries: list[tuple[Path, CanonicalSubmissionRecord, dict, datetime, int]],
) -> tuple[list[dict], list[dict]]:
    full_rows: list[dict] = []
    hard_rows: list[dict] = []

    for _, record, raw, _, _ in canonical_entries:
        row = _row_from_submission_record(record, raw)
        boards = _select_boards(raw, submission_id=record.submission_id)
        if "full" in boards:
            full_rows.append(row)
        if "hard" in boards:
            hard_rows.append(row)

    return full_rows, hard_rows


def publish_from_canonical(
    *,
    branch_root: Path,
    canonical_dir: Path,
    staging_dir: Path,
    max_canonical_records: int = 100,
    generation_id: str | None = None,
    generated_at_utc: str | None = None,
    dry_run: bool = False,
) -> LeaderboardManifest:
    """Build and publish leaderboard artifacts from canonical submission records."""
    if max_canonical_records < 1:
        raise ValueError("max_canonical_records must be >= 1")

    canonical_entries = _load_canonical_entries(canonical_dir)
    canonical_entries.sort(key=lambda entry: (entry[3], entry[4]), reverse=True)

    retained_entries = canonical_entries[:max_canonical_records]
    pruned_entries = canonical_entries[max_canonical_records:]

    if not dry_run:
        for pruned_path, _, _, _, _ in pruned_entries:
            pruned_path.unlink(missing_ok=True)

    generation_id = generation_id or _deterministic_generation_id(retained_entries)
    generated_at_utc = generated_at_utc or _default_generated_at_utc(retained_entries)

    full_rows, hard_rows = _rows_from_canonical_entries(retained_entries)
    manifest = generate_leaderboard_staging(
        staging_dir=staging_dir,
        generation_id=generation_id,
        generated_at_utc=generated_at_utc,
        full_rows=full_rows,
        hard_rows=hard_rows,
    )
    if dry_run:
        return manifest

    return publish_staged_leaderboard(staging_dir=staging_dir, gh_pages_root=branch_root)
