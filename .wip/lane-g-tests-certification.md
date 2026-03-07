# Lane G - Tests and Certification

## Goal

Validate architecture end-to-end with deterministic and auditable behavior.

## Status after Lane E merge

- Completed: G01, G02, G03, G04, G05, G06, G07
- Remaining: G08

## Tasks

- [x] G01 Intake contract tests (`deps: B01,B02,B03,C03,C05`)
  - Valid payload passes
  - Invalid shape fails with clear errors

- [x] G02 Manifest integrity tests (`deps: B03,C04`)
  - Hash and size mismatches fail deterministically

- [x] G03 Canonical record tests (`deps: B04,D05`)
  - `submission_id == pr_number`
  - provenance fields populated
  - evaluator version and scores persisted

- [x] G04 Rebuild single-writer tests (`deps: E02,E06`)
  - Concurrency guard behaves correctly

- [x] G05 Retention tests (`deps: E04`)
  - Exactly 100 canonical records retained in tip

- [x] G06 Atomic manifest tests (`deps: E06`)
  - Manifest points only to present generation files

- [x] G07 UI source tests (`deps: F01,F02,F03`)
  - Env var precedence works
  - Local fallback works

- [ ] G08 End-to-end certification run (`deps: G01,G02,G03,G04,G05,G06,G07`)
  - PR Gate pass -> merge -> finalize -> rebuild -> UI reads latest generation

## Certification checklist

- [x] C1 Intake validation is reliable and actionable
- [x] C2 Canonical ID and provenance persistence are correct
- [x] C3 HF persistence uses canonical path `submissions/<submission_id>/`
- [x] C4 Rebuild workflow is sole writer for leaderboard files
- [x] C5 Retention keeps exactly latest 100 canonical records
- [x] C6 Manifest switch is atomic and consistent
- [x] C7 Leaderboard refresh is independent from docs publish

## Replanned execution

1. Execute G08 end-to-end certification on branch workflows.
2. Capture run links and evidence in runbook and close checklist.
3. Freeze required checks after successful certification run.
