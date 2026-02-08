from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tarfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from huggingface_hub import HfApi
from huggingface_hub.community import DiscussionComment
from huggingface_hub.errors import HfHubHTTPError

from dev.leaderboard.constants import LEADERBOARD_SUBMISSIONS_ROOT
from dev.leaderboard.models import SubmissionStatus
from dev.leaderboard.utils.hf_sync import STATUS_COMMENT_MARKER, run_hf_single_pr

HF_TEST_REPO = "AmineHA/Webarena-Verified-Submissions-dev"


def _now_utc_z() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize_repo(repo: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")


def _submission_id(repo: str, hf_pr_id: int) -> str:
    return f"{_sanitize_repo(repo)}-pr-{hf_pr_id}"


def _build_archive_bytes() -> bytes:
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as tar:
        dir_info = tarfile.TarInfo(name="123")
        dir_info.type = tarfile.DIRTYPE
        dir_info.mode = 0o755
        dir_info.mtime = int(time.time())
        tar.addfile(dir_info)

        missing_info = tarfile.TarInfo(name="123/.missing")
        missing_info.size = 0
        missing_info.mode = 0o644
        missing_info.mtime = int(time.time())
        tar.addfile(missing_info, io.BytesIO(b""))
    return data.getvalue()


@pytest.fixture(scope="module")
def hf_token() -> str:
    token = os.getenv("HF_TOKEN")
    if not token:
        raise pytest.UsageError("HF_TOKEN environment variable is required for integration_hf tests.")
    return token


@pytest.fixture(scope="module")
def hf_api(hf_token: str) -> HfApi:
    return HfApi(token=hf_token)


@pytest.fixture
def setup_handle_pr_fixture(hf_api: HfApi, hf_token: str):
    nonce = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    bootstrap_path = f"smoke-tests/{nonce}/bootstrap.txt"
    created_pr_id: int | None = None
    local_record_paths: list[Path] = []

    try:
        try:
            created = hf_api.upload_file(
                path_or_fileobj=b"bootstrap\n",
                path_in_repo=bootstrap_path,
                repo_id=HF_TEST_REPO,
                repo_type="dataset",
                token=hf_token,
                create_pr=True,
                commit_message=f"Leaderboard Submission: hf-handle-pr integration {nonce}",
                commit_description="integration test bootstrap commit",
            )
            pr_url = str(getattr(created, "pr_url", "") or getattr(created, "pull_request_url", ""))
            match = re.search(r"/discussions/(\d+)", pr_url)
            if not match:
                raise RuntimeError(f"Unable to extract PR id from URL: {pr_url}")
            created_pr_id = int(match.group(1))
        except HfHubHTTPError as exc:
            existing = re.search(r"Discussion #(\d+) already exists", str(exc))
            if not existing:
                raise
            created_pr_id = int(existing.group(1))

        submission_id = _submission_id(HF_TEST_REPO, created_pr_id)
        submission_root = f"submissions/accepted/{submission_id}"
        archive_bytes = _build_archive_bytes()
        archive_sha = hashlib.sha256(archive_bytes).hexdigest()
        now = _now_utc_z()

        metadata = {
            "submission_id": submission_id,
            "name": "integration-test/model",
            "leaderboard": "hard",
            "reference": "https://example.com/integration-test",
            "created_at_utc": now,
        }
        manifest = {
            "submission_id": submission_id,
            "archive_file": "submission-payload.tar.gz",
            "archive_sha256": archive_sha,
            "archive_size_bytes": len(archive_bytes),
            "created_at_utc": now,
            "hf_pr_id": created_pr_id,
            "hf_pr_url": f"https://huggingface.co/datasets/{HF_TEST_REPO}/discussions/{created_pr_id}",
        }
        payloads = {
            "submission-payload.tar.gz": archive_bytes,
            "submission-payload.sha256": f"{archive_sha}  submission-payload.tar.gz\n".encode("utf-8"),
            "metadata.json": (json.dumps(metadata, sort_keys=True) + "\n").encode("utf-8"),
            "manifest.json": (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8"),
        }

        for file_name, file_bytes in payloads.items():
            hf_api.upload_file(
                path_or_fileobj=file_bytes,
                path_in_repo=f"{submission_root}/{file_name}",
                repo_id=HF_TEST_REPO,
                repo_type="dataset",
                token=hf_token,
                revision=f"refs/pr/{created_pr_id}",
                commit_message=f"Add {file_name} for integration test",
            )

        hf_api.rename_discussion(
            repo_id=HF_TEST_REPO,
            discussion_num=created_pr_id,
            new_title=f"Leaderboard Submission: hf-handle-pr integration {nonce}",
            repo_type="dataset",
            token=hf_token,
        )
        try:
            hf_api.change_discussion_status(
                repo_id=HF_TEST_REPO,
                discussion_num=created_pr_id,
                new_status="open",
                repo_type="dataset",
                token=hf_token,
                comment="integration test setup: ensure open",
            )
        except HfHubHTTPError as exc:
            if "already has status open" not in str(exc):
                raise

        local_record_paths.extend(
            [
                LEADERBOARD_SUBMISSIONS_ROOT / "accepted" / f"{submission_id}.json",
                LEADERBOARD_SUBMISSIONS_ROOT / "pending" / f"{submission_id}.json",
                LEADERBOARD_SUBMISSIONS_ROOT / "rejected" / f"{submission_id}.json",
            ]
        )

        yield {
            "pr_id": created_pr_id,
            "submission_id": submission_id,
        }
    finally:
        if created_pr_id is not None:
            try:
                hf_api.change_discussion_status(
                    repo_id=HF_TEST_REPO,
                    discussion_num=created_pr_id,
                    new_status="closed",
                    repo_type="dataset",
                    token=hf_token,
                    comment="integration test cleanup",
                )
            except Exception:
                # Already merged/closed is fine for cleanup.
                pass

        for path in local_record_paths:
            if path.exists():
                path.unlink()


@pytest.mark.integration_hf
def test_hf_handle_pr_merges_valid_submission(hf_api: HfApi, setup_handle_pr_fixture: dict[str, object]):
    pr_id = int(setup_handle_pr_fixture["pr_id"])
    submission_id = str(setup_handle_pr_fixture["submission_id"])

    run_hf_single_pr(hf_pr_id=pr_id, merge_accepted=True)

    accepted_record = LEADERBOARD_SUBMISSIONS_ROOT / "accepted" / f"{submission_id}.json"
    assert accepted_record.exists()
    payload = json.loads(accepted_record.read_text(encoding="utf-8"))
    assert payload["status"] == SubmissionStatus.ACCEPTED.value

    details = hf_api.get_discussion_details(
        repo_id=HF_TEST_REPO,
        discussion_num=pr_id,
        repo_type="dataset",
    )
    assert details.status in {"closed", "merged"}

    status_comments = [
        event
        for event in details.events
        if isinstance(event, DiscussionComment) and STATUS_COMMENT_MARKER in (event.content or "")
    ]
    assert status_comments
