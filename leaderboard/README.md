# Leaderboard System Guide (HF Direct)

## Architecture at a glance

1. Authors submit data through Hugging Face dataset PRs.
2. HF webhook receiver forwards events to GitHub `repository_dispatch`.
3. `leaderboard-hf-ingest.yml` runs `dev.leaderboard.hf-ingest`, updates control/canonical records, and opens a publish PR.
4. `leaderboard-hf-publish-pr.yml` validates scope + rebuild contract and auto-merges on success.
5. Leaderboard UI reads `leaderboard_manifest.json` and generation files from `leaderboard-submissions`.

## Branch roles

- `main`: source code, specs, and docs.
- `leaderboard-submissions`: control records, canonical accepted records, and leaderboard artifacts.
- `gh-pages`: docs site artifacts.

## Storage model

```text
submission_control/
  <submission_id>.json

submissions/
  inbox/
    pr-<hf_pr_number>/
      submission.json
      manifest.json
      tasks/
        <task_id>/agent_response.json
        <task_id>/network.har
        <task_id>/.missing
  <submission_id>.json

leaderboard_full.<generation_id>.json
leaderboard_hard.<generation_id>.json
leaderboard_manifest.json
```

## Ownership boundaries

- HF ingestion writes: `submission_control/<submission_id>.json`, `submissions/<submission_id>.json`.
- Rebuild writes: `leaderboard_full.*.json`, `leaderboard_hard.*.json`, `leaderboard_manifest.json`.
- Publish gating allows only:
  - `submission_control/**`
  - `submissions/**`
  - `leaderboard_manifest.json`
  - `leaderboard_full.*.json`
  - `leaderboard_hard.*.json`

## Identity and status contracts

- `submission_id = hf_pr_number`
- `submission_uid = hf:{hf_repo}:pr-{hf_pr_number}@{hf_head_sha}`
- Control statuses use `SubmissionControlStatus` enum values.
- Canonical records remain accepted records used by rebuild/publish.
