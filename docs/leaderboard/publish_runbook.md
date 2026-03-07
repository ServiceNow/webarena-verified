# Leaderboard Runbook (Canonical Rebuild)

This runbook covers canonical rebuild and atomic publish on `leaderboard-submissions`.

## Scope
Managed artifacts:
- `submissions/*.json`
- `leaderboard_manifest.json`
- `leaderboard_full.<generation_id>.json`
- `leaderboard_hard.<generation_id>.json`

## Operating Model
- Trigger: `.github/workflows/leaderboard-rebuild.yml`.
- Trigger sources: finalize success (`workflow_run`) or manual dispatch.
- Single writer concurrency: `leaderboard-data-writer`, no cancellation in progress.

## Manual Rebuild

```bash
uv run inv dev.leaderboard.rebuild-canonical \
  --repo-root . \
  --canonical-dir submissions \
  --staging-dir .tmp/leaderboard-staging \
  --max-canonical-records 100
```

Output includes:
- `generation_id`
- `full_file`
- `hard_file`
- `canonical_count_before`
- `canonical_count_after`

## Atomic Publish Contract
1. Stage full/hard files first.
2. Validate schema + hashes in staging.
3. Copy generation assets first.
4. Switch manifest last.
5. On publish failure, keep prior live manifest unchanged.

## Smoke Checks

```bash
curl -fsSL https://raw.githubusercontent.com/<org>/<repo>/leaderboard-submissions/leaderboard_manifest.json > /tmp/manifest.json
jq -r '.full_file,.hard_file' /tmp/manifest.json
curl -fsSL "https://raw.githubusercontent.com/<org>/<repo>/leaderboard-submissions/$(jq -r '.full_file' /tmp/manifest.json)" > /tmp/full.json
curl -fsSL "https://raw.githubusercontent.com/<org>/<repo>/leaderboard-submissions/$(jq -r '.hard_file' /tmp/manifest.json)" > /tmp/hard.json
```

## Retry/Failure Guidance
- Invalid canonical record shape halts rebuild with actionable error.
- Retention pruning keeps latest 100 by `eval_completed_at_utc desc`, tie `submission_id desc`.
- Re-running rebuild without canonical changes is deterministic.

## Rollback
1. Identify last known-good commit on `leaderboard-submissions`.
2. Restore `leaderboard_manifest.json` and referenced generation files.
3. Re-run smoke checks.
