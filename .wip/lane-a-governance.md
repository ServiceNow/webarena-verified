# Lane A - Governance and Branch Policy

## Goal

Enforce intake model with GitHub repository policy/ruleset.

## Tasks

- [ ] A01 Configure `leaderboard-submissions` branch ruleset (`deps: none`)
  - Require pull requests
  - Disable direct pushes
  - Require status checks before merge

- [ ] A02 Enforce fork-only intake in repository policy (`deps: A01`)
  - Submission PRs must come from forks
  - Do not enforce this in workflow code

- [ ] A03 Protect automation surfaces (`deps: A01`)
  - Restrict updates to `.github/workflows/**`
  - Restrict token/secrets access to intended workflows

- [ ] A04 Define required checks (`deps: A01`)
  - Require PR Gate check for merge
  - Require Rebuild check if configured as required

- [ ] A05 Verify permission model (`deps: A03,A04`)
  - PR Gate is read-only
  - Finalize has minimal write permissions
  - Rebuild has write permission for leaderboard files only

## Outputs

- Branch ruleset configured and documented
- Required checks policy documented
- Permission model approved
