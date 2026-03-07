# Lane G - Tests and Certification

## Goal

Validate architecture end-to-end with deterministic and auditable behavior.

## Tasks

- [ ] G01 Intake contract tests (`deps: B01,B02,B03,C03,C05`)
  - Valid payload passes
  - Invalid shape fails with clear errors

- [ ] G02 Manifest integrity tests (`deps: B03,C04`)
  - Hash and size mismatches fail deterministically

- [ ] G03 Canonical record tests (`deps: B04,D05`)
  - `submission_id == pr_number`
  - provenance fields populated
  - evaluator version and scores persisted

- [ ] G04 Rebuild single-writer tests (`deps: E02,E06`)
  - Concurrency guard behaves correctly

- [ ] G05 Retention tests (`deps: E04`)
  - Exactly 100 canonical records retained in tip

- [ ] G06 Atomic manifest tests (`deps: E06`)
  - Manifest points only to present generation files

- [ ] G07 UI source tests (`deps: F01,F02,F03`)
  - Env var precedence works
  - Local fallback works

- [ ] G08 End-to-end certification run (`deps: G01,G02,G03,G04,G05,G06,G07`)
  - PR Gate pass -> merge -> finalize -> rebuild -> UI reads latest generation

## Certification checklist

- [ ] C1 Intake validation is reliable and actionable
- [ ] C2 Canonical ID and provenance persistence are correct
- [ ] C3 HF persistence uses canonical path `submissions/<submission_id>/`
- [ ] C4 Rebuild workflow is sole writer for leaderboard files
- [ ] C5 Retention keeps exactly latest 100 canonical records
- [ ] C6 Manifest switch is atomic and consistent
- [ ] C7 Leaderboard refresh is independent from docs publish
