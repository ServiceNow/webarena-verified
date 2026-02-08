# Parallel Worktree Tracker

## Goal
Run parallel implementation tracks in separate worktrees, then merge all tracks back into this integration worktree:
- `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/add-leadearboard-site`

## Track Worktrees

### Track A: Control Plane + Post-Merge Transition
- Worktree: `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/leaderboard-track-a-control`
- Branch: `codex/leaderboard-track-a-control`
- Task file: `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/leaderboard-track-a-control/Task.md`
- Scope:
  - pending/processed control file mechanics
  - path/status invariants
  - terminal transitions and tests

### Track B: Submission PR CI Validation
- Worktree: `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/leaderboard-track-b-ci`
- Branch: `codex/leaderboard-track-b-ci`
- Task file: `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/leaderboard-track-b-ci/Task.md`
- Scope:
  - PR validation workflow
  - HF linkage and payload checks
  - rate-limit checks via GitHub API

### Track C: Leaderboard Site Integration
- Worktree: `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/leaderboard-track-c-site`
- Branch: `codex/leaderboard-track-c-site`
- Task file: `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/leaderboard-track-c-site/Task.md`
- Scope:
  - Astro site promotion to `leaderboard-site/`
  - manifest-first loading
  - fixed per-site columns + UX hardening

### Track D: Atomic Publish + Docs + E2E
- Worktree: `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/leaderboard-track-d-docs-e2e`
- Branch: `codex/leaderboard-track-d-docs-e2e`
- Task file: `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/leaderboard-track-d-docs-e2e/Task.md`
- Scope:
  - atomic publish behavior
  - rollback/smoke checks
  - docs and E2E hardening

## Shared Spec References
All tracks must use the same contract sources:
- `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/add-leadearboard-site/leaderboard/spec/leaderboard_submission_spec.md`
- `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/add-leadearboard-site/leaderboard/spec/leaderboard_page_spec.md`
- `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/add-leadearboard-site/leaderboard/spec/leaderboard_flows.md`
- `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/add-leadearboard-site/leaderboard/spec/implementation_tasks.md`

## Execution Rules
1. Rebase each track branch on top of latest integration base before opening final merge.
2. Keep changes scoped to each Task.md to reduce merge conflicts.
3. Do not modify locked decisions from Phase 0 unless explicitly approved.
4. Run local lint/tests in each worktree before merge request.

## Merge Order (Recommended)
1. Track A (`codex/leaderboard-track-a-control`)
2. Track B (`codex/leaderboard-track-b-ci`)
3. Track C (`codex/leaderboard-track-c-site`)
4. Track D (`codex/leaderboard-track-d-docs-e2e`)

Rationale:
- A provides control-plane primitives.
- B consumes A contracts.
- C is mostly independent UI work.
- D finalizes publish/docs/E2E and should run after A/B/C are visible.

## Merge Procedure (into this worktree)
From `/Users/amine.elhattami/workspace/webarena-verified/public/worktrees/add-leadearboard-site`:

```bash
# Keep integration branch current
git checkout add-leadearboard-site

# Merge A
git merge --no-ff codex/leaderboard-track-a-control

# Verify
.venv/bin/ruff check src tests .github/workflows
.venv/bin/pytest

# Merge B
git merge --no-ff codex/leaderboard-track-b-ci

# Verify
.venv/bin/ruff check src tests .github/workflows
.venv/bin/pytest

# Merge C
git merge --no-ff codex/leaderboard-track-c-site

# Verify
.venv/bin/ruff check src tests .github/workflows leaderboard-site
.venv/bin/pytest

# Merge D
git merge --no-ff codex/leaderboard-track-d-docs-e2e

# Final verify
.venv/bin/ruff check src tests .github/workflows leaderboard/spec leaderboard-site
.venv/bin/pytest
```

## Conflict Handling
1. Prefer canonical models under `src/webarena_verified/types/leaderboard/`.
2. If CI/workflow conflicts arise, preserve stricter checks (fail-closed behavior).
3. If site schema conflicts arise, schema in canonical models wins.
4. Re-run full verification after every manual conflict resolution.

## Done Criteria (Program-level)
1. Control-plane invariants enforced and tested.
2. Submission PR CI validation active and deterministic.
3. Site reads manifest-first and shows blocking error + retry on manifest failure.
4. Publish flow enforces atomic manifest switch semantics.
5. Specs and docs reflect implemented behavior.
