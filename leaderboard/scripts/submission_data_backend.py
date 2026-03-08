"""Backend for submission data retrieval from Hugging Face.

Encapsulates all interactions with the Hugging Face Hub API so that the
main submission-handling logic (``submission_handler``) stays independent
of the concrete data source.  If a different backend is needed in the
future, callers only need to swap this class.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

logger = logging.getLogger(__name__)


class SubmissionDataBackend:
    """Facade over Hugging Face Hub operations used by the ingest pipeline.

    Wraps ``HfApi`` and ``snapshot_download`` behind a small interface so
    that ``submission_handler`` never imports ``huggingface_hub`` directly.
    """

    def __init__(self, hf_token: str) -> None:
        self._token = hf_token or None
        self._api = HfApi(token=self._token)

    def download_submission_snapshot(
        self,
        *,
        repo_id: str,
        revision: str,
    ) -> Path:
        """Download a HF dataset snapshot and return the submissions root.

        Downloads only the ``submissions/`` subtree at the given revision.

        Returns:
            Path to the ``submissions/`` directory inside the snapshot.

        Raises:
            ValueError: If the snapshot does not contain a ``submissions/``
                directory.
        """
        logger.info("Downloading HF snapshot: repo=%s revision=%s", repo_id, revision)
        snapshot_root = Path(
            snapshot_download(
                repo_id=repo_id,
                repo_type="dataset",
                revision=revision,
                token=self._token,
                allow_patterns=["submissions/*", "submissions/*/**"],
            )
        )
        source_root = snapshot_root / "submissions"
        if not source_root.exists():
            raise ValueError("HF snapshot does not contain submissions directory")
        return source_root

    def get_pr_diff(self, *, repo_id: str, pr_number: int) -> str | None:
        """Fetch the diff text of a HF dataset pull request.

        Returns:
            The raw unified-diff string, or ``None`` if unavailable.
        """
        logger.info("Fetching PR diff: repo=%s pr=%d", repo_id, pr_number)
        details = self._api.get_discussion_details(
            repo_id=repo_id,
            discussion_num=pr_number,
            repo_type="dataset",
        )
        return getattr(details, "diff", None)

    def list_pr_refs(self, *, repo_id: str) -> dict[int, str]:
        """List open pull-request refs and their head commit SHAs.

        Returns:
            Mapping of PR number to target commit SHA.
        """
        logger.info("Listing PR refs: repo=%s", repo_id)
        refs = self._api.list_repo_refs(repo_id=repo_id, repo_type="dataset")
        head_by_pr_number: dict[int, str] = {}
        for ref in refs.pull_requests or []:
            suffix = ref.ref.replace("refs/pr/", "")
            if suffix.isdigit():
                head_by_pr_number[int(suffix)] = ref.target_commit
        return head_by_pr_number


def extract_submission_uids_from_diff(diff_text: str) -> set[str]:
    """Parse submission UIDs from a unified diff.

    Looks for paths matching ``submissions/<uid>/`` in diff headers.

    Returns:
        Set of submission UIDs found in the diff.
    """
    uids: set[str] = set()
    pattern = re.compile(r"^diff --git a/submissions/([^/]+)/", re.MULTILINE)
    for match in pattern.finditer(diff_text):
        uids.add(match.group(1))
    return uids
