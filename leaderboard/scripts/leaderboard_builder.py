from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from webarena_verified.submission.config import SubmissionFlowConfig
from webarena_verified.submission.models import SubmissionMode

from .models import (
    EvaluationSummaryPayload,
    LeaderboardGenerationArtifact,
    LeaderboardLatestArtifact,
    LeaderboardRow,
)


class LeaderboardBuilder:
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
        full_rows, hard_rows = self._load_existing_rows(repo_root)
        full_rows = [row for row in full_rows if row.submission_uid != submission_uid]
        hard_rows = [row for row in hard_rows if row.submission_uid != submission_uid]

        if submission_mode in {SubmissionMode.FULL, SubmissionMode.BOTH}:
            full_summary = evaluation_summaries.get(SubmissionMode.FULL)
            if full_summary is None:
                raise ValueError("Missing full leaderboard evaluation summary for submission mode")
            full_rows.append(
                self._row_from_summary(
                    submission_uid=submission_uid,
                    source_url=source_url,
                    submission_name=submission_name,
                    submission_model=submission_model,
                    evaluation_summary=full_summary,
                )
            )
        if submission_mode in {SubmissionMode.HARD, SubmissionMode.BOTH}:
            hard_summary = evaluation_summaries.get(SubmissionMode.HARD)
            if hard_summary is None:
                raise ValueError("Missing hard leaderboard evaluation summary for submission mode")
            hard_rows.append(
                self._row_from_summary(
                    submission_uid=submission_uid,
                    source_url=source_url,
                    submission_name=submission_name,
                    submission_model=submission_model,
                    evaluation_summary=hard_summary,
                )
            )

        return self._write_leaderboard_artifacts(repo_root=repo_root, full_rows=full_rows, hard_rows=hard_rows)

    def rebuild_leaderboard(self, *, repo_root: Path) -> tuple[Path, Path, Path]:
        full_rows, hard_rows = self._load_existing_rows(repo_root)
        return self._write_leaderboard_artifacts(repo_root=repo_root, full_rows=full_rows, hard_rows=hard_rows)

    def _load_existing_rows(self, repo_root: Path) -> tuple[list[LeaderboardRow], list[LeaderboardRow]]:
        latest_path = (
            repo_root / self._flow_config.leaderboard_root_dir / self._flow_config.leaderboard_latest_file_name
        )
        if not latest_path.exists():
            return [], []

        latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
        latest = LeaderboardLatestArtifact.model_validate(latest_payload)

        full_path = repo_root / latest.full_file
        hard_path = repo_root / latest.hard_file

        full_rows: list[LeaderboardRow] = []
        hard_rows: list[LeaderboardRow] = []

        if full_path.exists():
            full_payload = json.loads(full_path.read_text(encoding="utf-8"))
            full_artifact = LeaderboardGenerationArtifact.model_validate(full_payload)
            full_rows = list(full_artifact.rows)

        if hard_path.exists():
            hard_payload = json.loads(hard_path.read_text(encoding="utf-8"))
            hard_artifact = LeaderboardGenerationArtifact.model_validate(hard_payload)
            hard_rows = list(hard_artifact.rows)

        return full_rows, hard_rows

    def _write_leaderboard_artifacts(
        self,
        *,
        repo_root: Path,
        full_rows: list[LeaderboardRow],
        hard_rows: list[LeaderboardRow],
    ) -> tuple[Path, Path, Path]:
        ranked_full = self._rank_rows(full_rows)
        ranked_hard = self._rank_rows(hard_rows)

        generation_id = self._build_generation_id(full_rows=ranked_full, hard_rows=ranked_hard)
        generated_at_utc = self._resolve_generated_at_utc(repo_root=repo_root, generation_id=generation_id)
        generation_dir = repo_root / self._flow_config.leaderboard_generation_dir(generation_id)
        generation_dir.mkdir(parents=True, exist_ok=True)

        full_artifact = self._build_generation_artifact(
            generation_id=generation_id,
            leaderboard=SubmissionMode.FULL,
            rows=ranked_full,
            generated_at_utc=generated_at_utc,
        )
        hard_artifact = self._build_generation_artifact(
            generation_id=generation_id,
            leaderboard=SubmissionMode.HARD,
            rows=ranked_hard,
            generated_at_utc=generated_at_utc,
        )

        full_path = generation_dir / self._flow_config.generation_full_file_name
        hard_path = generation_dir / self._flow_config.generation_hard_file_name
        full_content = full_artifact.model_dump_json(indent=2) + "\n"
        hard_content = hard_artifact.model_dump_json(indent=2) + "\n"
        self._write_if_changed(path=full_path, content=full_content)
        self._write_if_changed(path=hard_path, content=hard_content)

        latest = LeaderboardLatestArtifact(
            schema_version=self._flow_config.schema_version,
            generation_id=generation_id,
            generated_at_utc=generated_at_utc,
            full_file=full_path.relative_to(repo_root).as_posix(),
            hard_file=hard_path.relative_to(repo_root).as_posix(),
            full_sha256=self._sha256_file(full_path),
            hard_sha256=self._sha256_file(hard_path),
            checksum="0" * 64,
            checksum_algo=self._flow_config.checksum_algo,
        )
        latest_payload = latest.model_dump(mode="json")
        latest_payload["checksum"] = self._checksum_for_payload(latest_payload)

        latest_path = (
            repo_root / self._flow_config.leaderboard_root_dir / self._flow_config.leaderboard_latest_file_name
        )
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        latest_content = json.dumps(latest_payload, indent=2) + "\n"
        self._write_if_changed(path=latest_path, content=latest_content)
        return latest_path, full_path, hard_path

    @staticmethod
    def _rank_rows(rows: list[LeaderboardRow]) -> list[LeaderboardRow]:
        ranked = sorted(rows, key=lambda item: (-item.overall, item.submission_uid))
        result: list[LeaderboardRow] = []
        for index, row in enumerate(ranked, start=1):
            payload = row.model_dump(mode="json")
            payload["rank"] = index
            result.append(LeaderboardRow.model_validate(payload))
        return result

    def _row_from_summary(
        self,
        *,
        submission_uid: str,
        source_url: str,
        submission_name: str,
        submission_model: str,
        evaluation_summary: EvaluationSummaryPayload,
    ) -> LeaderboardRow:
        return LeaderboardRow(
            rank=1,
            submission_uid=submission_uid,
            name=submission_name,
            model=submission_model,
            overall=evaluation_summary.scores.overall,
            shopping=evaluation_summary.scores.shopping,
            shopping_admin=evaluation_summary.scores.shopping_admin,
            gitlab=evaluation_summary.scores.gitlab,
            map=evaluation_summary.scores.map,
            reddit=evaluation_summary.scores.reddit,
            multisite=evaluation_summary.scores.multisite,
            gitlab_reddit=evaluation_summary.scores.gitlab_reddit,
            source=source_url,
        )

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
            "checksum": "0" * 64,
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
