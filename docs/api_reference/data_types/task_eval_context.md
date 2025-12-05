# TaskEvalContext

The evaluation context passed to evaluators containing all data needed to validate task completion.

## Overview

`TaskEvalContext` is provided to evaluators during task evaluation. It contains the task definition, agent response, network trace, and configuration needed for validation.

## Attributes

::: src.webarena_verified.types.eval.TaskEvalContext
    options:
      show_docstring_description: false
      members: ["task", "agent_response_raw", "network_trace", "config"]

## Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `task` | `WebArenaVerifiedTask` | The task being evaluated, including expected values and evaluator configurations |
| `agent_response_raw` | `Any` | The raw agent response (string, dict, or parsed JSON). Used by [AgentResponseEvaluator](../evaluators/agent_response_evaluator.md) |
| `network_trace` | `NetworkTrace` | Captured network events from the agent's execution. Used by [NetworkEventEvaluator](../evaluators/network_event_evaluator.md) |
| `config` | `WebArenaVerifiedConfig` | Framework configuration including site URLs and settings |

## Usage in Evaluators

Different evaluators access different fields from the context:

- **[AgentResponseEvaluator](../evaluators/agent_response_evaluator.md)**: Validates the structured response by accessing `agent_response_raw`
- **[NetworkEventEvaluator](../evaluators/network_event_evaluator.md)**: Validates network traffic by accessing `network_trace`

## See Also

- [Evaluation Results](../../evaluation/evaluation_results.md) - Understanding evaluator output format
- [WebArenaVerifiedTask](task.md) - Task structure and definition
