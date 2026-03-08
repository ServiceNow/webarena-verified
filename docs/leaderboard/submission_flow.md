# Submission Flow

This page shows the end-to-end leaderboard submission flow from a user run directory to published leaderboard artifacts.

## 1) End-to-End Pipeline

```mermaid
flowchart TD
    A --> B --> C --> D --> E --> F --> G --> H --> I
    H --> J
    H --> K
    I --> L
    J --> L
    K --> L
```

Legend:

- `A`: User run outputs
- `B`: `create-submission-pkg`
- `C`: Submission package is created
- `D`: `submit --submission-dir`
- `E`: Hugging Face dataset PR inbox
- `F`: Scheduled ingest workflow
- `G`: Ingest + deterministic evaluation
- `H`: Publish PR on `leaderboard-submissions`
- `I`: Rebuild leaderboard artifacts
- `J`: Full leaderboard generation file
- `K`: Hard leaderboard generation file
- `L`: Site reads `leaderboard_manifest.json` and generation files

## 2) Sequence View

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant CLI as webarena-verified CLI
    participant HF as Hugging Face Dataset Repo
    participant ING as leaderboard-hf-ingest.yml
    participant EVAL as hf_ingest.py
    participant BR as leaderboard-submissions Branch
    participant GATE as leaderboard-hf-publish-pr.yml
    participant SITE as Leaderboard Site

    U->>CLI: create-submission-pkg --run-output-dir ... --output ...
    CLI-->>U: Writes submission package with stats
    U->>CLI: submit --submission-dir ./my-submission
    CLI->>HF: Upload submissions/inbox/pr-N/... and open PR
    HF-->>CLI: Return HF PR URL + number

    ING->>HF: Poll recent PR refs (schedule)
    ING->>EVAL: Run reconcile + ingest
    EVAL->>BR: Write control record and canonical record
    EVAL->>BR: Open publish PR (leaderboard-submissions)

    GATE->>BR: Validate changed paths + rebuild contract
    GATE->>BR: Auto-merge publish PR when checks pass
    BR-->>SITE: Publish new manifest + generation files
    SITE->>BR: Read leaderboard_manifest.json and generation files
```

## 3) Submission Status Lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> validating
    validating --> evaluating
    evaluating --> accepted_pending_publish
    accepted_pending_publish --> published

    validating --> rejected
    evaluating --> failed_retryable
    failed_retryable --> validating

    pending --> superseded
    validating --> superseded
    evaluating --> superseded
    accepted_pending_publish --> superseded
```

## Notes

- User-facing submit commands: `create-submission-pkg` and `submit`.
- Ingestion/reconciliation is schedule-driven and writes both control and canonical records.
- Leaderboard site rendering is manifest-driven: the site reads `leaderboard_manifest.json` and generation-specific full/hard files.
