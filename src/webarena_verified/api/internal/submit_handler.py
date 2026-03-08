import datetime
import hashlib
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from huggingface_hub import CommitOperationAdd, HfApi
from pydantic import ValidationError

from webarena_verified.core.utils import logger
from webarena_verified.types.leaderboard import (
    IntakeManifest,
    IntakeManifestFile,
    IntakePackagingSummary,
    IntakeSubmission,
)
from webarena_verified.types.submit_result import SubmitResult

_SUBMISSION_FILE_NAME = "submission.json"
_MANIFEST_FILE_NAME = "manifest.json"
_TASKS_DIR_NAME = "tasks"
_AGENT_RESPONSE_FILE = "agent_response.json"
_NETWORK_HAR_FILE = "network.har"
_MANIFEST_SCHEMA_VERSION = "1.0"
_INBOX_PREFIX = "submissions/inbox"

_PACKAGED_TASKS_KEYS = ("valid", "incomplete", "missing", "expected")


class SubmitHandler:
    def __init__(self, submission_dir: Path, hf_repo: str, hf_token: str | None = None) -> None:
        self.submission_dir = submission_dir
        self.hf_repo = hf_repo
        self.hf_token = hf_token

    def submit(
        self,
    ) -> SubmitResult:
        logger.info(f"Validating submission directory: {self.submission_dir}")
        task_dirs = self._validate_submission_dir()

        logger.info("Loading submission metadata")
        submission_metadata = self._load_submission_metadata()

        logger.info("Computing packaging summary")
        packaging_summary = self._compute_packaging_summary(
            task_dirs=task_dirs,
            submission_metadata=submission_metadata,
        )

        submission_uid = str(uuid.uuid4())
        logger.info(f"Submission UID: {submission_uid}")

        logger.info("Preparing staging payload")
        with tempfile.TemporaryDirectory() as tmp_dir:
            staging_dir = Path(tmp_dir)
            tasks_submitted = self._prepare_staging(
                staging_dir=staging_dir,
                task_dirs=task_dirs,
                submission_metadata=submission_metadata,
                packaging_summary=packaging_summary,
            )

            name = submission_metadata["name"]
            leaderboard = submission_metadata["leaderboard"]
            if name is None or leaderboard is None:
                raise ValueError(f"{_SUBMISSION_FILE_NAME} must include non-empty 'name' and 'leaderboard'")

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

        submission_path = self.submission_dir / _SUBMISSION_FILE_NAME
        if not submission_path.exists() or not submission_path.is_file():
            raise ValueError(f"Missing required {_SUBMISSION_FILE_NAME} in: {self.submission_dir}")

        task_dirs = self._collect_valid_task_dirs()
        if not task_dirs:
            raise ValueError(
                "No valid numeric task directories found with required files "
                f"({_AGENT_RESPONSE_FILE} + {_NETWORK_HAR_FILE})"
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
        has_agent_response = (task_dir / _AGENT_RESPONSE_FILE).exists()
        has_network_har = (task_dir / _NETWORK_HAR_FILE).exists()
        return has_agent_response and has_network_har

    def _load_submission_metadata(self) -> dict[str, Any]:
        submission_path = self.submission_dir / _SUBMISSION_FILE_NAME
        try:
            payload = json.loads(submission_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {_SUBMISSION_FILE_NAME}: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError(f"{_SUBMISSION_FILE_NAME} must contain a JSON object")

        required_fields = ("name", "model", "leaderboard", "reference", "contact_email", "packaged_tasks")
        missing_fields = [field for field in required_fields if field not in payload]
        if missing_fields:
            raise ValueError(f"Missing required {_SUBMISSION_FILE_NAME} field(s): {', '.join(missing_fields)}")

        placeholder_field = self._find_placeholder_field(payload)
        if placeholder_field is not None:
            raise ValueError(
                f"{_SUBMISSION_FILE_NAME} contains placeholder value for '{placeholder_field}'. "
                "Please edit submission.json before submitting."
            )

        validation_payload: dict[str, Any] = {
            "name": payload.get("name"),
            "model": payload.get("model"),
            "leaderboard": payload.get("leaderboard"),
            "reference": payload.get("reference"),
            "code_repository": payload.get("code_repository"),
            "contact_email": payload.get("contact_email"),
            "created_at_utc": self._now_utc_z(),
            "packaging_summary": {
                "tasks_packaged": 0,
                "tasks_with_issues": 0,
                "duplicate_tasks": 0,
                "unknown_tasks": 0,
                "missing_from_output": 0,
            },
        }
        try:
            validated = IntakeSubmission.model_validate(validation_payload)
        except ValidationError as exc:
            raise ValueError(f"Invalid submission metadata: {exc}") from exc

        packaged_tasks = self._validate_packaged_tasks(
            leaderboard=validated.leaderboard.value,
            packaged_tasks=payload.get("packaged_tasks"),
        )

        return {
            "name": validated.name,
            "model": validated.model,
            "leaderboard": validated.leaderboard.value,
            "reference": validated.reference,
            "code_repository": validated.code_repository,
            "contact_email": validated.contact_email,
            "packaged_tasks": packaged_tasks,
        }

    def _validate_packaged_tasks(self, *, leaderboard: str, packaged_tasks: Any) -> dict[str, dict[str, int]]:
        if not isinstance(packaged_tasks, dict):
            raise ValueError("submission.json field 'packaged_tasks' must be a JSON object")

        keys = set(packaged_tasks.keys())
        if not keys.issubset({"full", "hard"}):
            raise ValueError("submission.json field 'packaged_tasks' can only contain 'full' and/or 'hard' keys")

        required_keys = {leaderboard} if leaderboard in {"full", "hard"} else {"full", "hard"}
        if keys != required_keys:
            required = ", ".join(sorted(required_keys))
            found = ", ".join(sorted(keys))
            raise ValueError(
                f"submission.json field 'packaged_tasks' must contain exactly [{required}] for leaderboard '{leaderboard}'. "
                f"Found [{found}]"
            )

        validated: dict[str, dict[str, int]] = {}
        for board, stats in packaged_tasks.items():
            if not isinstance(stats, dict):
                raise ValueError(f"submission.json packaged_tasks.{board} must be an object")

            missing_stats_fields = [key for key in _PACKAGED_TASKS_KEYS if key not in stats]
            if missing_stats_fields:
                raise ValueError(
                    f"submission.json packaged_tasks.{board} is missing field(s): {', '.join(missing_stats_fields)}"
                )

            typed_stats: dict[str, int] = {}
            for key in _PACKAGED_TASKS_KEYS:
                value = stats.get(key)
                if not isinstance(value, int) or value < 0:
                    raise ValueError(f"submission.json packaged_tasks.{board}.{key} must be a non-negative integer")
                typed_stats[key] = value

            if typed_stats["valid"] + typed_stats["incomplete"] + typed_stats["missing"] != typed_stats["expected"]:
                raise ValueError(
                    f"submission.json packaged_tasks.{board} is invalid: "
                    "valid + incomplete + missing must equal expected"
                )

            if typed_stats["valid"] == 0:
                raise ValueError(f"submission.json packaged_tasks.{board}.valid must be greater than 0")

            validated[board] = typed_stats

        return validated

    def _find_placeholder_field(self, value: Any, path: str = "") -> str | None:
        if isinstance(value, str):
            return path if "<EDIT:" in value else None

        if isinstance(value, dict):
            for key, nested_value in value.items():
                next_path = f"{path}.{key}" if path else str(key)
                nested_match = self._find_placeholder_field(nested_value, next_path)
                if nested_match is not None:
                    return nested_match
            return None

        if isinstance(value, list):
            for index, nested_value in enumerate(value):
                next_path = f"{path}[{index}]" if path else f"[{index}]"
                nested_match = self._find_placeholder_field(nested_value, next_path)
                if nested_match is not None:
                    return nested_match
            return None

        return None

    def _compute_packaging_summary(
        self,
        *,
        task_dirs: list[Path],
        submission_metadata: dict[str, Any],
    ) -> IntakePackagingSummary:
        leaderboard = submission_metadata["leaderboard"]
        stats_by_board = submission_metadata["packaged_tasks"]
        selected_board = "full" if leaderboard == "both" else leaderboard
        selected_stats = stats_by_board[selected_board]

        tasks_packaged = len(task_dirs)
        if tasks_packaged != selected_stats["valid"]:
            raise ValueError(
                "submission.json packaged task stats do not match package contents: "
                f"expected {selected_stats['valid']} valid {selected_board} tasks, found {tasks_packaged}"
            )

        return IntakePackagingSummary(
            tasks_packaged=tasks_packaged,
            tasks_with_issues=selected_stats["incomplete"],
            duplicate_tasks=0,
            unknown_tasks=0,
            missing_from_output=selected_stats["missing"],
        )

    def _prepare_staging(
        self,
        *,
        staging_dir: Path,
        task_dirs: list[Path],
        submission_metadata: dict[str, Any],
        packaging_summary: IntakePackagingSummary,
    ) -> int:
        tasks_root = staging_dir / _TASKS_DIR_NAME
        tasks_root.mkdir(parents=True, exist_ok=True)

        for task_dir in task_dirs:
            shutil.copytree(task_dir, tasks_root / task_dir.name)

        created_at_utc = self._now_utc_z()
        source_submission_path = self.submission_dir / _SUBMISSION_FILE_NAME
        staged_submission_path = staging_dir / _SUBMISSION_FILE_NAME
        shutil.copy2(source_submission_path, staged_submission_path)

        submission_payload = json.loads(staged_submission_path.read_text(encoding="utf-8"))
        if not isinstance(submission_payload, dict):
            raise ValueError(f"{_SUBMISSION_FILE_NAME} must contain a JSON object")

        submission_payload["name"] = submission_metadata["name"]
        submission_payload["model"] = submission_metadata["model"]
        submission_payload["leaderboard"] = submission_metadata["leaderboard"]
        submission_payload["reference"] = submission_metadata["reference"]
        submission_payload["code_repository"] = submission_metadata["code_repository"]
        submission_payload["contact_email"] = submission_metadata["contact_email"]
        submission_payload["created_at_utc"] = created_at_utc
        submission_payload["packaging_summary"] = packaging_summary.model_dump(mode="json")
        submission_payload.pop("packaged_tasks", None)

        submission = IntakeSubmission.model_validate(submission_payload)
        staged_submission_path.write_text(submission.model_dump_json(indent=2) + "\n", encoding="utf-8")

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
