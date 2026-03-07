# Leaderboard Submission Process

This README explains the submission flow for leaderboard results.

## Quick overview

1. Submit from a fork with a PR targeting `leaderboard-submissions`.
2. Add exactly one intake folder under `submissions/inbox/<intake_id>/`.
3. PR Gate validates structure, manifest integrity, and scoring preview.
4. After merge, Finalize sets `submission_id = <pr_number>` and writes canonical state.
5. Rebuild regenerates leaderboard files and switches `leaderboard_manifest.json` last.

## What you submit

Your PR must include exactly one intake folder:

```text
submissions/inbox/<intake_id>/
  submission.json
  manifest.json
  tasks/
    <task_id>/
      agent_response.json
      network.har
    <task_id>/
      .missing
```

Task rule:
- each task folder must contain either `.missing` or both `agent_response.json` and `network.har`

`submission.json` required fields:
- `name`
- `leaderboard`
- `reference`
- `created_at_utc`
- `packaging_summary`

`manifest.json` required fields:
- `created_at_utc`
- `schema_version`
- `files[]` entries with `path`, `sha256`, and `size_bytes`

## PR and merge flow

1. Open a PR from your fork into `leaderboard-submissions`.
2. PR Gate runs read-only checks and posts pass/fail feedback.
3. Fix any reported issues and update the PR.
4. Once checks pass and review requirements are met, merge the PR.

## What happens after merge

Finalize workflow:
- reads PR metadata and sets canonical `submission_id = <pr_number>`
- uploads canonical payload to Hugging Face at `submissions/<submission_id>/`
- writes canonical record `submissions/<submission_id>.json`
- removes merged intake folder `submissions/inbox/<intake_id>/`

Rebuild workflow:
- loads canonical records from `submissions/*.json`
- keeps latest 100 canonical records
- writes immutable generation files:
  - `leaderboard_full.<generation_id>.json`
  - `leaderboard_hard.<generation_id>.json`
- updates `leaderboard_manifest.json` last for atomic publish

## Important rules

- Intake is PR-only to `leaderboard-submissions` (no direct pushes).
- Non-contributors must submit from forks.
- Do not manually edit canonical records or leaderboard output files in submission PRs.
- `submission_id` is assigned by CI from the merged PR number.

## Common failure reasons

- missing required files in intake folder
- hash/size mismatches between files and `manifest.json`
- invalid task structure (`.missing` rule not respected)
- malformed required fields in `submission.json` or `manifest.json`
