# Leaderboard Flows (ASCII)

## Flow A: User Submission (CLI)

```text
User
  |
  | webarena-verified submission submit --data-dir ... [--dry-run|--skip-upload]
  v
[Local Validate + Package]
  - build payload.tar.zst
  - build payload.sha256
  - write metadata.json
  - write manifest.json (hf_pr_id/url = null initially)
  |
  +--> if --dry-run or --skip-upload: STOP (local success)
  |
  v
[Create/Update HF PR]  (payload repo)
  - upload files to central HF dataset as PR
  - get hf_pr_id + hf_pr_url
  - patch manifest.json with hf_pr_id/url
  |
  v
[Create GitHub PR] (control repo)
  - add leaderboard/data/submissions/pending/<submission_id>.json
  - submission.json links to HF PR
```

## Flow B: GitHub PR CI Orchestration

```text
GitHub PR opened
  |
  v
[Read submission.json]
  - submission_id
  - hf_repo
  - hf_pr_id
  - hf_pr_url
  |
  v
[Validate HF PR Content]
  - HF PR is OPEN
  - submission_id consistency (GH path + HF payload + files)
  - pending path/status invariant:
      leaderboard/data/submissions/pending/<id>.json => status=pending
  - checksum matches
  - extract archive
  - task structure checks
  - .missing rules
  - HAR validation (trimmer/normalizer)
  |
  +--> FAIL:
  |      - post failure comment
  |      - request CODEOWNERS review
  |      - keep HF PR OPEN (unmerged)
  |      - GitHub PR stays failing
  |
  +--> PASS:
         - merge HF PR first
         - enable/allow GitHub PR auto-merge (squash)
```

## Flow C: Post-Merge on Main

```text
GitHub PR merged
  |
  v
[Post-Merge Job]
  - canonical re-check/evaluation
  - move control record:
      leaderboard/data/submissions/pending/<id>.json
      -> leaderboard/data/submissions/processed/<id>.json
  - set terminal status:
      accepted or rejected
  - commit control-plane updates to main
  |
  v
[Leaderboard Site Deploy]
  - generate and publish manifest + generation files on gh-pages:
      leaderboard/data/leaderboard_manifest.json
      leaderboard/data/leaderboard_full.<generation_id>.json
      leaderboard/data/leaderboard_hard.<generation_id>.json
  - never update live manifest unless all referenced assets are uploaded/verified
  - build Astro site
  - publish /leaderboard/ on GitHub Pages (without clobbering docs)
  - MkDocs keeps link to leaderboard site
```

## Flow D: Data Ownership

```text
                    +-----------------------------+
                    |  Hugging Face Dataset Repo  |
                    |  (payload source of truth)  |
                    |                             |
                    | submissions/accepted/<id>/  |
                    |   payload.tar.zst           |
                    |   payload.sha256            |
                    |   metadata.json             |
                    |   manifest.json             |
                    +--------------+--------------+
                                   ^
                                   | linked by submission.json
                                   v
+----------------------------------+----------------------------------+
|            GitHub Repository (main control branch)                 |
|  leaderboard/data/submissions/pending/<id>.json                    |
|  leaderboard/data/submissions/processed/<id>.json                  |
+----------------------------------+----------------------------------+
                                   |
                                   | publish job mirrors generated data
                                   v
+----------------------------------+----------------------------------+
|            GitHub Pages (gh-pages publish branch)                  |
|  leaderboard/data/leaderboard_manifest.json                        |
|  leaderboard/data/leaderboard_full.<generation_id>.json            |
|  leaderboard/data/leaderboard_hard.<generation_id>.json            |
+---------------------------------------------------------------------+
```

## Flow E: `.missing` Handling

```text
For each expected task_id:
  - if task output exists -> normal task folder/files
  - if missing -> create task_id/.missing (empty)

Validation:
  - .missing alone = valid
  - .missing + other files = invalid
  - submission may still pass with missing tasks
  - missing count reported in summaries/scores
```
