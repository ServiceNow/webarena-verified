"""Persistence for submission control-plane records."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from dev.leaderboard.models import SubmissionRecord, SubmissionStatus

if TYPE_CHECKING:
    from pathlib import Path


class SubmissionRecordRepository:
    """Persist and load submission control-plane records."""

    def __init__(self, root: Path) -> None:
        """Initialize repository rooted at status-partitioned record directories."""
        self._root = root

    def load_existing_records(self) -> dict[tuple[str, int], SubmissionRecord]:
        """Load records keyed by `(hf_repo, hf_pr_id)` for fast orchestration lookups."""
        records: dict[tuple[str, int], SubmissionRecord] = {}
        if not self._root.exists():
            return records

        for status_dir in self._root.iterdir():
            if not status_dir.is_dir():
                continue
            for record_file in status_dir.glob("*.json"):
                try:
                    payload = json.loads(record_file.read_text(encoding="utf-8"))
                    record = SubmissionRecord.model_validate(payload)
                except (OSError, json.JSONDecodeError, ValueError) as exc:
                    raise RuntimeError(f"Unreadable submission record '{record_file}': {exc}") from exc
                records[(record.hf_repo, record.hf_pr_id)] = record
        return records

    def persist_submission_record(self, previous: SubmissionRecord | None, updated: SubmissionRecord) -> None:
        """Replace prior status file when needed, then write the updated record."""
        if previous:
            previous_path = self.record_path(previous)
            if previous_path.exists():
                previous_path.unlink()
        self.write_record(updated)

    def write_record(self, record: SubmissionRecord) -> None:
        """Serialize one record as deterministic JSON under its status directory."""
        path = self.record_path(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True)
        path.write_text(f"{serialized}\n", encoding="utf-8")

    def read_all_records(self) -> list[SubmissionRecord]:
        """Read every stored record for submissions.json generation."""
        if not self._root.exists():
            return []

        records: list[SubmissionRecord] = []
        for path in sorted(self._root.glob("*/*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(SubmissionRecord.model_validate(payload))
        return records

    def record_path(self, record: SubmissionRecord) -> Path:
        """Return file location `<root>/<status>/<submission_id>.json`."""
        return self.status_dir(record.status) / f"{record.submission_id}.json"

    def status_dir(self, status: SubmissionStatus) -> Path:
        """Map status enum to its on-disk partition directory."""
        return self._root / status.value
