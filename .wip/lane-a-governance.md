# Lane A - Governance and Branch Policy

## Goal

Enforce intake model with GitHub repository policy/ruleset.

## Locked decisions

- Fork policy: strict fork-only intake for non-contributors.
- Contributor bypass roles: `write`, `maintain`, `admin`.
- Enforcement location: repository policy/ruleset only (no workflow code-level fork checks).
- Required checks rollout: phased to avoid merge deadlock.

## Tasks

- [x] A01 Configure `leaderboard-submissions` branch ruleset (`deps: none`)
  - Require pull requests
  - Disable direct pushes
  - Required checks wired in phased rollout (see A04)

- [x] A02 Enforce fork-only intake in repository policy (`deps: A01`)
  - Submission PRs must come from forks
  - Do not enforce this in workflow code

- [x] A03 Protect automation surfaces (`deps: A01`)
  - Restrict updates to `.github/workflows/**`
  - Restrict token/secrets access to intended workflows

- [x] A04 Define required checks (`deps: A01`)
  - Require PR Gate check for merge
  - Require Rebuild check if configured as required

- [ ] A05 Verify permission model (`deps: A03,A04`)
  - PR Gate is read-only
  - Finalize has minimal write permissions
  - Rebuild has write permission for leaderboard files only

## Execution plan

### A01 - Configure `leaderboard-submissions` branch ruleset

1. Create remote branch `leaderboard-submissions` from `main`.
2. Create or update active ruleset scoped to `refs/heads/leaderboard-submissions`.
3. Enforce:
   - pull request required,
   - no direct pushes for non-bypass actors,
   - no force-push,
   - no branch deletion.
4. Keep bypass actors minimal (contributor roles and automation actor only when required).

### A02 - Enforce strict fork-only intake in policy

1. Activate/update repository-level `force-fork` ruleset.
2. Configure bypass actors to contributor roles:
   - `write`,
   - `maintain`,
   - `admin`.
3. Verify expected behavior:
   - non-contributors cannot create upstream submission branches,
   - contributors can still create upstream branches.

### A03 - Protect automation surfaces

1. Restrict updates to `.github/workflows/**` for submission intake path.
2. Set repository default `GITHUB_TOKEN` permissions to `read`.
3. Keep explicit workflow/job-level write permissions only where needed.
4. Restrict `HF_TOKEN` usage to workflows/jobs that require HF access.

### A04 - Define required checks (phased)

1. Phase 1: require PR Gate check after Lane C check name is stable.
2. Phase 2: require Rebuild check after Lane E check name is stable.
3. Do not require checks before workflows exist and report consistently.

### A05 - Verify and capture evidence

Validate and record evidence for:

1. Non-contributor blocked from creating upstream branch.
2. Non-contributor can open fork PR targeting `leaderboard-submissions`.
3. Contributor can create upstream branch.
4. Direct push to `leaderboard-submissions` is blocked for non-bypass actors.
5. PR Gate runs read-only; Finalize/Rebuild write only within intended scope.

Evidence to capture:

- ruleset IDs and target refs,
- required check names and enforcement mode,
- screenshots/CLI output links from policy verification runs.

## Execution status (2026-03-07)

- `leaderboard-submissions` branch created on remote from `main`.
- Branch ruleset created and active:
  - id: `13611485`
  - name: `leaderboard-submissions`
  - target: `refs/heads/leaderboard-submissions`
  - policy: PR required, direct push blocked for non-bypass actors, no force-push, no deletion
  - PR review guard: 1 approval + code-owner review required
- Repository-level fork policy activated:
  - id: `10842280`
  - name: `force-fork`
  - enforcement: `active`
  - bypass roles: `write`, `maintain`, `admin` (actor ids `4`, `2`, `5`)
- Repository Actions default token permissions reduced:
  - `default_workflow_permissions=read`
  - `can_approve_pull_request_reviews=true` retained
- Required checks policy is intentionally phased:
  - Phase 1: require PR Gate after Lane C check name is stable
  - Phase 2: require Rebuild after Lane E check name is stable

## Remaining verification for A05

- [ ] Non-contributor branch creation denial test (upstream)
- [ ] Non-contributor fork PR happy-path test
- [ ] Contributor upstream branch creation test
- [ ] Direct push denial test to `leaderboard-submissions` for non-bypass actor
- [ ] Workflow permission matrix sign-off for PR Gate / Finalize / Rebuild

## Outputs

- Branch ruleset configured and documented
- Required checks policy documented
- Permission model approved
