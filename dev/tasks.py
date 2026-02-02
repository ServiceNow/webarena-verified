"""GitHub CLI helper tasks.

Usage:
    inv -r dev --list
    inv -r dev pr-comments-dump                  # Uses PR for current branch
    inv -r dev pr-comments-dump --pr-number 123  # Uses specific PR
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

from invoke import Collection, Context, task

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_repo_info() -> tuple[str, str]:
    """Get owner and repo name from gh CLI."""
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "owner,name"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return data["owner"]["login"], data["name"]


def _get_pr_number_for_current_branch() -> int:
    """Get PR number for the current branch."""
    result = subprocess.run(
        ["gh", "pr", "view", "--json", "number"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return data["number"]


def _generate_summary(output_dir: Path, pr_number: int) -> Path:
    """Generate summary MD file from dumped comments."""
    template_path = TEMPLATES_DIR / "pr-fixes-summary.md"
    template = template_path.read_text()

    owner, repo = _get_repo_info()

    # Parse review comments (inline code comments)
    checklist_items = []
    comments_detail = []

    for comment_file in sorted(output_dir.glob("review_comment_*.json")):
        comment = json.loads(comment_file.read_text())
        path = comment.get("path", "unknown")
        line = comment.get("line") or comment.get("original_line", "?")
        body = comment["body"]
        first_line = body.split("\n")[0][:80]  # First line, truncated

        checklist_items.append(f"- [ ] `{path}:{line}` - {first_line}")
        comments_detail.append(f"### `{path}:{line}`\n\n{body}\n")

    # Parse PR conversation comments
    pr_comment_files = list(output_dir.glob("comment_*.json"))
    for comment_file in sorted(pr_comment_files):
        comment = json.loads(comment_file.read_text())
        body = comment["body"]
        first_line = body.split("\n")[0][:80]
        author = comment.get("author", {}).get("login", "unknown")

        checklist_items.append(f"- [ ] (conversation) @{author}: {first_line}")
        comments_detail.append(f"### Conversation comment by @{author}\n\n{body}\n")

    review_comment_count = len(list(output_dir.glob("review_comment_*.json")))
    pr_comment_count = len(pr_comment_files)

    # Fill template
    summary = template.format(
        pr_number=pr_number,
        timestamp=datetime.now().isoformat(),
        pr_url=f"https://github.com/{owner}/{repo}/pull/{pr_number}",
        total_comments=len(checklist_items),
        review_comments=review_comment_count,
        pr_comments=pr_comment_count,
        checklist="\n".join(checklist_items) or "No comments to address",
        comments_detail="\n---\n".join(comments_detail) or "No details",
    )

    summary_path = output_dir / "SUMMARY.md"
    summary_path.write_text(summary)
    return summary_path


@task(
    help={
        "pr_number": "Pull request number (optional, defaults to PR for current branch)",
    },
    optional=["pr_number"],
)
def pr_comments_dump(ctx: Context, pr_number: int | None = None) -> None:
    """Dump PR comments to ./tmp/pr-comments-<pr_number>-<timestamp>/"""
    if pr_number is None:
        pr_number = _get_pr_number_for_current_branch()
        print(f"Using PR #{pr_number} for current branch")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"./tmp/pr-comments-{pr_number}-{ts}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fetch PR conversation comments
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "comments"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    comments = data.get("comments", [])

    for i, comment in enumerate(comments):
        comment_file = output_dir / f"comment_{i:03d}.json"
        comment_file.write_text(json.dumps(comment, indent=2))

    # Fetch inline review comments
    result = subprocess.run(
        ["gh", "api", "repos/{owner}/{repo}/pulls/" + str(pr_number) + "/comments"],
        capture_output=True,
        text=True,
        check=True,
    )
    review_comments = json.loads(result.stdout)

    for i, comment in enumerate(review_comments):
        comment_file = output_dir / f"review_comment_{i:03d}.json"
        comment_file.write_text(json.dumps(comment, indent=2))

    print(f"Dumped {len(comments)} PR comments and {len(review_comments)} review comments to {output_dir}")

    # Generate summary
    summary_path = _generate_summary(output_dir, pr_number)
    print(f"Generated summary: {summary_path}")


# Namespace for standalone use with inv -r
ns = Collection()
ns.add_task(pr_comments_dump)
