# Leaderboard System Guide

## Architecture at a glance

1. Authors submit data through Hugging Face dataset PRs.
2. `leaderboard-hf-ingest.yml` runs on schedule, syncs pending HF submissions, evaluates, rebuilds artifacts, then commits directly to `leaderboard-submissions`.
3. `deploy-site.yml` builds MkDocs docs and the leaderboard Astro app, then deploys both to `gh-pages` in a single push.
4. Leaderboard UI reads `leaderboard/latest.json` and generation files from `leaderboard-submissions` via manifest URL.

## Branch roles

- `main`: source code, specs, and docs.
- `leaderboard-submissions`: accepted submissions and leaderboard artifacts.
- `gh-pages`: deployed site — MkDocs docs at `/` and leaderboard app at `/leaderboard/`.

## CI workflows

- `deploy-site.yml`: Unified deploy. Triggers on docs or leaderboard site changes to `main`. Builds docs via `mike deploy` (no push), builds Astro leaderboard app, injects leaderboard dist into `gh-pages` via git worktree, then pushes.
- `leaderboard-site-build.yml`: PR validation only. Runs leaderboard site tests and build on pull requests to catch issues before merge.
- `leaderboard-hf-ingest.yml`: Scheduled HF sync. Ingests submissions, evaluates, rebuilds artifacts, commits to `leaderboard-submissions`.
