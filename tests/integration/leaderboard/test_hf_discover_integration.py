from __future__ import annotations

import os
import time
import uuid

import pytest
from huggingface_hub import HfApi

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
    matching_title = f"{HF_SUBMISSION_DISCUSSION_TITLE_PREFIX}discover-it-{nonce}"
    non_matching_title = f"Not a submission discover-it-{nonce}"
    created_ids: list[int] = []

    matching = hf_api.create_discussion(
        repo_id=HF_DISCOVER_TEST_REPO,
        title=matching_title,
        description="integration test fixture: matching discover PR",
        pull_request=True,
        repo_type="dataset",
        token=hf_token,
    )
    created_ids.append(int(matching.num))

    non_matching = hf_api.create_discussion(
        repo_id=HF_DISCOVER_TEST_REPO,
        title=non_matching_title,
        description="integration test fixture: non-matching discover PR",
        pull_request=True,
        repo_type="dataset",
        token=hf_token,
    )
    created_ids.append(int(non_matching.num))

    try:
        yield {
            "matching_pr_id": int(matching.num),
            "non_matching_pr_id": int(non_matching.num),
        }
    finally:
        for pr_id in created_ids:
            hf_api.change_discussion_status(
                repo_id=HF_DISCOVER_TEST_REPO,
                discussion_num=pr_id,
                new_status="closed",
                repo_type="dataset",
                token=hf_token,
                comment="integration test cleanup",
            )


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
    assert setup_test_prs["matching_pr_id"] in discovered_ids
    assert setup_test_prs["non_matching_pr_id"] not in discovered_ids
