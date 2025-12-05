# AgentResponseEvaluator

Ensures the agent returns a structured response with the expected action, status, and payload.

## Configuration

| Field | Type | Notes |
|-------|------|-------|
| `evaluator` | `"AgentResponseEvaluator"` | Required discriminator. |
| `ordered` | `bool` | If `True`, `retrieved_data` order must match. |
| `results_schema` | JSON Schema | Validates `retrieved_data` shape. |
| `expected` | `FinalAgentResponse` | Expected action, status, results, and optional error details. |

See `AgentResponseEvaluatorCfg` for the full model.

## Example

```json
{
  "evaluator": "AgentResponseEvaluator",
  "ordered": false,
  "results_schema": {
    "type": "array",
    "items": {"type": "string"}
  },
  "expected": {
    "task_type": "retrieve",
    "status": "SUCCESS",
    "retrieved_data": ["Quest Lumaflex™ Band"]
  }
}
```

The evaluator compares the normalized agent response against `expected` and reports failures when:

- The action differs (`retrieve`, `navigate`, `mutate`).
- The status mismatches (`SUCCESS`, `NOT_FOUND_ERROR`, etc.).
- The payload violates the schema or expected values.
