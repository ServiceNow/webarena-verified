# Evaluation

WebArena-Verified provides a comprehensive evaluation framework for assessing web agent performance.
The system validates agent behavior through multiple evaluators that check different aspects of task completion.

## Evaluator Configuration

Each task defines its validation requirements through evaluator configurations:

- **One agent response evaluator** - Every task has exactly one `AgentResponseEvaluator` configuration that validates the agent's final structured response (performed operation, status, and retrieved data).
- **Zero or more network event evaluators** - Depending on the expected operation, a task may include zero to multiple `NetworkEventEvaluator` configurations. Navigate and mutate operations typically require network validation, while retrieve operations may not need any network checks.

## Evaluation Method Comparison

| Aspect | WebArena | WebArena-Verified |
|--------|----------|-------------------|
| **Validation Approach** | DOM-based evaluation | Network event-based evaluation |
| **Matching Method** | Substring matching and LLM-as-judge eval | Data type-aware exact match |
| **LLM-Based Evaluation** | LLM-based evaluation | Replaced by exact match |
| **Stability** | Fragile - breaks with UI changes | Stable - resilient to UI changes |
| **Tool Dependency** | Tightly coupled to specific frameworks | Framework-flexible (any tool with network traces) |
| **Offline Evaluation** | Not supported | Supported - re-evaluate captured traces |

## Learn More

- **[Evaluation Results](evaluation_results.md)** - Complete guide to understanding evaluation output format and results
- **[Network Event-Based Evaluation](network_event_based_evaluation.md)** - Detailed guide on network trace validation using HTTP Archive (HAR) format
- **[Removing LLM-Based Evaluation](removing_llm_based_evaluation.md)** - How we replaced LLM-as-judge with exact matching and verifiable intents
- **[Handling of Unachievable Tasks](handling_of_unachievable_tasks.md)** - Guidance on replacing N/A with explicit statuses and reducing guesswork
