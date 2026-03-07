# Lane C - PR Gate Workflow (Read-only)

## Goal

Validate intake payload and compute score preview without mutating branch state.

## Tasks

- [x] C01 Implement PR Gate trigger (`deps: A04,B01`)
  - `pull_request` on `leaderboard-submissions`
  - Path filters under `submissions/inbox/**`
  - Implemented in `.github/workflows/leaderboard-pr-gate.yml`

- [x] C02 Enforce read-only execution (`deps: A05`)
  - No branch writes
  - No HF writes
  - Enforced via workflow permissions `contents: read` and checkout `persist-credentials: false`

- [x] C03 Validate intake structure (`deps: B01`)
  - Exactly one intake folder per PR
  - Required files present
  - Implemented in `dev/leaderboard/pr_gate_intake_validator.py`

- [x] C04 Validate manifest integrity (`deps: B03`)
  - Recompute hash/size for declared files
  - Compare with `manifest.json`
  - Implemented in `dev/leaderboard/pr_gate_intake_validator.py`

- [x] C05 Validate task invariants (`deps: B01`)
  - `.missing` xor (`agent_response.json` + `network.har`)
  - Implemented in `dev/leaderboard/pr_gate_intake_validator.py`

- [x] C06 Compute scoring preview (`deps: B05`)
  - Use pinned evaluator package version
  - Emit result in check summary/comment
  - Implemented via `dev/leaderboard/pr_gate_intake_validator.py` + `.github/workflows/leaderboard-pr-gate.yml`

- [x] C07 Improve failure diagnostics (`deps: C03,C04,C05,C06`)
  - Actionable, path-specific errors
  - Error codes/path-specific messages surfaced in validator output and gate summary

## Outputs

- PR Gate workflow ready and required-check compatible
- Deterministic score preview in PR checks

## Detailed implementation plan

- See `.wip/lane-c-pr-gate-implementation-plan.md` for code-level signatures, module boundaries, interaction diagrams, and test matrix.
