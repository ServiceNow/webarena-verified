# Leaderboard System Guide

## Architecture at a glance

1. Authors submit data through Hugging Face dataset PRs.
2. `leaderboard-hf-ingest.yml` runs on schedule, syncs pending HF submissions, evaluates, rebuilds artifacts, then commits directly to `leaderboard-submissions`.
3. Leaderboard UI reads `leaderboard/latest.json` and generation files from `leaderboard-submissions`.

## Branch roles

- `main`: source code, specs, and docs.
- `leaderboard-submissions`: accepted submissions and leaderboard artifacts.
- `gh-pages`: docs site artifacts.
