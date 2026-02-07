# Leaderboard Implementation Tasks (Parallel-First)

## Phase 0 (Blocking, short)
1. Contract freeze
- Add canonical models in `src/webarena_verified/types/leaderboard/`.
- Align `leaderboard/spec/` docs with model fields and invariants.
- Output: shared model package used by all streams.

## Parallel Streams (start after Phase 0)

### Stream A: Submission Control Plane (`main`)
1. Implement storage helpers for:
- `leaderboard/data/submissions/pending/<id>.json`
- `leaderboard/data/submissions/processed/<id>.json`
2. Enforce path/status invariants in code and CI.
3. Enforce transitions: `pending -> accepted|rejected` with `processed_at_utc`.
4. Add tests for mismatch, duplicate IDs, and rejection reason requirements.

### Stream B: CLI Submission Flow
1. Implement `webarena-verified submission submit`.
2. Generate local artifacts:
- `payload.tar.zst`
- `payload.sha256`
- `metadata.json`
- `manifest.json`
3. Integrate HF PR creation/update then GitHub control PR creation.
4. Allow update-in-place for same pending submission before merge.
5. Add tests for dry-run, skip-upload, retries, and invalid metadata.

### Stream C: PR CI Validation Workflow
1. Add submission PR validation workflow.
2. Validate:
- PR file-change constraints
- schema and path/status invariants
- HF linkage/open state
- checksum/archive extraction
- `.missing` policy
- HAR validation
3. Enforce rate limits via GitHub API (`github.actor`), fail closed if API unavailable.
4. Add fixture-driven tests and failure-path coverage.

### Stream D: Post-Merge Processing + Publisher
1. Post-merge job moves pending -> processed and sets terminal status.
2. Generate leaderboard full/hard data + manifest.
3. Publish to `gh-pages` atomically:
- upload all generation assets
- switch manifest last
- never switch manifest on failed publish
4. Keep only manifest + leaderboard generation files on `gh-pages`.
5. Add tests for partial publish failure and rollback safety.

### Stream E: Leaderboard Site Loader/UI
1. Promote `tmp/leaderboard_test_astro` -> `leaderboard-site/`.
2. Update loader to manifest-first fetch.
3. No client hash/integrity validation.
4. Show blocking error + retry when manifest fetch fails.
5. Update table columns to include fixed site score fields:
- `shopping_score`, `reddit_score`, `gitlab_score`, `wikipedia_score`, `map_score`, `shopping_admin_score`
6. Handle sentinel `-1` for unavailable site scores.
7. Add UI tests for error/empty states and fixed-column rendering.

### Stream F: Cross-Cutting Tests/Fixtures
1. Add shared fixtures for submission JSON, manifest, and full/hard rows.
2. Add integration tests for generation + ranking determinism.
3. Add regression tests for tie-break rule:
- `overall_score` desc, then `submission_id` asc

### Stream G: Docs + Ops
1. Write maintainer runbook for submission lifecycle and CI failures.
2. Document atomic publish and rollback procedures.
3. Update contributor docs with expected leaderboard update latency.

## Dependency Graph
1. Phase 0 unlocks Streams A/B/C/D/E/F.
2. A + C align on control-file semantics.
3. D + E align on manifest/data loading contract.
4. F validates all streams continuously.
5. G can run once interfaces stabilize.

## Recommended PR Slices
1. PR1: models + fixtures (Phase 0)
2. PR2: control-plane helpers + tests (A)
3. PR3: CI validator workflow (C)
4. PR4: post-merge + atomic publisher (D)
5. PR5: Astro promotion + loader/UI updates (E)
6. PR6: CLI `submission submit` integration (B)
7. PR7: docs/runbooks (G)
