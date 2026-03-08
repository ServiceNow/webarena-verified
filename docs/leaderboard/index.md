# Leaderboard

The WebArena-Verified leaderboard is the public results table for benchmark submissions.
Each entry is produced from deterministic offline evaluation and linked to a submission record.

- Live leaderboard: https://servicenow.github.io/webarena-verified/leaderboard/
- Boards:
  - `WebArena-Verified` (full benchmark, 812 tasks)
  - `WebArena-Verified-Hard` (hard subset, 258 tasks)

## What You Can Inspect

Each row includes:

- Rank
- Name
- Overall Score
- Per-site scores: Shopping, Shopping Admin, Reddit, GitLab, Wikipedia, Map
- Submission ID
- Evaluator Version

## UI Features

- Search and filter by model/team name or submission ID
- Toggle between Full and Hard boards
- Export leaderboard rows as CSV

!!! info
    Evaluation is deterministic and offline. WebArena-Verified does not use LLM-as-judge scoring for leaderboard entries.

## Next Step

To publish results, follow the submission walkthrough: [Submitting Results](submission.md).
