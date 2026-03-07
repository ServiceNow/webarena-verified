# Lane C - PR Gate Workflow (Read-only)

## Goal

Validate intake payload and compute score preview without mutating branch state.

## Tasks

- [ ] C01 Implement PR Gate trigger (`deps: A04,B01`)
  - `pull_request` on `leaderboard-submissions`
  - Path filters under `submissions/inbox/**`

- [ ] C02 Enforce read-only execution (`deps: A05`)
  - No branch writes
  - No HF writes

- [ ] C03 Validate intake structure (`deps: B01`)
  - Exactly one intake folder per PR
  - Required files present

- [ ] C04 Validate manifest integrity (`deps: B03`)
  - Recompute hash/size for declared files
  - Compare with `manifest.json`

- [ ] C05 Validate task invariants (`deps: B01`)
  - `.missing` xor (`agent_response.json` + `network.har`)

- [ ] C06 Compute scoring preview (`deps: B05`)
  - Use pinned evaluator package version
  - Emit result in check summary/comment

- [ ] C07 Improve failure diagnostics (`deps: C03,C04,C05,C06`)
  - Actionable, path-specific errors

## Outputs

- PR Gate workflow ready and required-check compatible
- Deterministic score preview in PR checks
