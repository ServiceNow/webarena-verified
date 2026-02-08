# Leaderboard Flows (HF PR Only, Scheduled)

## Flow A: User Submission (CLI + HF PR)

```text
User
  |
  | webarena-verified submission submit --data-dir ...
  v
[Local Validate + Package]
  - payload.tar.zst
  - payload.sha256
  - metadata.json
  - manifest.json
  |
  v
[Create/Update HF PR]
  - HF dataset repo: submissions/accepted/<submission_id>/
  - hf_pr_id + hf_pr_url recorded in manifest
```

## Flow B: Scheduled HF Sync (GitHub Actions)

```text
Cron / manual dispatch
  |
  v
[List open HF dataset PR discussions]
  |
  v
[Resolve candidate submission_id from refs/pr/<id>/ tree]
  |
  v
[Ensure pending control record]
  - leaderboard/data/submissions/pending/<id>.json
  |
  v
[Validate HF payload]
  - PR open state
  - required files
  - checksum
  - metadata/manifest schema
  - archive extraction
  - task + .missing policy
  - HAR validation
  |
  +--> FAIL:
  |      pending -> processed(rejected) with reason
  |
  +--> PASS:
         merge HF PR
         pending -> processed(accepted)
```

## Flow C: Publish

```text
[Processed control records]
  |
  v
[Generate full/hard tables + manifest]
  |
  v
[Atomic publish to gh-pages]
  - upload generation files first
  - switch manifest last
  - rollback-safe on failure
```

## Flow D: Data Ownership

```text
HF dataset PRs (ingress payload)
  submissions/accepted/<id>/{payload.tar.zst,payload.sha256,metadata.json,manifest.json}
                |
                v
GitHub main (control state)
  leaderboard/data/submissions/pending/<id>.json
  leaderboard/data/submissions/processed/<id>.json
                |
                v
GitHub Pages (published artifacts)
  leaderboard/data/leaderboard_manifest.json
  leaderboard/data/leaderboard_full.<generation_id>.json
  leaderboard/data/leaderboard_hard.<generation_id>.json
```
