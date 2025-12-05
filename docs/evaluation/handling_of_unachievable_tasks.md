# Handling of Unachievable Tasks

This page explains how we handle action outcome statuses in evaluation, replacing catch‑all labels with explicit, diagnosable statuses to improve determinism and reduce guesswork.

## Replacing Catch‑All N/A

Previously, some unachievable tasks were labeled with a generic `N/A`. We now require returning a specific status that describes the failure mode instead of `N/A`.

- Use one of the explicit error codes (e.g., `NOT_FOUND_ERROR`, `ACTION_NOT_ALLOWED_ERROR`, `PERMISSION_DENIED_ERROR`, `DATA_VALIDATION_ERROR`, `UNKNOWN_ERROR`) that best fits the situation.
- Benefits: Clearer evaluation, reproducible exact matching, and easier debugging of failure causes.
- Reference: See the canonical list in `docs/api_reference/data_types/agent_response.md`.

The AI agent selects the status code at runtime based on its assessment of the failure mode. The framework does not pre‑select or auto‑map statuses.

## Response Requirements

- Keep `action` consistent with the intended operation (`retrieve`, `navigate`, `mutate`).
- For failure statuses, set `results` to `null` (or `[]` only when explicitly allowed).
- `error_details` is optional and ignored for scoring; include brief context for debugging.

## Examples

=== "Retrieve — not found"

```json
{
  "action": "retrieve",
  "status": "NOT_FOUND_ERROR",
  "results": null,
  "error_details": "No invoices found for 2021-01 through 2021-03."
}
```

=== "Mutate — permission denied"

```json
{
  "action": "mutate",
  "status": "PERMISSION_DENIED_ERROR",
  "results": null,
  "error_details": "User lacks admin role to delete project."
}
```

=== "Navigate — action not allowed"

```json
{
  "action": "navigate",
  "status": "ACTION_NOT_ALLOWED_ERROR",
  "results": null,
  "error_details": "Direct navigation to billing page is disabled for this role."
}
```

## Evaluator Expectations

- Scoring uses exact match on `status` and basic structural checks (e.g., `results` is `null` for failures).
- `error_details` does not affect scoring; it’s for analysis only.
- For tasks labeled unachievable in the dataset, returning the expected specific status is required; generic `N/A` is not accepted.

## Fewer Free Passes, Less Guessing

In the original harness, a catch‑all “N/A” could be credited even after minimal exploration, creating asymmetric grading: high recall but low precision for failures. By requiring explicit, agent‑selected status codes, premature “N/A” answers are no longer auto‑credited.

- Effect on spurious passes: The evaluator expects an exact, task‑appropriate status; superficial attempts tend to pick incorrect labels and fail.
- Effect on guessing: Without a catch‑all, naive guessing among multiple failure labels is unlikely to match the expected status (intuitively ~1/M when M valid failure codes exist).
- Exploration adequacy: The protocol favors agents that explore sufficiently before concluding failure, aligning outcomes with the paper’s analysis of under‑explored “N/A” cases.

Takeaway: Removing `N/A` and requiring explicit statuses reduces accidental credits, encourages adequate exploration, and yields more reliable failure reporting.

