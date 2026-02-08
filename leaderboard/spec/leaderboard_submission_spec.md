# Leaderboard Submission Specification (HF PR Only, Scheduled)

## Status
Draft v4 (HF-PR-only ingestion with scheduled processing)

Related diagrams:
- `leaderboard/spec/leaderboard_flows.md`

## Goal
Use Hugging Face dataset PRs as the only submission ingress. GitHub Actions scheduled runs validate, process, and publish leaderboard data.

## System Model

### Source of truth
- Payload source of truth: HF dataset repo PRs (`submissions/accepted/<submission_id>/...`).
- Workflow/control source of truth: GitHub control records under `leaderboard/data/submissions/`.
- Published data: GitHub Pages (`gh-pages`) under `leaderboard/data/`.

### Canonical model source
- Pydantic models in `src/webarena_verified/types/leaderboard/` remain canonical for control records, payload contracts, and publish outputs.

## Ingestion Contract

### Accepted ingress
- Maintainers do not process GitHub submission PR diffs.
- Scheduled/manual workflow polls open HF dataset PR discussions and infers candidate submissions.

### Required HF payload layout
Each HF PR must include exactly one submission folder:
- `submissions/accepted/<submission_id>/`

Required files:
- `payload.tar.zst`
- `payload.sha256`
- `metadata.json`
- `manifest.json`

### Control-plane state machine
Durable records are stored in:
- `leaderboard/data/submissions/pending/<submission_id>.json`
- `leaderboard/data/submissions/processed/<submission_id>.json`

Rules:
- `pending/<id>.json` must have `status="pending"`.
- `processed/<id>.json` must have `status in {"accepted","rejected"}`.
- `processed_at_utc` required for terminal statuses.
- duplicate `submission_id` across pending/processed is invalid.

### Required linkage fields
Each control record contains:
- `hf_repo`
- `hf_pr_id`
- `hf_pr_url`

## Scheduled Processing Behavior

1. List open HF dataset PR discussions.
2. Resolve candidate `submission_id` from `refs/pr/<id>/submissions/accepted/` tree.
3. Ensure/create pending record (idempotent).
4. Validate HF PR open state and payload:
- required files present
- checksum consistency
- metadata/manifest schema checks
- submission/linkage consistency
- payload extractability
- task folder + `.missing` policy
- HAR validation
5. On validation failure: transition pending -> rejected with reason.
6. On validation success: merge HF PR (fail closed). If merge succeeds, transition pending -> accepted.
7. Publish full/hard leaderboard data and manifest to `gh-pages` atomically.

## Idempotency Requirements
- Already processed submission ids are skipped.
- Re-running with no new HF changes is a no-op.
- Merge failures keep records pending for future retry.
- One candidate failure must not block others.

## Publish Contract
- Publish remains manifest-gated and atomic:
1. stage full/hard generation files
2. validate staged files and hashes
3. copy generation assets first
4. switch manifest last
5. on failure, keep previous live manifest

## Non-Goals
- Real-time processing
- GitHub submission PR orchestration
- manual PR-diff-based ingestion
