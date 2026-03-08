from __future__ import annotations

import json
from pathlib import Path

from huggingface_hub import HfApi

from leaderboard.scripts.hf_ingest import ingest_hf_submission


def _list_recent_hf_pr_heads(*, hf_repo: str, hf_token: str) -> dict[int, str]:
    refs = HfApi(token=hf_token or None).list_repo_refs(repo_id=hf_repo, repo_type="dataset")
    head_by_pr_number: dict[int, str] = {}
    for ref in refs.pull_requests or []:
        suffix = ref.ref.replace("refs/pr/", "")
        if suffix.isdigit():
            head_by_pr_number[int(suffix)] = ref.target_commit
    return head_by_pr_number


def sync_submissions(
    *,
    repo_root: Path,
    hf_repo: str,
    hf_token: str,
    evaluator_version: str,
    max_recent_refs: int = 50,
) -> list[int]:
    if not hf_repo.strip() or not hf_token.strip():
        raise ValueError("hf_repo and hf_token are required")
    if max_recent_refs < 1:
        raise ValueError("max_recent_refs must be >= 1")

    head_by_pr_number = _list_recent_hf_pr_heads(hf_repo=hf_repo, hf_token=hf_token)
    selected_numbers = sorted(head_by_pr_number.keys(), reverse=True)[:max_recent_refs]

    processed: list[int] = []
    for pr_number in selected_numbers:
        event_payload = {
            "client_payload": {
                "event_id": f"sync-{pr_number}-{head_by_pr_number[pr_number]}",
                "event_scope": "schedule",
                "event_action": "sync_submissions",
                "hf_repo": hf_repo,
                "hf_pr_number": pr_number,
                "hf_head_sha": head_by_pr_number[pr_number],
                "hf_pr_url": f"https://huggingface.co/datasets/{hf_repo}/discussions/{pr_number}",
            }
        }
        event_path = repo_root / ".tmp" / f"sync-{pr_number}.json"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(json.dumps(event_payload), encoding="utf-8")
        ingest_hf_submission(
            repo_root=repo_root,
            event_path=event_path,
            hf_repo_expected=hf_repo,
            hf_token=hf_token,
            evaluator_version=evaluator_version,
        )
        processed.append(pr_number)
    return processed
