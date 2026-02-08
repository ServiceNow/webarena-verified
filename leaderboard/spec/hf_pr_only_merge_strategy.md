# HF-PR-Only Migration Merge Strategy

## Objective
Merge HF-PR-only submission processing incrementally, with the final step being user-facing CLI submission changes.

## Strategy
Use a strangler approach: add the new scheduled HF ingestion path first, run it in parallel with the existing GitHub-submission-PR path, then cut over. Keep CLI changes last.

## PR Sequence

## PR1: Core HF Validator Extraction (No Behavior Change)
1. Extract reusable HF payload validation logic from:
   - `dev/leaderboard/submission_pr_validator.py`
2. Add a new shared module (e.g. `dev/leaderboard/hf_validator.py`) for:
   - HF PR open-state checks.
   - payload checksum/schema validation.
   - archive/task/HAR validation.
3. Keep all existing workflows unchanged.

Acceptance:
1. Existing workflows behave exactly as before.
2. New unit tests cover extracted validator behavior.

## PR2: Scheduled HF Sync Workflow (Dry-Run)
1. Add `.github/workflows/leaderboard-hf-sync.yml` with:
   - `schedule`
   - `workflow_dispatch`
2. Poll HF PR/discussion candidates and validate them.
3. Do not merge/write/publish yet (`dry-run` only).
4. Output summary metrics (candidates, valid, invalid, skipped).

Acceptance:
1. Workflow runs reliably on schedule and manual trigger.
2. Zero side effects on repository branches.

## PR3: Enable Control-Plane Writes
1. Enable accepted/rejected processing in HF sync:
   - write records via `dev/leaderboard/submission_control_plane.py`.
2. Add idempotency guards:
   - skip already processed HF PRs/submission IDs.
3. Keep old GitHub-submission-PR flow active.

Acceptance:
1. Scheduled sync writes deterministic control records.
2. Re-runs do not duplicate records or transitions.

## PR4: Wire Leaderboard Publish from Scheduled Path
1. Trigger publish from newly written processed records.
2. Reuse existing atomic publisher:
   - `.github/workflows/leaderboard-publish.yml`
   - `dev/leaderboard/publish.py`
3. Keep smoke checks active:
   - `.github/workflows/leaderboard-smoke.yml`

Acceptance:
1. Scheduled ingestion updates `gh-pages` through atomic publish.
2. Smoke checks pass post-publish.

## PR5: Cutover Ingestion (Disable Old GH Submission PR Path)
1. Disable/remove:
   - `.github/workflows/leaderboard-submission-pr-validate.yml`
   - `.github/workflows/leaderboard-post-merge-transition.yml`
2. Keep:
   - control-plane validation
   - publish workflow
   - smoke workflow

Acceptance:
1. No workflow depends on GitHub submission PR file diffs.
2. HF scheduled flow is the only active ingestion path.

## PR6 (Last): CLI User-Facing Submission Changes
1. Update CLI submission flow to HF-only submission path.
2. Remove/disable GitHub submission PR creation in CLI.
3. Ensure output artifacts and linkage fields remain compatible.

Acceptance:
1. User-facing CLI behavior matches new HF-only architecture.
2. End-to-end submission -> publish still passes.

## PR7: Documentation and Spec Finalization
1. Update:
   - `leaderboard/spec/leaderboard_submission_spec.md`
   - `leaderboard/spec/leaderboard_flows.md`
   - `leaderboard/spec/implementation_tasks.md`
   - `docs/leaderboard/publish_runbook.md`
2. Remove references to GitHub submission PR ingestion.
3. Document scheduled cadence and retry/idempotency model.

Acceptance:
1. Docs reflect actual production behavior.
2. Maintainer runbook is sufficient for operations and rollback.

## Rollback Guidance
1. Keep old ingestion workflows until PR5 lands.
2. If issues occur before PR5, disable scheduled HF write path and continue existing GH submission flow.
3. After PR5, rollback by temporarily re-enabling previous workflows from prior commit.

## Why This Order
1. Minimizes production risk by introducing non-destructive visibility first.
2. Validates HF integration before branch-writing and publish side effects.
3. Keeps user-facing CLI changes last, after backend architecture is proven stable.
