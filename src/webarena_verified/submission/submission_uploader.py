from __future__ import annotations

from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi

from .config import SubmissionFlowConfig
from .models import SubmissionUploadResult
from .submission_validator import SubmissionValidator


class SubmissionUploader:
    def __init__(
        self,
        *,
        submission_dir: Path,
        hf_repo: str,
        hf_token: str | None = None,
        flow_config: SubmissionFlowConfig | None = None,
    ) -> None:
        self._submission_dir = submission_dir
        self._hf_repo = hf_repo
        self._hf_token = hf_token
        self._flow_config = flow_config or SubmissionFlowConfig()
        self._validator = SubmissionValidator(self._flow_config)

    def upload(self) -> SubmissionUploadResult:
        submission, _, _ = self._validator.validate_submission_tree(self._submission_dir)
        submission_path = self._flow_config.submission_dataset_path(submission.submission_uid)

        operations: list[CommitOperationAdd] = []
        for file_path in sorted(self._submission_dir.rglob("*")):
            if not file_path.is_file():
                continue
            relative_path = file_path.relative_to(self._submission_dir).as_posix()
            operations.append(
                CommitOperationAdd(
                    path_in_repo=f"{submission_path}/{relative_path}",
                    path_or_fileobj=str(file_path),
                )
            )

        api = HfApi(token=self._hf_token)
        commit_info = api.create_commit(
            repo_id=self._hf_repo,
            repo_type="dataset",
            operations=operations,
            commit_message=f"[Leaderboard Submission] [{submission.submission_uid}] {submission.name}",
            commit_description=self._pr_description(submission.name),
            create_pr=True,
        )
        if commit_info.pr_num is None or not commit_info.pr_url:
            raise ValueError("Unable to resolve created HuggingFace PR metadata")

        return SubmissionUploadResult(
            pr_url=commit_info.pr_url,
            pr_number=commit_info.pr_num,
            submission_uid=submission.submission_uid,
            hf_repo=self._hf_repo,
            submission_dir=str(self._submission_dir),
            tasks_submitted=submission.submitted_tasks,
        )

    @staticmethod
    def _pr_description(submission_name: str) -> str:
        return (
            f"Submission Name: {submission_name}\n\n"
            "For issues, open a repository issue: "
            "https://github.com/ServiceNow/webarena-verified/issues\n\n"
            "---\n\n"
            "> Auto-generated description."
        )
