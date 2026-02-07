# Leaderboard Publish Runbook

This runbook covers atomic leaderboard generation/publish for `gh-pages` and rollback-safe operations.

## Scope

This runbook covers only leaderboard publish artifacts:

- `leaderboard/data/leaderboard_manifest.json`
- `leaderboard/data/leaderboard_full.<generation_id>.json`
- `leaderboard/data/leaderboard_hard.<generation_id>.json`

No other files should be modified by leaderboard publishing.

## Atomic Publish Contract

Publish must obey all of the following:

1. Generate `full` and `hard` files in staging first.
2. Validate schemas and file hashes in staging.
3. Upload/copy generation assets first.
4. Switch manifest last.
5. Never switch the live manifest on a failed publish.
6. Keep only manifest + referenced generation files in `leaderboard/data/`.

The implementation is in `dev/leaderboard/publish.py`.

## Operational Steps

1. Prepare a generation in a clean staging directory.
2. Run generation + manifest creation.
3. Run publish with atomic swap semantics into a local `gh-pages` checkout.
4. Commit and push in a single commit.

Example (from repo root):

```bash
uv run inv dev.leaderboard.publish-from-processed \
  --processed-dir leaderboard/data/submissions/processed \
  --staging-dir /tmp/leaderboard-staging \
  --gh-pages-root /tmp/gh-pages-checkout \
  --generation-id gen-EXAMPLE \
  --generated-at-utc 2026-02-07T00:00:00Z
```

## Smoke Checks

After publish and push, verify:

```bash
curl -fsSL https://<org>.github.io/<repo>/leaderboard/data/leaderboard_manifest.json > /tmp/manifest.json
jq -r '.full_file,.hard_file' /tmp/manifest.json
curl -fsSL "https://<org>.github.io/<repo>/leaderboard/data/$(jq -r '.full_file' /tmp/manifest.json)" > /tmp/full.json
curl -fsSL "https://<org>.github.io/<repo>/leaderboard/data/$(jq -r '.hard_file' /tmp/manifest.json)" > /tmp/hard.json
```

Expected:

- All `curl` commands return HTTP 200.
- `leaderboard_manifest.json` references files that exist and parse as leaderboard table schemas.

## Rollback Procedure

If a bad generation is published:

1. Identify the last known-good `gh-pages` commit.
2. Check out that commit in a temporary branch.
3. Re-push `gh-pages` to that commit.
4. Re-run smoke checks to confirm restoration.

Because publish is manifest-gated and atomic, rollback is a single branch reset/redeploy operation.
