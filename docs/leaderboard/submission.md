# Submitting Results

This guide shows the full submission flow from run outputs to leaderboard ingestion.

## Prerequisites

Your run output should contain task folders in this shape:

```text
<run_output_dir>/
  <task_id>/
    agent_response.json
    network.har
```

You can submit partial coverage. Missing or invalid tasks are tracked in the package summary.

## Step 1 - Create Submission Package

```bash
uvx webarena-verified create-submission-pkg \
  --run-output-dir ./output \
  --output ./my-submission
```

If you prefer, you can run the same CLI through a local install, `uv run`, or Docker.

The `--output` path is the submission package directory itself. If it already exists, the command will fail unless you pass `--force` to overwrite it.

Expected result: a `./my-submission/` folder containing task folders, `summary.json`, `submission.json` (with placeholder values), and `manifest.json`.

## Step 2 - Review `summary.json`

Open `summary.json` and check `packaging_summary` plus `issues`.

Common issue categories:

| Category | Meaning |
|---|---|
| `missing_agent_response_only` | Task is missing `agent_response.json` |
| `missing_network_har_only` | Task is missing `network.har` |
| `missing_both_files` | Both required files are missing |
| `invalid_har_files` | HAR exists but cannot be processed |
| `empty_agent_response` | Agent response file exists but is empty |

!!! tip
    Fix issues before submitting when possible. Higher-quality packages reduce ingestion failures and improve evaluation coverage.

## Step 3 - Edit `submission.json`

Open `submission.json` and replace the placeholder values with your submission details:

```json
{
  "name": "TeamX/ModelY",
  "leaderboard": "both",
  "reference": "https://example.com/paper",
  "version": null,
  "contact_info": null
}
```

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Model or team name (e.g. `TeamX/ModelY`) |
| `leaderboard` | Yes | Target leaderboard: `hard`, `full`, or `both` |
| `reference` | Yes | HTTP(S) URL to paper or model reference |
| `version` | No | Model version identifier |
| `contact_info` | No | Contact email address |

## Step 4 - Submit To Leaderboard

```bash
uvx webarena-verified submit \
  --submission-dir ./my-submission
```

What this command does:

1. Validates the package and reads your `submission.json`.
2. Regenerates `manifest.json` for integrity.
3. Uploads the payload to HuggingFace and creates a dataset PR.

Expected output includes the HuggingFace PR URL, for example:

```text
PR URL: https://huggingface.co/datasets/<org>/<repo>/discussions/<N>
```

!!! info "Authentication"
    The `submit` command requires HuggingFace authentication. Use either method:

    ```bash
    # Option 1: Login via CLI (persistent)
    hf auth login

    # Option 2: Set token as environment variable
    export HF_TOKEN=hf_...
    ```

## What Happens Next

The automated ingestion pipeline runs every 30 minutes:

```mermaid
flowchart LR
    A[Submit CLI] --> B[HF dataset PR created]
    B --> C[Ingestion job validates payload]
    C --> D[Deterministic evaluation by task and site]
    D --> E[Canonical records updated]
    E --> F[Leaderboard artifacts published]
```

If your submission fails ingestion, review the PR payload and retry with a corrected package.
For support, open an issue in the WebArena-Verified repository.
