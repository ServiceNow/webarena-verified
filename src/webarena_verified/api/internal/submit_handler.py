import datetime
import hashlib
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import cast

from huggingface_hub import CommitOperationAdd, HfApi
from pydantic import ValidationError

from webarena_verified.core.utils import logger
from webarena_verified.types.leaderboard import (
    IntakeManifest,
    IntakeManifestFile,
    IntakePackagingSummary,
    IntakeSubmission,
    SubmissionLeaderboard,
)
from webarena_verified.types.submit_result import SubmitResult

_SUMMARY_FILE_NAME = "summary.json"
_SUBMISSION_FILE_NAME = "submission.json"
_MANIFEST_FILE_NAME = "manifest.json"
_TASKS_DIR_NAME = "tasks"
_MISSING_SENTINEL_FILE = ".missing"
_AGENT_RESPONSE_FILE = "agent_response.json"
_NETWORK_HAR_FILE = "network.har"
_MANIFEST_SCHEMA_VERSION = "1.0"
_INBOX_PREFIX = "submissions/inbox"

_REQUIRED_PACKAGING_SUMMARY_FIELDS = (
    "tasks_packaged",
    "tasks_with_issues",
    "duplicate_tasks",
    "unknown_tasks",
    "missing_from_output",
)


class SubmitHandler:
    def __init__(self, submission_dir: Path, hf_repo: str, hf_token: str | None = None) -> None:
        self.submission_dir = submission_dir
        self.hf_repo = hf_repo
        self.hf_token = hf_token

    def submit(
        self,
        *,
        name: str,
        leaderboard: str,
        reference: str,
        version: str | None = None,
        contact_info: str | None = None,
    ) -> SubmitResult:
        logger.info(f"Validating submission directory: {self.submission_dir}")
        task_dirs = self._validate_submission_dir()

        logger.info("Loading packaging summary")
        packaging_summary = self._load_packaging_summary()

        submission_uid = str(uuid.uuid4())
        logger.info(f"Submission UID: {submission_uid}")

        logger.info("Preparing staging payload")
        with tempfile.TemporaryDirectory() as tmp_dir:
            staging_dir = Path(tmp_dir)
            tasks_submitted = self._prepare_staging(
                staging_dir=staging_dir,
                task_dirs=task_dirs,
                name=name,
                leaderboard=leaderboard,
                reference=reference,
                packaging_summary=packaging_summary,
                version=version,
                contact_info=contact_info,
            )

            logger.info("Uploading submission to HuggingFace")
            pr_url, pr_number = self._upload_to_hf(
                staging_dir=staging_dir,
                submission_uid=submission_uid,
                name=name,
                leaderboard=leaderboard,
            )

        return SubmitResult(
            pr_url=pr_url,
            pr_number=pr_number,
            submission_uid=submission_uid,
            hf_repo=self.hf_repo,
            submission_dir=str(self.submission_dir),
            tasks_submitted=tasks_submitted,
        )

    def _validate_submission_dir(self) -> list[Path]:
        if not self.submission_dir.exists():
            raise ValueError(f"Submission directory does not exist: {self.submission_dir}")
        if not self.submission_dir.is_dir():
            raise ValueError(f"Submission path is not a directory: {self.submission_dir}")

        summary_path = self.submission_dir / _SUMMARY_FILE_NAME
        if not summary_path.exists() or not summary_path.is_file():
            raise ValueError(f"Missing required {_SUMMARY_FILE_NAME} in: {self.submission_dir}")

        task_dirs = self._collect_valid_task_dirs()
        if not task_dirs:
            raise ValueError(
                "No valid numeric task directories found with required files "
                f"({_AGENT_RESPONSE_FILE} + {_NETWORK_HAR_FILE} or {_MISSING_SENTINEL_FILE})"
            )
        return task_dirs

    def _collect_valid_task_dirs(self) -> list[Path]:
        valid: list[Path] = []
        children = [child for child in self.submission_dir.iterdir() if child.is_dir() and child.name.isdigit()]
        for child in sorted(children, key=lambda path: int(path.name)):
            if not child.is_dir() or not child.name.isdigit():
                continue
            if self._is_valid_task_dir(child):
                valid.append(child)
        return valid

    def _is_valid_task_dir(self, task_dir: Path) -> bool:
        if (task_dir / _MISSING_SENTINEL_FILE).exists():
            return True

        has_agent_response = (task_dir / _AGENT_RESPONSE_FILE).exists()
        has_network_har = (task_dir / _NETWORK_HAR_FILE).exists()
        return has_agent_response and has_network_har

    def _load_packaging_summary(self) -> IntakePackagingSummary:
        summary_path = self.submission_dir / _SUMMARY_FILE_NAME
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {_SUMMARY_FILE_NAME}: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError(f"{_SUMMARY_FILE_NAME} must contain a JSON object")

        packaging_summary = payload.get("packaging_summary")
        if not isinstance(packaging_summary, dict):
            raise ValueError(f"{_SUMMARY_FILE_NAME} must contain a 'packaging_summary' object")

        missing_fields = [field for field in _REQUIRED_PACKAGING_SUMMARY_FIELDS if field not in packaging_summary]
        if missing_fields:
            raise ValueError(f"Missing required packaging_summary field(s): {', '.join(missing_fields)}")

        try:
            return IntakePackagingSummary.model_validate(packaging_summary)
        except ValidationError as exc:
            raise ValueError(f"Invalid packaging_summary: {exc}") from exc

    def _prepare_staging(
        self,
        *,
        staging_dir: Path,
        task_dirs: list[Path],
        name: str,
        leaderboard: str,
        reference: str,
        packaging_summary: IntakePackagingSummary,
        version: str | None,
        contact_info: str | None,
    ) -> int:
        tasks_root = staging_dir / _TASKS_DIR_NAME
        tasks_root.mkdir(parents=True, exist_ok=True)

        for task_dir in task_dirs:
            shutil.copytree(task_dir, tasks_root / task_dir.name)

        created_at_utc = self._now_utc_z()
        submission_path = staging_dir / _SUBMISSION_FILE_NAME
        try:
            allowed_leaderboards = {item.value for item in SubmissionLeaderboard}
            if leaderboard not in allowed_leaderboards:
                raise ValueError(f"leaderboard must be one of: {', '.join(sorted(allowed_leaderboards))}")

            resolved_leaderboard = cast(SubmissionLeaderboard, leaderboard)
            submission = IntakeSubmission(
                name=name,
                leaderboard=resolved_leaderboard,
                reference=reference,
                created_at_utc=created_at_utc,
                packaging_summary=packaging_summary,
                version=version,
                contact_info=contact_info,
            )
        except (ValidationError, ValueError) as exc:
            raise ValueError(f"Invalid submission metadata: {exc}") from exc
        submission_path.write_text(submission.model_dump_json(indent=2) + "\n", encoding="utf-8")

        manifest_entries = self._build_manifest_entries(staging_dir)
        manifest = IntakeManifest(
            schema_version=_MANIFEST_SCHEMA_VERSION,
            created_at_utc=self._now_utc_z(),
            files=manifest_entries,
        )
        (staging_dir / _MANIFEST_FILE_NAME).write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return len(task_dirs)

    def _build_manifest_entries(self, staging_dir: Path) -> list[IntakeManifestFile]:
        entries: list[IntakeManifestFile] = []
        for path in sorted(staging_dir.rglob("*")):
            if not path.is_file() or path.name == _MANIFEST_FILE_NAME:
                continue
            relative = path.relative_to(staging_dir).as_posix()
            entries.append(
                IntakeManifestFile(
                    path=relative,
                    sha256=self._sha256(path),
                    size_bytes=path.stat().st_size,
                )
            )
        return entries

    def _upload_to_hf(self, *, staging_dir: Path, submission_uid: str, name: str, leaderboard: str) -> tuple[str, int]:
        api = HfApi(token=self.hf_token)
        inbox_path = f"{_INBOX_PREFIX}/{submission_uid}"

        operations: list[CommitOperationAdd] = []
        for file_path in sorted(staging_dir.rglob("*")):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(staging_dir).as_posix()
            operations.append(
                CommitOperationAdd(
                    path_in_repo=f"{inbox_path}/{relative}",
                    path_or_fileobj=str(file_path),
                )
            )

        pr_description = (
            f"Submission Name: {name}\n"
            f"Leaderboard: {leaderboard}\n\n"
            "For any issues or questions, please open an issue at "
            "https://github.com/ServiceNow/webarena-verified/issues\n\n"
            "---\n\n"
            "> This description is auto-generated. Do not manually edit — "
            "it will discard the submission. To cancel the submission, click Close."
        )

        logger.info(f"Creating PR with {len(operations)} files at {inbox_path}/")
        commit_info = api.create_commit(
            repo_id=self.hf_repo,
            repo_type="dataset",
            operations=operations,
            commit_message=f"[Leaderboard Submission] [{submission_uid}] {name}",
            commit_description=pr_description,
            create_pr=True,
        )

        pr_number = commit_info.pr_num
        pr_url = commit_info.pr_url

        if pr_number is None or not pr_url:
            raise ValueError("Unable to resolve created HuggingFace PR metadata")

        return pr_url, pr_number

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now_utc_z() -> str:
        return datetime.datetime.now(tz=datetime.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
