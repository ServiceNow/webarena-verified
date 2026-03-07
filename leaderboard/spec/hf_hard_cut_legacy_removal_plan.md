# HF Hard-Cut Legacy Removal Plan

## Goal
Remove all legacy leaderboard intake/finalization code that depends on GitHub submission PRs and `submissions/inbox/<intake_id>` as the primary source.

Target state:
- HF PR dispatch + schedule reconciler is the only ingestion path.
- Control records live under `submission_control/<submission_id>.json`.
- Canonical accepted records live under `submissions/<submission_id>.json`.

## Legacy Definition
Legacy means any runtime path whose primary trigger is:
1. GitHub contributor PRs changing `submissions/inbox/**`.
2. `pull_request_target` finalize flow on merged intake PRs.
3. Code/tests/docs that require `submission_id == github_pr_number`.

## Removal Scope

### A) Delete legacy runtime modules
- `leaderboard/scripts/pr_gate_intake_validator.py`
- `leaderboard/scripts/finalize.py`

### B) Remove legacy invoke tasks
Update `leaderboard/scripts/tasks.py` to remove:
- `@task(name="pr-gate-intake-validate")`
- `@task(name="finalize")`

Keep only HF-direct and publish/rebuild tasks:
- `hf-ingest`
- `rebuild-canonical`

### C) Remove legacy tests
Delete:
- `tests/leaderboard/test_pr_gate_intake_validator.py`
- `tests/leaderboard/test_finalize.py`
- `tests/leaderboard/test_end_to_end_certification.py` (legacy end-to-end centered on PR gate + finalize)

Replace with:
- HF-direct e2e test built on `hf_ingest.ingest_hf_submission` + `publish_from_canonical`.

### D) Remove legacy workflow contract expectations
Update tests to stop referencing removed workflow files and behavior:
- No assertions for `.github/workflows/leaderboard-pr-gate.yml`
- No assertions for `.github/workflows/leaderboard-finalize.yml`

### E) Remove legacy docs/spec references
Update or delete docs that prescribe PR-gate/finalize intake:
- `leaderboard/scripts/README.md` (already updated)
- `docs/leaderboard/publish_runbook.md` (remove legacy command mentions if present)
- Any spec files that instruct `dev.leaderboard.pr-gate-intake-validate` or `dev.leaderboard.finalize`

### F) Tighten type model to non-legacy semantics
In `src/webarena_verified/types/leaderboard/submission_record.py`:
- Keep decoupled identity (no `submission_id == github_pr_number` invariant).
- Mark GitHub intake provenance fields as optional or explicitly publish-PR provenance only.

## Implementation Order
1. Remove legacy invoke task exports from `leaderboard/scripts/tasks.py`.
2. Delete `pr_gate_intake_validator.py` and `finalize.py`.
3. Delete legacy tests and add HF-direct replacement end-to-end test.
4. Sweep docs/specs for removed command references.
5. Run full leaderboard/type verification.

## Search-and-Destroy Checklist
Use repo-wide search and require zero matches for these symbols:
- `dev.leaderboard.finalize`
- `dev.leaderboard.pr-gate-intake-validate`
- `run_pr_gate_intake_validation`
- `finalize_submission(`
- `parse_finalize_event(`
- `list_merged_pr_changed_files(`
- `pull_request_target`
- `submissions/inbox/<intake_id>` (legacy intake-id contract phrasing)

Allowed surviving pattern:
- `submissions/inbox/pr-<hf_pr_number>/`

## Verification Gate (must pass)
1. `uv run pytest tests/leaderboard tests/types/test_leaderboard_types.py`
2. `uv run pytest` for full suite sanity.
3. `inv --list` confirms only intended leaderboard tasks remain.
4. `grep`/search checklist above returns no legacy runtime references.

## Done Criteria
All are true:
1. No executable code path remains for GitHub submission PR intake.
2. No workflow references or tests depend on removed legacy files.
3. No docs instruct using removed legacy commands.
4. Test suite passes with HF-direct only pipeline.
