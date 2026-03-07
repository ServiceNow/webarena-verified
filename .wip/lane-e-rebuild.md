# Lane E - Rebuild Leaderboard (Single Writer)

## Goal

Single workflow owns retention pruning and leaderboard file generation.

## Tasks

- [ ] E01 Implement rebuild trigger (`deps: D07`)
  - Triggered by finalize success
  - Optional manual dispatch for recovery

- [ ] E02 Enforce single-writer concurrency (`deps: E01`)
  - `concurrency.group: leaderboard-data-writer`
  - `cancel-in-progress: false`

- [ ] E03 Load canonical records (`deps: E01`)
  - Source: `submissions/*.json`
  - Include accepted records for leaderboard rows

- [ ] E04 Prune to latest 100 canonical records (`deps: E03`)
  - Sort by `eval_completed_at_utc desc`, tie `submission_id desc`

- [ ] E05 Generate immutable leaderboard files (`deps: E04,B05`)
  - `leaderboard_full.<generation_id>.json`
  - `leaderboard_hard.<generation_id>.json`

- [ ] E06 Atomic manifest switch (`deps: E05`)
  - Write generation files first
  - Update `leaderboard_manifest.json` last

- [ ] E07 Determinism verification (`deps: E06`)
  - Rebuild without new inputs yields stable output

## Outputs

- Single writer for leaderboard outputs
- Retention policy enforced in branch tip
