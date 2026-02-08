# HF-PR-Only Submission Plan (Scheduled Processing)

## Goal
Move submission ingestion from GitHub submission PRs to Hugging Face (HF) dataset PRs only, processed by scheduled GitHub Actions runs a few times per day.

## Target Architecture
1. HF PRs are the only submission ingress.
2. A scheduled GitHub workflow polls HF dataset PRs/discussions.
3. Workflow validates HF payloads, decides accepted/rejected, and writes control records.
4. Leaderboard publish runs from processed control records and updates `gh-pages`.
5. No real-time requirement; idempotent batch runs are the default.

## Phase 1: Introduce Scheduled HF Sync Workflow
### Changes
1. Add a new workflow, e.g. `.github/workflows/leaderboard-hf-sync.yml`.
2. Triggers:
   - `schedule` (e.g. every 6 or 12 hours).
   - `workflow_dispatch`.
3. Workflow steps:
   - checkout + setup.
   - run a new invoke task that polls HF discussions/PRs.
   - validate each candidate submission payload.
   - transition control files to accepted/rejected.
   - invoke publish flow.
4. Emit run summary:
   - total candidates, accepted, rejected, skipped, generation id.

### Acceptance Criteria
1. One manual run can process HF PRs end-to-end without GitHub submission PR input.
2. Re-running with no new HF changes results in no-op behavior.

## Phase 2: Refactor Validation Logic for HF-Only Ingestion
### Changes
1. Extract HF payload validation from `dev/leaderboard/submission_pr_validator.py` into a reusable module (e.g. `dev/leaderboard/hf_validator.py`).
2. Keep/port:
   - HF PR open-state check.
   - required file checks.
   - checksum checks.
   - metadata/manifest schema checks.
   - archive extraction + task structure + HAR checks.
3. Remove ingestion coupling to GitHub PR diff/title/rate-limit for the scheduled path.

### Acceptance Criteria
1. HF validation can run without GitHub PR context.
2. Existing validation guarantees remain intact.

## Phase 3: Add HF Sync Processor Task
### Changes
1. Add a new invoke task in `dev/leaderboard_tasks.py` (e.g. `hf-sync`).
2. Task behavior:
   - list candidate HF discussions/PRs.
   - filter to relevant submission PRs.
   - run validation.
   - merge accepted HF PRs.
   - write/update control records under:
     - `leaderboard/data/submissions/pending/`
     - `leaderboard/data/submissions/processed/`
3. Ensure idempotency:
   - avoid re-processing already finalized submissions.
   - deterministic transitions and safe retries.

### Acceptance Criteria
1. Same HF PR is not processed twice as accepted/rejected.
2. Failures for one candidate do not block processing of others.

## Phase 4: Retire GitHub-Submission-PR Flow
### Changes
1. Disable/remove:
   - `.github/workflows/leaderboard-submission-pr-validate.yml`
   - `.github/workflows/leaderboard-post-merge-transition.yml`
2. Keep `leaderboard-control-plane-validate.yml`, but retarget trigger behavior to the branch used for control records (push-driven, not PR-dependent).

### Acceptance Criteria
1. No workflow depends on GitHub submission PR file diffs.
2. Control-plane invariants are still enforced on every bot/data update.

## Phase 5: Keep Publish + Smoke, Retarget Triggers if Needed
### Changes
1. Keep `leaderboard-publish.yml` as the publisher from processed records to `gh-pages`.
2. If control data branch is not `main`, update publish workflow branch filters accordingly.
3. Keep `leaderboard-smoke.yml` unchanged (or adjust URL if deployment path changes).

### Acceptance Criteria
1. Processed records generate full/hard + manifest correctly.
2. Atomic publish semantics remain unchanged.
3. Smoke checks succeed post-publish.

## Phase 6: Documentation and Spec Updates
### Changes
1. Update:
   - `leaderboard/spec/leaderboard_submission_spec.md`
   - `leaderboard/spec/leaderboard_flows.md`
   - `leaderboard/spec/implementation_tasks.md`
   - `docs/leaderboard/publish_runbook.md`
2. Replace GitHub-submission-PR assumptions with HF-PR scheduled ingestion model.

### Acceptance Criteria
1. Docs reflect actual running architecture.
2. Maintainer runbook includes polling cadence and retry model.

## Data and State Model
1. Keep control files as the durable state machine:
   - pending: `status=pending`
   - processed: `status=accepted|rejected`
2. Store HF linkage fields in records (`hf_repo`, `hf_pr_id`, `hf_pr_url`).
3. Use processed records and/or explicit state markers to guarantee idempotent scheduled runs.

## Migration Strategy
1. Implement scheduled path first while keeping existing workflows.
2. Run both paths temporarily in dry-run/observe mode.
3. Cut over by disabling GitHub-submission-PR workflows after stable scheduled runs.
4. Keep rollback option by re-enabling previous workflows if needed.

## Validation Checklist
1. Unit tests:
   - HF validator module.
   - sync task state transitions.
   - idempotency/retry behavior.
2. Integration tests:
   - accepted HF PR -> processed record -> publish artifacts.
   - rejected HF PR -> rejected processed record with reason.
3. Workflow checks:
   - scheduled workflow success.
   - publish + smoke success.
4. Safety:
   - no manifest switch on publish failure.
   - no duplicate submission id in published rows.

## Risks and Mitigations
1. HF API instability/rate limits:
   - fail closed for merge actions, retry next schedule.
2. Duplicate processing:
   - processed-record guards + explicit idempotency keys.
3. Drift during migration:
   - temporary parallel run window and explicit cutover checkpoint.

## Recommended PR Slices
1. PR1: HF validator extraction + tests.
2. PR2: HF sync task + scheduled workflow (dry-run mode).
3. PR3: control-plane update wiring + idempotency guards.
4. PR4: cutover (disable old PR-based workflows).
5. PR5: docs/spec updates.
