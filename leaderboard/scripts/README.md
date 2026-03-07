## Leaderboard Ingestion

Leaderboard ingestion is HF-direct with control records on `leaderboard-submissions`.

- Intake path: `submissions/inbox/pr-<hf_pr_number>/...`
- HF ingest: `inv dev.leaderboard.hf-ingest`
- Control records: `submission_control/<submission_id>.json`
- Canonical records: `submissions/<submission_id>.json`
- Rebuild: `inv dev.leaderboard.rebuild-canonical` regenerates `leaderboard_full.*.json`, `leaderboard_hard.*.json`, and `leaderboard_manifest.json`
