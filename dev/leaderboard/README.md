## Leaderboard Ingestion

Leaderboard ingestion is PR-based on the `leaderboard-submissions` branch.

- Intake path: `submissions/inbox/<intake_id>/...` in a submission PR
- PR gate: `inv dev.leaderboard.pr-gate-intake-validate`
- Finalization: `inv dev.leaderboard.finalize` writes `submissions/<submission_id>.json` and removes merged inbox payload
- Rebuild: `inv dev.leaderboard.rebuild-canonical` regenerates `leaderboard_full.*.json`, `leaderboard_hard.*.json`, and `leaderboard_manifest.json`
