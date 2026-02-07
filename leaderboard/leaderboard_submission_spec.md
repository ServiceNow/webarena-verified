# Leaderboard Submission CI Specification

## Status
Draft v2 (HF payload PR + GitHub control PR)

Related diagrams:
- `leaderboard/leaderboard_flows.md`

## Goal
Provide a low-friction, PR-driven submission system where:
- users submit via CLI,
- payload data lives in a central Hugging Face dataset repo,
- GitHub PR CI validates and orchestrates acceptance,
- accepted results update leaderboard data for the leaderboard site.

## System Model

### Source of truth split
- **Payload source of truth:** central HF dataset repo (archives + manifests via HF PRs)
- **Workflow/control source of truth:** GitHub repo PRs and CI
- **Leaderboard data canonical file (GitHub):** `leaderboard-site/public/data/leaderboard.json`

### Trigger model
- Users do **not** open manual GitHub/HF PRs separately.
- CLI creates/updates both PRs:
  - HF PR (payload contribution)
  - GitHub PR (control/orchestration)
- GitHub PR CI handles validation and HF PR merge decision.

## CLI Contract

Primary command:
- `webarena-verified submission submit --data-dir <path> [--output-dir <path>] [--skip-upload] [--dry-run] --name <value> --leaderboard <hard|full|both> --reference <url> [--version <value>] [--contact-info <email>]`

Defaults:
- `--output-dir`: `./webarena-verified-submissions/`

Behavior:
1. Validate local submission input.
2. Package into local output folder.
3. Write metadata + manifest + checksum + archive.
4. If `--dry-run`: stop (no HF/GitHub network operations).
5. If `--skip-upload`: stop after local artifacts.
6. Otherwise:
   - create/update HF PR first,
   - capture HF PR id/url into manifest and GitHub linkage file,
   - open GitHub PR.

`--dry-run` and `--skip-upload` must still produce:
- `payload.tar.zst`
- `payload.sha256`
- `metadata.json`
- `manifest.json`

## Local Output Layout (CLI)
`<output-dir>/<submission_id>/`

Required files:
- `payload.tar.zst`
- `payload.sha256`
- `metadata.json`
- `manifest.json`

## GitHub PR Layout
Each submission GitHub PR must add exactly one folder:
- `leaderboard/submissions/pending/<submission_id>/`

Required file:
- `leaderboard/submissions/pending/<submission_id>/submission.json`

`submission.json` required fields:
- `submission_id`
- `hf_repo`
- `hf_pr_id`
- `hf_pr_url`

Rules:
- `submission_id` must match the pending folder name.
- PR title must start with exact prefix: `Leaderboard Submission: `
- GitHub PR contains only submission-pending additions (no unrelated edits/deletes).

## HF Dataset PR Payload Layout
Single central HF dataset repo is used.

HF PR adds one folder:
- `submissions/accepted/<submission_id>/`

Required files in that folder:
- `payload.tar.zst`
- `payload.sha256`
- `metadata.json`
- `manifest.json`

No direct user write to HF main branch; contributions happen via HF PR only.

## Metadata Contract (`metadata.json`)
Required fields:
- `submission_id` (UUID v4 lowercase, CLI-generated only)
- `name` (required; format `SystemA` or `TeamA/SystemB`)
- `leaderboard` (`hard` | `full` | `both`)
- `reference` (required URL)
- `created_at_utc` (CLI-generated ISO timestamp)

Optional fields:
- `version`
- `contact_info` (if provided, must be valid email format)

Validation rules:
- `submission_id` is never user-provided.
- UUID collision check against central HF repo path; CLI retries generation up to 3 times.
- `name` regex: `^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$`
- `leaderboard=both` requires full task-id namespace coverage.

## Manifest Contract (`manifest.json`)
Required fields:
- `submission_id`
- `archive_file` (`payload.tar.zst`)
- `archive_sha256`
- `archive_size_bytes`
- `created_at_utc`
- `hf_pr_id` (nullable)
- `hf_pr_url` (nullable)

Rules:
- `hf_pr_id` and `hf_pr_url` are `null` when `--skip-upload` or `--dry-run`.
- After successful upload with `create_pr=True`, CLI updates manifest with actual HF PR id/url.

## Task Coverage & Missing Policy

Task directory policy in packaged payload:
- Any missing task is represented as `<task_id>/.missing` (empty file).
- `.missing` + other files in the same task folder is invalid.
- `.missing` is allowed and should warn the user during packaging.
- Submissions with `.missing` are accepted; missing counts are reported in evaluation summaries.

## PR Validation (GitHub CI)
GitHub PR CI validates by reading linked HF PR content:
- `submission.json` linkage integrity.
- HF PR state must be `open`.
- `submission_id` consistency across:
  - GitHub folder path,
  - `submission.json`,
  - HF payload path/files.
- metadata and manifest schema validity.
- checksum integrity (`payload.sha256` vs archive).
- archive extraction and task-structure checks.
- HAR validation using trimmer/normalizer.

If validation fails:
- GitHub PR fails.
- HF PR remains open (not merged).
- CI comments clearly and requests CODEOWNERS review.

If validation passes:
- CI merges HF PR first.
- Then CI enables/allows GitHub PR auto-merge (squash).

## Post-Merge Processing (`main`)
After GitHub PR merge:
1. Re-run canonical checks/evaluation using accepted payload reference.
2. Generate/update submission artifacts in GitHub repo.
3. Regenerate leaderboard data file:
   - `leaderboard-site/public/data/leaderboard.json`
4. Commit generated updates.

## Immutability
- Accepted submission ids are immutable.
- Duplicate `submission_id` must fail.
- Existing accepted HF submission path must not be overwritten.

## Rate Limits (GitHub PR Author)
- Maximum one open submission PR per author.
- Maximum one new submission PR per 24-hour rolling UTC window.
- Violations must include a clear comment with next allowed UTC timestamp.

## Docs Integration
- Leaderboard is a separate static site (Astro) on GitHub Pages.
- MkDocs includes a top-level link to that leaderboard site URL.
- Leaderboard JSON consumed by the site is generated into:
  - `leaderboard-site/public/data/leaderboard.json`

## Non-Goals (v1)
- Email notifications from CI.
- Manual maintainer-only submission merges.
- Storing raw task payload files permanently in GitHub repo.
