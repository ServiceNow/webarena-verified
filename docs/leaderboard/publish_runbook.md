# Leaderboard Runbook (HF PR Scheduled Processing)

This runbook covers scheduled HF ingestion, control-plane transitions, and atomic publish for `gh-pages`.

## Scope
Managed artifacts:
- `leaderboard/data/submissions/pending/*.json`
- `leaderboard/data/submissions/processed/*.json`
- `leaderboard/data/leaderboard_manifest.json`
- `leaderboard/data/leaderboard_full.<generation_id>.json`
- `leaderboard/data/leaderboard_hard.<generation_id>.json`

## Operating Model
- Ingress: HF dataset PRs only.
- Processor: `.github/workflows/leaderboard-hf-sync.yml`.
- Cadence: scheduled every 6 hours (plus manual dispatch).
- Idempotency: processed ids are skipped; merge failures remain pending and retry on next run.

## Manual Sync
From repo root:

```bash
HF_TOKEN=<token> uv run inv dev.leaderboard.hf-sync \
  --hf-repo <owner>/<dataset> \
  --submissions-root leaderboard/data/submissions
```

Output includes:
- `total_candidates`
- `accepted`
- `rejected`
- `skipped`
- `pending_retry`
- `generation_id`

## Manual Publish

```bash
uv run inv dev.leaderboard.publish-from-processed \
  --processed-dir leaderboard/data/submissions/processed \
  --staging-dir /tmp/leaderboard-staging \
  --gh-pages-root /tmp/gh-pages-checkout
```

## Atomic Publish Contract
1. Stage full/hard files first.
2. Validate schema + hashes in staging.
3. Copy generation assets first.
4. Switch manifest last.
5. On publish failure, keep prior live manifest unchanged.

## Smoke Checks

```bash
curl -fsSL https://<org>.github.io/<repo>/leaderboard/data/leaderboard_manifest.json > /tmp/manifest.json
jq -r '.full_file,.hard_file' /tmp/manifest.json
curl -fsSL "https://<org>.github.io/<repo>/leaderboard/data/$(jq -r '.full_file' /tmp/manifest.json)" > /tmp/full.json
curl -fsSL "https://<org>.github.io/<repo>/leaderboard/data/$(jq -r '.hard_file' /tmp/manifest.json)" > /tmp/hard.json
```

## Retry/Failure Guidance
- Validation failure for a candidate: record transitions to `processed/rejected` with reason.
- HF merge failure: candidate remains pending and is retried on next scheduled run.
- One candidate failure must not block processing others.

## Rollback
1. Identify last known-good `gh-pages` commit.
2. Restore `gh-pages` to that commit.
3. Re-run smoke checks.
