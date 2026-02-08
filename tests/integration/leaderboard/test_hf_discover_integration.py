from __future__ import annotations

import os
import time
import uuid
import re

import pytest
from huggingface_hub import HfApi
from huggingface_hub.errors import HfHubHTTPError

from dev.leaderboard.constants import HF_SUBMISSION_DISCUSSION_TITLE_PREFIX
from dev.leaderboard.utils.hf_sync import discover_submission_prs

HF_DISCOVER_TEST_REPO = "AmineHA/Webarena-Verified-Submissions-dev"


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
def setup_test_prs(hf_api: HfApi, hf_token: str) -> dict[str, int]:
    nonce = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    matching_open_title = f"{HF_SUBMISSION_DISCUSSION_TITLE_PREFIX}discover-it-open-{nonce}"
    non_matching_closed_title = f"Not a submission discover-it-closed-{nonce}"
    matching_closed_title = f"{HF_SUBMISSION_DISCUSSION_TITLE_PREFIX}discover-it-closed-{nonce}"
    created_ids: list[int] = []

    def _create_pr(title: str, description: str) -> int:
        try:
            discussion = hf_api.create_discussion(
                repo_id=HF_DISCOVER_TEST_REPO,
                title=title,
                description=description,
                pull_request=True,
                repo_type="dataset",
                token=hf_token,
            )
            return int(discussion.num)
        except HfHubHTTPError as exc:
            existing = re.search(r"Discussion #(\d+) already exists", str(exc))
            if not existing:
                raise
            return int(existing.group(1))

    def _close_pr(pr_id: int, comment: str) -> None:
        try:
            hf_api.change_discussion_status(
                repo_id=HF_DISCOVER_TEST_REPO,
                discussion_num=pr_id,
                new_status="closed",
                repo_type="dataset",
                token=hf_token,
                comment=comment,
            )
        except HfHubHTTPError as exc:
            if "already has status closed" not in str(exc):
                raise

    def _open_pr(pr_id: int, comment: str) -> None:
        try:
            hf_api.change_discussion_status(
                repo_id=HF_DISCOVER_TEST_REPO,
                discussion_num=pr_id,
                new_status="open",
                repo_type="dataset",
                token=hf_token,
                comment=comment,
            )
        except HfHubHTTPError as exc:
            if "already has status open" not in str(exc):
                raise

    matching_closed_id = _create_pr(
        title=matching_closed_title,
        description="integration test fixture: matching closed discover PR",
    )
    created_ids.append(matching_closed_id)
    _close_pr(matching_closed_id, "integration test setup: close matching PR")

    non_matching_closed_id = _create_pr(
        title=non_matching_closed_title,
        description="integration test fixture: non-matching closed discover PR",
    )
    created_ids.append(non_matching_closed_id)
    hf_api.rename_discussion(
        repo_id=HF_DISCOVER_TEST_REPO,
        discussion_num=non_matching_closed_id,
        new_title=non_matching_closed_title,
        repo_type="dataset",
        token=hf_token,
    )
    _close_pr(non_matching_closed_id, "integration test setup: close non-matching PR")

    matching_open_id = _create_pr(
        title=matching_open_title,
        description="integration test fixture: matching open discover PR",
    )
    created_ids.append(matching_open_id)
    hf_api.rename_discussion(
        repo_id=HF_DISCOVER_TEST_REPO,
        discussion_num=matching_open_id,
        new_title=matching_open_title,
        repo_type="dataset",
        token=hf_token,
    )
    _open_pr(matching_open_id, "integration test setup: open matching PR")

    try:
        yield {
            "matching_open_pr_id": matching_open_id,
            "non_matching_closed_pr_id": non_matching_closed_id,
            "matching_closed_pr_id": matching_closed_id,
        }
    finally:
        for pr_id in created_ids:
            try:
                hf_api.change_discussion_status(
                    repo_id=HF_DISCOVER_TEST_REPO,
                    discussion_num=pr_id,
                    new_status="closed",
                    repo_type="dataset",
                    token=hf_token,
                    comment="integration test cleanup",
                )
            except HfHubHTTPError as exc:
                if "already has status closed" not in str(exc):
                    raise


@pytest.mark.integration_hf
def test_discover_submission_prs_contract(hf_token: str, setup_test_prs: dict[str, int]):
    discovered = discover_submission_prs(HF_DISCOVER_TEST_REPO, hf_token)
    assert isinstance(discovered, dict)
    assert isinstance(discovered["count"], int)
    assert isinstance(discovered["matrix"], dict)
    include = discovered["matrix"]["include"]
    assert isinstance(include, list)
    assert discovered["count"] == len(include)

    for item in include:
        assert isinstance(item["hf_pr_id"], int)
        assert isinstance(item["hf_head_sha"], str)

    discovered_ids = {item["hf_pr_id"] for item in include}
    assert setup_test_prs["matching_open_pr_id"] in discovered_ids
    assert setup_test_prs["non_matching_closed_pr_id"] not in discovered_ids
    assert setup_test_prs["matching_closed_pr_id"] not in discovered_ids
