# Usage

This guide walks you through using WebArena-Verified to evaluate web agents. You'll learn how to get task data, run your agent, and evaluate the results using either the CLI or programmatic API.

## Prerequisites

- Python 3.11+
- WebArena-Verified installed (see [Installation](#installation))
- Configuration file set up (see [Configuration](configuration.md))

## Installation

Install WebArena-Verified from PyPI:

```bash
pip install webarena-verified
```

Verify the installation:

```bash
webarena-verified --help
```

For development or contributing, see [Local Development](../contributing/local-development.md).

## Step 1: Set Up Your Configuration

Create a configuration file that specifies your environment URLs and credentials:

```json
{
  "environments": {
    "__GITLAB__": {
      "urls": ["http://localhost:8012"],
      "credentials": {"username": "root", "password": "demopass"}
    },
    "__SHOPPING__": {
      "urls": ["http://localhost:7770"]
    }
  }
}
```

See [Configuration](configuration.md) for complete details on all configuration options.

## Step 2: Get Task Data

Export task information that your agent needs using the `agent-input-get` command:

=== "All tasks"

    ```bash
    webarena-verified agent-input-get \
      --config config.json \
      --output tasks.json
    ```

=== "Specific tasks"

    ```bash
    webarena-verified agent-input-get \
      --task-ids 1,2,3 \
      --config config.json \
      --output tasks.json
    ```

=== "Filter by site"

    ```bash
    webarena-verified agent-input-get \
      --sites shopping \
      --config config.json \
      --output tasks.json
    ```

The output file contains task metadata your agent needs:

```json
[
  {
    "task_id": 1,
    "intent_template_id": 100,
    "sites": ["shopping"],
    "start_urls": ["http://localhost:7770/..."],
    "intent": "What is the price of..."
  }
]
```

!!! tip "URL Rendering"
    The `--config` flag is required to render template URLs (like `__SHOPPING__`) into actual URLs that your agent can navigate to.

## Step 3: Run Your Agent

Your agent should:

1. Load task data from the JSON file produced in Step 2
2. For each task:
    - Navigate to the provided `start_urls`
    - Execute the task based on the `intent`
    - Save outputs to the expected location

**Required output files per task:**

```
{output_dir}/
└── {task_id}/
    ├── agent_response.json  # Agent's response (see format below)
    └── network.har          # Network trace in HAR format
```

**Agent response format:**

```json
{
  "task_type": "RETRIEVE",
  "status": "SUCCESS",
  "retrieved_data": ["extracted data here"],
  "error_details": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `task_type` | string | One of: `RETRIEVE`, `MUTATE`, `NAVIGATE` |
| `status` | string | One of: `SUCCESS`, `ACTION_NOT_ALLOWED_ERROR`, `PERMISSION_DENIED_ERROR`, `NOT_FOUND_ERROR`, `DATA_VALIDATION_ERROR`, `UNKNOWN_ERROR` |
| `retrieved_data` | array or null | Required for `RETRIEVE` tasks; list of extracted values |
| `error_details` | string or null | Optional error description |

!!! example "Reference Implementation"
    See the human agent example in `examples/agents/human/` for a complete reference implementation that demonstrates loading task data, browser automation with Playwright, and producing properly formatted output files.

## Step 4: Evaluate Results

Use the `eval-tasks` command to score your agent's outputs:

### Basic Evaluation

Score one or more runs. When no filters are provided, the CLI discovers every task directory under `--output-dir` that contains the required files.

=== "CLI"

    ```bash
    webarena-verified eval-tasks --output-dir output
    ```

=== "Docker"

    ```bash
    docker run --rm \
      -v /path/to/output:/data \
      am1n3e/webarena-verified:latest \
      eval-tasks --output-dir /data
    ```

### Filtering Tasks

You can filter which tasks to evaluate:

=== "Specific task IDs"

    ```bash
    webarena-verified eval-tasks \
      --config config.json \
      --output-dir output \
      --task-ids 1,2,3
    ```

=== "Single task"

    ```bash
    webarena-verified eval-tasks \
      --config config.json \
      --output-dir output \
      --task-ids 42
    ```

=== "By site"

    ```bash
    webarena-verified eval-tasks \
      --config config.json \
      --output-dir output \
      --sites shopping
    ```

=== "By task type"

    ```bash
    webarena-verified eval-tasks \
      --config config.json \
      --output-dir output \
      --task-type mutate
    ```

=== "By template ID"

    ```bash
    webarena-verified eval-tasks \
      --config config.json \
      --output-dir output \
      --template-id 5
    ```

=== "Combined filters"

    ```bash
    webarena-verified eval-tasks \
      --config config.json \
      --output-dir output \
      --sites shopping,reddit \
      --task-type mutate
    ```

=== "Dry run (no scoring)"

    ```bash
    webarena-verified eval-tasks \
      --config config.json \
      --output-dir output \
      --sites reddit \
      --dry-run
    ```

**Available filter flags:**

| Flag            | Description                                                   |
|:---------------:|:--------------------------------------------------------------|
| `--task-ids`    | Comma-separated task IDs (for example `1,2,3` or single `42`). |
| `--sites`       | Comma-separated site names (`shopping`, `reddit`, `gitlab`, `map`, etc.). |
| `--task-type`   | Task type (`retrieve`, `mutate`, or `navigate`).     |
| `--template-id` | Filter by `intent_template_id`.                                |
| `--dry-run`     | List matching tasks without scoring them.                     |

### Understanding Evaluation Output

The CLI writes evaluation artifacts alongside your agent outputs:

```
output/
├── {task_id}/
│   ├── agent_response.json  # Agent response produced by the agent
│   ├── network.har          # Network trace captured during the run (HAR format)
│   └── eval_result.json     # Evaluation result written by the CLI
└── eval_log_{timestamp}.txt # Batch evaluation log
```

See [Evaluation Results](../evaluation/evaluation_results.md) for details on the evaluation output format.

## Using the Programmatic API

If you prefer to integrate WebArena-Verified directly into your Python code, you can use the programmatic API.

### Step 1: Initialize WebArenaVerified

Create a `WebArenaVerified` instance with your environment configuration:

```python
from pathlib import Path
from webarena_verified.api import WebArenaVerified
from webarena_verified.types.config import WebArenaVerifiedConfig

# Initialize with configuration
config = WebArenaVerifiedConfig(
    environments={
        "__GITLAB__": {
            "urls": ["http://localhost:8012"],
            "credentials": {"username": "root", "password": "demopass"}
        }
    }
)
wa = WebArenaVerified(config=config)
```

### Step 2: Get Task Data

Retrieve task information programmatically:

```python
# Get a single task
task = wa.get_task(42)
print(f"Task intent: {task.intent}")
print(f"Start URLs: {task.start_urls}")

# Get multiple tasks
tasks = [wa.get_task(task_id) for task_id in [1, 2, 3]]
```

### Step 3: Evaluate Agent Output

Once you have your agent's output, evaluate it against the task definition. You can pass agent responses as file paths or construct them directly in code:

=== "With Files"

    ```python
    # Evaluate a task with file paths
    result = wa.evaluate_task(
        task_id=44,
        agent_response=Path("output/44/agent_response.json"),
        network_trace=Path("output/44/network.har")
    )

    print(f"Score: {result.score}, Status: {result.status}")
    ```

=== "With Content"

    ```python
    import json

    # Evaluate a task with direct content
    result = wa.evaluate_task(
        task_id=44,
        agent_response={
            "task_type": "NAVIGATE",
            "status": "SUCCESS",
            "retrieved_data": None
        },
        network_trace=json.loads(Path("output/44/network.har").read_text())
    )

    print(f"Score: {result.score}, Status: {result.status}")
    ```

## See Also

- **[Configuration](configuration.md)** - Complete configuration reference and options
- **[Subset Manager](subset_manager.md)** - Work with task subsets for focused evaluation
