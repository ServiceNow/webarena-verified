# Evaluation Results

This guide explains the evaluation result format produced by WebArena-Verified's evaluation system.

## Overview

When you evaluate tasks, WebArena-Verified generates structured JSON files containing:

- Task metadata and identification
- Overall score and status
- Individual evaluator results
- Version and checksum information for reproducibility

Result files are saved as `eval_result.json` in each task's output directory.

## Result File Format

### Complete Example

Here's a complete evaluation result from a successful task:

```json
{
  "task_id": 676,
  "intent_template_id": 253,
  "sites": ["shopping_admin"],
  "task_revision": 2,
  "status": "success",
  "score": 1.0,
  "evaluators_results": [
    {
      "evaluator_name": "AgentResponseEvaluator",
      "status": "success",
      "score": 1.0,
      "actual": {
        "action": "navigate",
        "status": "SUCCESS",
        "results": null,
        "error_details": null
      },
      "actual_normalized": {
        "action": "navigate",
        "status": "SUCCESS",
        "results": null,
        "error_details": null
      },
      "expected": {
        "action": "navigate",
        "status": "SUCCESS",
        "results": null,
        "error_details": null
      },
      "assertions": null,
      "error_msg": null
    },
    {
      "evaluator_name": "NetworkEventEvaluator",
      "status": "success",
      "score": 1.0,
      "actual": {
        "url": "__shopping_admin__/sales/order/",
        "headers": {
          "referer": "__shopping_admin__/dashboard/"
        },
        "response_status": 200,
        "query_string": {},
        "post_data": {},
        "event_type": "navigation",
        "http_method": "GET"
      },
      "actual_normalized": {
        "url": "__shopping_admin__/sales/order/",
        "headers": {
          "referer": "__shopping_admin__/dashboard/"
        },
        "response_status": 200,
        "query_string": {},
        "post_data": {},
        "event_type": "navigation",
        "http_method": "GET"
      },
      "expected": {
        "url": "__shopping_admin__/sales/order/",
        "headers": {
          "referer": "__shopping_admin__/dashboard/"
        },
        "response_status": 200,
        "query_string": {},
        "post_data": {},
        "event_type": "navigation",
        "http_method": "GET"
      },
      "assertions": null,
      "error_msg": null
    }
  ],
  "error_msg": null,
  "webarena_verified_version": "1.0.0-rc.1",
  "webarena_verified_evaluator_checksum": "27e007a063d15058672f721653068f7abd4c0b85556b5000c2e555f39a3db422",
  "webarena_verified_data_checksum": "035da5132fe32c25ed12c1fdb012fe55749202dca1eb0dc183e9ab7043f76984"
}
```

## Top-Level Fields

### Task Identification

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `int` | Unique identifier for the task |
| `intent_template_id` | `int` | Groups tasks generated from the same template |
| `sites` | `array[string]` | List of platforms involved (e.g., `["shopping_admin"]`, `["gitlab", "reddit"]`) |
| `task_revision` | `int` | Version number of the task definition (increments when task is updated) |

### Evaluation Results

| Field | Type | Description |
|-------|------|-------------|
| `status` | `string` | Overall evaluation status: `"success"`, `"failure"`, `"partial_match"`, or `"error"` |
| `score` | `float` | Overall score between 0.0 and 1.0. Score is 1.0 only if all evaluators succeed |
| `evaluators_results` | `array` | Results from each individual evaluator (see [Evaluator Results](#evaluator-results)) |
| `error_msg` | `string\|null` | Error message if evaluation failed, otherwise `null` |

### Version Tracking

| Field | Type | Description |
|-------|------|-------------|
| `webarena_verified_version` | `string` | Version of WebArena-Verified that performed the evaluation |
| `webarena_verified_evaluator_checksum` | `string` | SHA-256 checksum of evaluator code (detects evaluator changes) |
| `webarena_verified_data_checksum` | `string` | SHA-256 checksum of dataset file (detects task definition changes) |

Version tracking ensures reproducibility - you can detect if evaluation results differ due to code changes, dataset updates, or actual agent performance differences.

## Evaluator Results

Each entry in `evaluators_results` represents the output of a single evaluator. Multiple evaluators can run for a single task to validate different aspects.

### Evaluator Result Structure

```json
{
  "evaluator_name": "AgentResponseEvaluator",
  "status": "success",
  "score": 1.0,
  "actual": { ... },
  "actual_normalized": { ... },
  "expected": { ... },
  "assertions": null,
  "error_msg": null
}
```

### Evaluator Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `evaluator_name` | `string` | Name of the evaluator that ran (e.g., `"AgentResponseEvaluator"`, `"NetworkEventEvaluator"`) |
| `status` | `string` | Evaluator status: `"success"`, `"failure"`, or `"error"` |
| `score` | `float` | Evaluator score between 0.0 and 1.0 |
| `actual` | `object\|null` | What the agent actually produced (raw format) |
| `actual_normalized` | `object\|null` | Normalized version of actual output (for comparison) |
| `expected` | `object\|null` | What was expected (from task definition) |
| `assertions` | `array\|null` | Detailed assertion results if available (see [Assertions](#assertions)) |
| `error_msg` | `string\|null` | Error message if evaluator failed, otherwise `null` |

## Common Evaluators

### AgentResponseEvaluator

Validates the agent's structured response format, action type, status, and results.

> **Note:** This evaluator examines [`TaskEvalContext.agent_response_raw`](../api_reference/data_types/task_eval_context.md#field-descriptions) to validate the agent's response.

**Example Output:**

```json
{
  "evaluator_name": "AgentResponseEvaluator",
  "status": "success",
  "score": 1.0,
  "actual": {
    "action": "retrieve",
    "status": "SUCCESS",
    "results": ["Product A", "Product B"],
    "error_details": null
  },
  "expected": {
    "action": "retrieve",
    "status": "SUCCESS",
    "results": ["Product A", "Product B"],
    "error_details": null
  }
}
```

### NetworkEventEvaluator

Validates navigation and network requests by matching URLs, headers, query parameters, and status codes captured in HAR traces.

> **Note:** This evaluator examines [`TaskEvalContext.network_trace`](../api_reference/data_types/task_eval_context.md#field-descriptions) to validate network events.

**Example Output:**

```json
{
  "evaluator_name": "NetworkEventEvaluator",
  "status": "success",
  "score": 1.0,
  "actual": {
    "url": "__shopping_admin__/sales/order/",
    "headers": {
      "referer": "__shopping_admin__/dashboard/"
    },
    "response_status": 200,
    "query_string": {},
    "post_data": {},
    "event_type": "navigation",
    "http_method": "GET"
  },
  "expected": {
    "url": "__shopping_admin__/sales/order/",
    "headers": {
      "referer": "__shopping_admin__/dashboard/"
    },
    "response_status": 200,
    "query_string": {},
    "post_data": {},
    "event_type": "navigation",
    "http_method": "GET"
  }
}
```

## Understanding Status Values

### Task-Level Status

| Status | Description | Score | When It Occurs |
|--------|-------------|-------|----------------|
| `success` | Task completed successfully | `1.0` | All evaluators have status `"success"` and score `1.0` |
| `failure` | Task failed validation | `0.0` | One or more evaluators have status `"failure"` |
| `error` | Evaluation encountered an error | `0.0` | One or more evaluators encountered an error during execution |

### Evaluator-Level Status

Each evaluator can have one of these statuses:

- **`success`**: Evaluator validation passed completely
- **`failure`**: Evaluator validation failed (actual didn't match expected)
- **`error`**: Evaluator encountered an error during execution (e.g., missing files, malformed data)

## Assertions

Some evaluators provide detailed assertion-level results to explain why validation succeeded or failed.

### Assertion Structure

```json
{
  "assertion_name": "url_match",
  "status": "success",
  "assertion_msgs": [
    "URL matched expected pattern"
  ],
  "error_msg": null
}
```

### Assertion Fields

| Field | Type | Description |
|-------|------|-------------|
| `assertion_name` | `string` | Name identifying this specific assertion |
| `status` | `string` | Assertion result: `"success"`, `"failure"`, or `"error"` |
| `assertion_msgs` | `array[string]\|null` | Human-readable messages explaining the assertion result |
| `error_msg` | `string\|null` | Error message if assertion encountered an error |

## Common Result Patterns

### Successful Evaluation

All evaluators pass:

```json
    {
      "status": "success",
      "score": 1.0,
      "evaluators_results": [
        {
          "evaluator_name": "AgentResponseEvaluator",
          "status": "success",
          "score": 1.0
        },
        {
          "evaluator_name": "NetworkEventEvaluator",
          "status": "success",
          "score": 1.0
        }
      ],
      "error_msg": null
}
```

### Failed Evaluation

One or more evaluators fail:

```json
    {
      "status": "failure",
      "score": 0.0,
      "evaluators_results": [
        {
          "evaluator_name": "AgentResponseEvaluator",
          "status": "success",
          "score": 1.0
        },
        {
          "evaluator_name": "NetworkEventEvaluator",
          "status": "failure",
          "score": 0.0,
          "error_msg": "No network events matched criteria: {'url': '__shopping_admin__/sales/order/'}"
        }
      ],
      "error_msg": null
    }
  ```

### Evaluation Error

Evaluator encountered an error during execution:

```json
{
  "status": "error",
  "score": 0.0,
  "evaluators_results": [
    {
      "evaluator_name": "AgentResponseEvaluator",
      "status": "error",
      "score": 0.0,
      "error_msg": "Failed to parse agent_response.json: Expecting property name enclosed in double quotes"
    }
  ],
  "error_msg": "One or more evaluators encountered errors"
}
```

## Batch Evaluation Results

When evaluating multiple tasks using `eval-tasks`, WebArena-Verified generates:

1. **Individual task results**: One `task_{id}_eval_result.json` per task in each task's directory
2. **Summary file**: `eval_summary.json` in the output directory with aggregated statistics

### Summary File Format

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "webarena_verified_version": "1.0.0-rc.1",
  "webarena_verified_evaluator_checksum": "27e007a...",
  "webarena_verified_data_checksum": "035da51...",
  "total": 100,
  "success_count": 87,
  "failed_count": 12,
  "error_count": 1,
  "per_site_summary": {
    "shopping_admin": [
      {"task_id": 1, "status": "success", "score": 1.0},
      {"task_id": 2, "status": "success", "score": 1.0}
    ],
    "gitlab": [
      {"task_id": 50, "status": "failure", "score": 0.0}
    ]
  },
  "task_results": [ ... ]
}
```

## Using Evaluation Results

### Programmatic Access

Read and analyze results in Python:

```python
import json
from pathlib import Path

# Load result file
result_path = Path("output/task_1/task_1_eval_result.json")
with open(result_path) as f:
    result = json.load(f)

# Check if task passed
if result["status"] == "success" and result["score"] == 1.0:
    print(f"Task {result['task_id']} passed!")
else:
    print(f"Task {result['task_id']} failed")
    for eval_result in result["evaluators_results"]:
        if eval_result["status"] != "success":
            print(f"  - {eval_result['evaluator_name']}: {eval_result['error_msg']}")
```

### Filtering Results

Find all failed tasks:

```bash
# Using jq
find output -name "*_eval_result.json" -exec jq -r 'select(.status != "success") | .task_id' {} \;
```

### Computing Pass Rate

```bash
# Count successes vs total
total=$(find output -name "*_eval_result.json" | wc -l)
passed=$(find output -name "*_eval_result.json" -exec jq -r 'select(.status == "success") | .task_id' {} \; | wc -l)
echo "Pass rate: $passed / $total"
```

## Troubleshooting

### Score is 0.0 but status is "success"

This shouldn't happen in WebArena-Verified. If you encounter this, it may indicate:

- A bug in evaluator logic
- Corrupted result file

Please report this as an issue.

### Missing evaluators_results

If `evaluators_results` is empty or missing, check:

- The task definition has valid evaluator configurations
- All required files are present (agent_response.json, trace.zip)
- The evaluation didn't encounter an early error (check `error_msg`)

### Checksum Mismatches

If you re-evaluate the same task and get different checksums:

- **evaluator_checksum changed**: Evaluator code was modified (code update, bug fix)
- **data_checksum changed**: Task definition was updated (dataset version change)

Different checksums don't necessarily mean results are invalid, but they indicate the evaluation conditions changed.

## See Also

- [Network Event Based Evaluation](network_event_based_evaluation.md) - Deep dive into network trace validation
- [Getting Started Guide](../index.md) - Learn how to run evaluations
- [API Reference: EvaluatorResult](../api_reference/data_types/task.md) - Technical schema details
