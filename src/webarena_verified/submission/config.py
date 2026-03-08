from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SubmissionFlowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    manifest_file_name: str = "manifest.json"
    submission_file_name: str = "submission.json"
    internal_file_name: str = "_internal.json"
    evaluation_summary_file_name: str = "evaluation_summary.json"
    task_agent_response_file_name: str = "agent_response.json"
    task_network_file_name: str = "network.har"
    submission_root_dir: str = "submissions"
    leaderboard_root_dir: str = "leaderboard"
    leaderboard_generations_dir: str = "generations"
    leaderboard_latest_file_name: str = "latest.json"
    generation_full_file_name: str = "full.json"
    generation_hard_file_name: str = "hard.json"
    checksum_algo: str = "sha256"
    source_sha_placeholder: str | None = None
    generation_prefix: str = "gen"
    hard_subset_name: str = "webarena-verified-hard"
    source_submission_url_template: str = (
        "https://huggingface.co/datasets/{hf_repo}/tree/{source_sha}/{submission_path}"
    )
    max_submission_records: int = Field(default=100, ge=1)

    def submission_dataset_path(self, submission_uid: str) -> str:
        return f"{self.submission_root_dir}/{submission_uid}"

    def leaderboard_generation_dir(self, generation_id: str) -> Path:
        return Path(self.leaderboard_root_dir) / self.leaderboard_generations_dir / generation_id
