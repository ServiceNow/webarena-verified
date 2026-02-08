## Leaderboard HF Submission CI Flow (V1 Basic)

### Goal
A simple, working flow that safely processes HF dataset submission PRs and merges only passing submissions.

### Scope (V1)
- Single CI workflow (scheduled or manual trigger)
- Process open HF dataset PRs that match submission rules
- One processing attempt per `(hf_repo, hf_pr_id, head_sha)`
- Enforce immutable PR content: new commit means open a new PR

### Workflow
1. Start sync workflow with a global workflow concurrency lock.
2. Fetch open HF dataset PRs.
3. Filter PRs by submission title/policy.
4. For each candidate PR:
   - Read `start_sha`.
   - If this PR was previously locked to an `initial_head_sha` and `start_sha` differs:
     - Set terminal state `REJECTED_MUTATED_PR`.
     - Update bot status comment: new submission must use a new PR.
     - Optionally close PR.
     - Continue to next PR.
   - If no lock exists yet, lock `initial_head_sha = start_sha`.
   - Validate PR is still open.
   - Upsert one bot status comment with `processing started`.
   - Verify required files exist:
     - `submission-payload.tar.gz`
     - `submission_metadata.json`
   - Compute SHA256 checksum for each required file.
   - Compute a submission checksum from the required file checksums.
   - Create `manifest.json` listing files + checksums.
   - Run payload validation.
   - Update bot status comment with validation result (`failed` or `validation passed`).
   - If validation passed, run evaluation using `webarena-verified` CLI.
   - Re-fetch PR state before finalize:
     - if PR is closed, stop and mark `STALE`.
     - if head SHA changed, stop and mark `STALE` (do not merge).
   - Write terminal control-plane state.
   - Update bot status comment with final pass/fail status.
   - Merge only if:
     - final status is `PASS`,
     - PR is still open,
     - current SHA equals locked `initial_head_sha`.

### Persistent State (Durable)
Store only durable processing records (no durable queue file):
- `hf_repo`
- `hf_pr_id`
- `initial_head_sha`
- `processed_head_sha`
- terminal status (`PASS`, `FAIL_VALIDATION`, `FAIL_EVAL`, `REJECTED_MUTATED_PR`, `STALE`, `INFRA_ERROR`)
- reason/message
- timestamps

### Queue Model (Ephemeral)
- No separate persistent queue.
- Candidates are fetched and processed within the same CI run.
- Idempotency key is `(hf_repo, hf_pr_id, head_sha)`.

### Deferred Improvements (Post-V1)
- Retry budget/backoff for transient infra failures
- Stronger archive safety limits and sandboxing
- Per-PR parallel workers with per-item concurrency groups
- Auto-retry orchestration and stale lock recovery
