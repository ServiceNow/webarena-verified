# Leaderboard Implementation Tasks (HF PR Only)

## Phase 1: Scheduled HF Sync Workflow
1. Add `.github/workflows/leaderboard-hf-sync.yml`.
2. Trigger on `schedule` and `workflow_dispatch`.
3. Run `inv dev.leaderboard.hf-sync`, commit control updates, publish to `gh-pages`.
4. Emit run summary: candidates, accepted, rejected, skipped, pending-retry, generation id.

## Phase 2: Reusable HF Validator
1. Extract HF payload validation to `dev/leaderboard/hf_validator.py`.
2. Keep open-state, checksum, metadata/manifest, extraction, task/.missing, HAR checks.
3. Reuse validator from PR validator and scheduled sync processor.

## Phase 3: HF Sync Processor
1. Add `dev/leaderboard/hf_sync.py`.
2. Add invoke task `dev.leaderboard.hf-sync` in `dev/leaderboard_tasks.py`.
3. Implement idempotent transitions with pending/processed guards.
4. Process each candidate independently so one failure does not block others.

## Phase 4: Retire GitHub Submission PR Ingestion
1. Remove `.github/workflows/leaderboard-submission-pr-validate.yml`.
2. Remove `.github/workflows/leaderboard-post-merge-transition.yml`.
3. Keep control-plane validation workflow push-driven for bot/data updates.

## Phase 5: Publish + Smoke
1. Keep `leaderboard-publish.yml` and `leaderboard-smoke.yml` for publish/smoke coverage.
2. Ensure branch/path filters match the control records branch.

## Phase 6: Docs + Runbook
1. Update submission/flow specs to HF-PR-only scheduled model.
2. Update runbook with schedule cadence and retry model.
