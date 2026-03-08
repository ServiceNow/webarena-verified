from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
from pathlib import Path  # noqa: TC003

from webarena_verified.submission.config import SubmissionFlowConfig
from webarena_verified.submission.models import SubmissionMode

from .models import (
    EvaluationSummaryPayload,
    LeaderboardGenerationArtifact,
    LeaderboardLatestArtifact,
    LeaderboardRow,
)

logger = logging.getLogger(__name__)

_CHECKSUM_PLACEHOLDER = "0" * 64


class LeaderboardBuilder:
    """Builds and updates ranked leaderboard generation artifacts.

    Sits at stage 3 of the ingest pipeline.  After ``SubmissionEvaluator``
    produces ``EvaluationSummaryPayload`` objects for each submission mode,
    this class merges the new scores into (or rebuilds from) the existing
    leaderboard rows, re-ranks by overall score, and writes three files to
    the ``leaderboard-submissions`` branch checkout:

    * ``<generation_dir>/full.json`` - ``LeaderboardGenerationArtifact``
      for the full (812-task) leaderboard.
    * ``<generation_dir>/hard.json`` - same for the hard (258-task) subset.
    * ``leaderboard/latest.json`` - ``LeaderboardLatestArtifact`` pointer
      with SHA-256 digests of the generation files.

    The generation ID is a content-addressable hash of the ranked rows, so
    unchanged leaderboard content reuses the same generation directory and
    preserves the original timestamp.
    """

    def __init__(self, flow_config: SubmissionFlowConfig | None = None) -> None:
        self._flow_config = flow_config or SubmissionFlowConfig()

    def apply_submission_result(
        self,
        *,
        repo_root: Path,
        submission_uid: str,
        submission_mode: SubmissionMode,
        source_url: str,
        submission_name: str,
        submission_model: str,
        evaluation_summaries: dict[SubmissionMode, EvaluationSummaryPayload],
    ) -> tuple[Path, Path, Path]:
        """Integrate a newly evaluated submission into the leaderboard.

        Loads the existing rows from the current generation, removes any
        prior entry for ``submission_uid`` (idempotent upsert), appends new
        rows from the evaluation summaries, re-ranks, and writes updated
        generation artifacts.

        Called by ``submission_handler.ingest_hf_submission`` at the end of
        a successful ingest cycle.

        Returns:
            ``(latest_path, full_path, hard_path)`` — the three files written.
        """
        logger.info("Applying submission result for uid=%s mode=%s", submission_uid, submission_mode)
        full_rows, hard_rows = self._load_existing_rows(repo_root)
        full_rows = [row for row in full_rows if row.submission_uid != submission_uid]
        hard_rows = [row for row in hard_rows if row.submission_uid != submission_uid]

        rows_by_mode = {SubmissionMode.FULL: full_rows, SubmissionMode.HARD: hard_rows}
        for mode, rows in rows_by_mode.items():
            if submission_mode not in {mode, SubmissionMode.BOTH}:
                continue
            summary = evaluation_summaries.get(mode)
            if summary is None:
                raise ValueError(f"Missing {mode.value} leaderboard evaluation summary for submission mode")
            rows.append(
                LeaderboardRow(
                    rank=1,
                    submission_uid=submission_uid,
                    name=submission_name,
                    model=submission_model,
                    overall=summary.scores.overall,
                    shopping=summary.scores.shopping,
                    shopping_admin=summary.scores.shopping_admin,
                    gitlab=summary.scores.gitlab,
                    map=summary.scores.map,
                    reddit=summary.scores.reddit,
                    multisite=summary.scores.multisite,
                    gitlab_reddit=summary.scores.gitlab_reddit,
                    source=source_url,
                )
            )

        return self._write_leaderboard_artifacts(repo_root=repo_root, full_rows=full_rows, hard_rows=hard_rows)

    def rebuild_leaderboard(self, *, repo_root: Path) -> tuple[Path, Path, Path]:
        """Re-rank and rewrite generation artifacts from existing rows.

        Unlike ``apply_submission_result``, this does not add or remove any
        rows — it simply loads the current leaderboard state, re-ranks, and
        writes fresh artifacts.  Useful for repairing artifacts after a
        schema change or manual row edit.

        Returns:
            ``(latest_path, full_path, hard_path)`` — the three files written.
        """
        full_rows, hard_rows = self._load_existing_rows(repo_root)
        return self._write_leaderboard_artifacts(repo_root=repo_root, full_rows=full_rows, hard_rows=hard_rows)

    @staticmethod
    def _load_rows_from_file(path: Path) -> list[LeaderboardRow]:
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        artifact = LeaderboardGenerationArtifact.model_validate(payload)
        return list(artifact.rows)

    def _load_existing_rows(self, repo_root: Path) -> tuple[list[LeaderboardRow], list[LeaderboardRow]]:
        latest_path = (
            repo_root / self._flow_config.leaderboard_root_dir / self._flow_config.leaderboard_latest_file_name
        )
        if not latest_path.exists():
            return [], []

        latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
        latest = LeaderboardLatestArtifact.model_validate(latest_payload)

        full_rows = self._load_rows_from_file(repo_root / latest.full_file)
        hard_rows = self._load_rows_from_file(repo_root / latest.hard_file)
        return full_rows, hard_rows

    def _write_generation_file(
        self,
        *,
        generation_dir: Path,
        mode: SubmissionMode,
        rows: list[LeaderboardRow],
        generation_id: str,
        generated_at_utc: str,
    ) -> Path:
        file_name = (
            self._flow_config.generation_full_file_name
            if mode == SubmissionMode.FULL
            else self._flow_config.generation_hard_file_name
        )
        artifact = self._build_generation_artifact(
            generation_id=generation_id,
            leaderboard=mode,
            rows=rows,
            generated_at_utc=generated_at_utc,
        )
        path = generation_dir / file_name
        self._write_if_changed(path=path, content=artifact.model_dump_json(indent=2) + "\n")
        return path

    def _write_leaderboard_artifacts(
        self,
        *,
        repo_root: Path,
        full_rows: list[LeaderboardRow],
        hard_rows: list[LeaderboardRow],
    ) -> tuple[Path, Path, Path]:
        ranked_full = self._rank_rows(full_rows)
        ranked_hard = self._rank_rows(hard_rows)
        logger.info("Ranked %d full rows, %d hard rows", len(ranked_full), len(ranked_hard))

        generation_id = self._build_generation_id(full_rows=ranked_full, hard_rows=ranked_hard)
        generated_at_utc = self._resolve_generated_at_utc(repo_root=repo_root, generation_id=generation_id)
        generation_dir = repo_root / self._flow_config.leaderboard_generation_dir(generation_id)
        generation_dir.mkdir(parents=True, exist_ok=True)

        full_path = self._write_generation_file(
            generation_dir=generation_dir,
            mode=SubmissionMode.FULL,
            rows=ranked_full,
            generation_id=generation_id,
            generated_at_utc=generated_at_utc,
        )
        hard_path = self._write_generation_file(
            generation_dir=generation_dir,
            mode=SubmissionMode.HARD,
            rows=ranked_hard,
            generation_id=generation_id,
            generated_at_utc=generated_at_utc,
        )

        latest_path = self._write_latest_artifact(
            repo_root=repo_root,
            generation_id=generation_id,
            generated_at_utc=generated_at_utc,
            full_path=full_path,
            hard_path=hard_path,
        )
        logger.info("Wrote artifacts: generation_id=%s latest=%s", generation_id, latest_path)
        return latest_path, full_path, hard_path

    def _write_latest_artifact(
        self,
        *,
        repo_root: Path,
        generation_id: str,
        generated_at_utc: str,
        full_path: Path,
        hard_path: Path,
    ) -> Path:
        latest_payload = {
            "schema_version": self._flow_config.schema_version,
            "generation_id": generation_id,
            "generated_at_utc": generated_at_utc,
            "full_file": full_path.relative_to(repo_root).as_posix(),
            "hard_file": hard_path.relative_to(repo_root).as_posix(),
            "full_sha256": self._sha256_file(full_path),
            "hard_sha256": self._sha256_file(hard_path),
            "checksum": _CHECKSUM_PLACEHOLDER,
            "checksum_algo": self._flow_config.checksum_algo,
        }
        latest_payload["checksum"] = self._checksum_for_payload(latest_payload)

        latest_path = (
            repo_root / self._flow_config.leaderboard_root_dir / self._flow_config.leaderboard_latest_file_name
        )
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_if_changed(path=latest_path, content=json.dumps(latest_payload, indent=2) + "\n")
        return latest_path

    @staticmethod
    def _rank_rows(rows: list[LeaderboardRow]) -> list[LeaderboardRow]:
        ranked = sorted(rows, key=lambda item: (-item.overall, item.submission_uid))
        return [row.model_copy(update={"rank": index}) for index, row in enumerate(ranked, start=1)]

    def _build_generation_artifact(
        self,
        *,
        generation_id: str,
        leaderboard: SubmissionMode,
        rows: list[LeaderboardRow],
        generated_at_utc: str,
    ) -> LeaderboardGenerationArtifact:
        payload = {
            "generation_id": generation_id,
            "leaderboard": leaderboard,
            "generated_at_utc": generated_at_utc,
            "rows_count": len(rows),
            "rows": [row.model_dump(mode="json") for row in rows],
            "checksum": _CHECKSUM_PLACEHOLDER,
            "checksum_algo": self._flow_config.checksum_algo,
        }
        payload["checksum"] = self._checksum_for_payload(payload)
        return LeaderboardGenerationArtifact.model_validate(payload)

    def _build_generation_id(self, *, full_rows: list[LeaderboardRow], hard_rows: list[LeaderboardRow]) -> str:
        digest = hashlib.sha256()
        digest.update(json.dumps([row.model_dump(mode="json") for row in full_rows], sort_keys=True).encode("utf-8"))
        digest.update(b"\n")
        digest.update(json.dumps([row.model_dump(mode="json") for row in hard_rows], sort_keys=True).encode("utf-8"))
        return f"{self._flow_config.generation_prefix}-{digest.hexdigest()[:16]}"

    @staticmethod
    def _checksum_for_payload(payload: dict) -> str:
        material = {key: value for key, value in payload.items() if key != "checksum"}
        content = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now_utc_z() -> str:
        return dt.datetime.now(tz=dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _resolve_generated_at_utc(self, *, repo_root: Path, generation_id: str) -> str:
        latest_path = (
            repo_root / self._flow_config.leaderboard_root_dir / self._flow_config.leaderboard_latest_file_name
        )
        if not latest_path.exists():
            return self._now_utc_z()

        latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
        latest = LeaderboardLatestArtifact.model_validate(latest_payload)
        if latest.generation_id != generation_id:
            return self._now_utc_z()
        return latest.generated_at_utc

    @staticmethod
    def _write_if_changed(*, path: Path, content: str) -> None:
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return
        path.write_text(content, encoding="utf-8")
