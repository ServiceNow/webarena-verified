# Lane D - Finalize Workflow (Post-merge)

## Goal

After merge, canonicalize submission, persist to HF, and write canonical record.

## Tasks

- [ ] D01 Implement finalize trigger (`deps: A04,C01`)
  - Trigger on merged PR into `leaderboard-submissions`

- [ ] D02 Canonical ID assignment (`deps: D01`)
  - `submission_id = <pr_number>`

- [ ] D03 Capture provenance fields from PR event (`deps: D01,B04`)
  - source repository id/full name
  - PR author id/login

- [ ] D04 Upload canonical payload to HF (`deps: D02`)
  - Destination `submissions/<submission_id>/`
  - Capture HF revision

- [ ] D05 Write canonical record (`deps: D02,D03,D04,B04`)
  - Path `submissions/<submission_id>.json`

- [ ] D06 Remove merged intake folder (`deps: D05`)
  - Delete `submissions/inbox/<intake_id>/`

- [ ] D07 Trigger rebuild workflow (`deps: D06`)
  - Dispatch or trigger-by-change for rebuild

## Outputs

- Canonical records produced from merged intake PRs
- Inbox cleaned after finalization
