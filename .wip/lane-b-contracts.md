# Lane B - Contracts and Data Shapes

## Goal

Freeze intake, canonical, and leaderboard contracts.

## Tasks

- [ ] B01 Freeze intake path contract (`deps: none`)
  - `submissions/inbox/<intake_id>/submission.json`
  - `submissions/inbox/<intake_id>/manifest.json`
  - `submissions/inbox/<intake_id>/tasks/**`

- [ ] B02 Freeze `submission.json` schema (`deps: B01`)
  - Required: `name`, `leaderboard`, `reference`, `created_at_utc`, `packaging_summary`
  - Optional: `version`, `contact_info`

- [ ] B03 Freeze `manifest.json` schema (`deps: B01`)
  - Required: `created_at_utc`, `schema_version`, `files[]`
  - `files[]`: `path`, `sha256`, `size_bytes`

- [ ] B04 Freeze canonical record schema `submissions/<submission_id>.json` (`deps: B02,B03`)
  - `submission_id`, `github_pr_number`, `github_pr_url`
  - provenance fields:
    - `source_repository_id`
    - `source_repository_full_name`
    - `github_pr_author_id`
    - `github_pr_author_login`
  - status/timing/version/HF pointers
  - score and count fields

- [ ] B05 Freeze leaderboard generation contract (`deps: B04`)
  - Include accepted canonical records only
  - Rank sorting: `overall_score desc`, `submission_id asc`

## Outputs

- Contract document with schema examples
- Type/schema updates ready for workflow consumers
