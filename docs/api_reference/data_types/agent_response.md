# Agent Response Schema

This page documents the expected structure for agent responses in WebArena-Verified.

## Summary

Agents must return a JSON object with the following structure:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | string | Yes | The action type performed: `retrieve`, `navigate`, or `mutate` |
| `status` | string | Yes | Outcome status: `SUCCESS` or error codes (`NOT_FOUND_ERROR`, `PERMISSION_DENIED_ERROR`, etc.) |
| `results` | array or null | Yes | Array of results for successful `retrieve` actions; `null` or empty array for navigate/mutate |
| `error_details` | string | Optional| Detailed explanation when status indicates failure; `null` for `SUCCESS`. Used for analysis and debugging only. |

## Action Types

| Action | Description | When to Use |
|--------|-------------|-------------|
| `retrieve` | Retrieved or accessed information | When the agent reads data without making changes |
| `mutate` | Modified, created, or deleted data | When the agent changes data in the environment |
| `navigate` | Navigated to a specific page or location | When the agent moves to a target page or location |

## Status Codes

| Status | Description | When to Use |
|--------|-------------|-------------|
| `SUCCESS` | Task completed successfully | When the action was completed as intended |
| `NOT_FOUND_ERROR` | Target entity doesn't exist | When search criteria matched no results (e.g., issue, user, product not found) |
| `ACTION_NOT_ALLOWED_ERROR` | Platform doesn't support the action | When the requested action is not supported |
| `PERMISSION_DENIED_ERROR` | Lack authorization | When the agent doesn't have permission to perform the action |
| `DATA_VALIDATION_ERROR` | Input doesn't meet requirements | When input is missing or has invalid format |
| `UNKNOWN_ERROR` | Unexpected failure | When an unexpected error occurs that doesn't fit other categories. This is useful to catch cases where the testing environment is faulty (e.g., website is not reachable). This helps differentiate evaluation failure from evaluation framework errors. |

## Results Field

The `results` field must follow these rules:

- **For successful `retrieve` actions**: Array containing the requested data
- **For `navigate` or `mutate` actions**: Must be `null` or empty array
- **Array items**: All items must be of the same type (string, number, boolean, object, or null)
- **Object results**: When returning multiple objects, all objects must have the same keys


## Example Responses

=== "Successful Retrieve"

    ```json
    {
      "action": "retrieve",
      "status": "SUCCESS",
      "results": ["Quest Lumaflex™ Band"]
    }
    ```

=== "Retrieve with Structured Data"

    ```json
    {
      "action": "retrieve",
      "status": "SUCCESS",
      "results": [
        {
          "name": "Buffalo-Niagara International Airport",
          "state": "New York",
          "zip_code": "14225"
        }
      ]
    }
    ```

=== "Successful Navigate"

    ```json
    {
      "action": "navigate",
      "status": "SUCCESS",
      "results": null
    }
    ```

=== "Error Response"

    ```json
    {
      "action": "retrieve",
      "status": "NOT_FOUND_ERROR",
      "results": null,
      "error_details": "No products found matching the search criteria 'invalid-product-name' after checking all 5 pages of results."
    }
    ```

## Python Model Reference

The agent response schema is defined by the `FinalAgentResponse` class in the codebase:

::: webarena_verified.types.agent_response.FinalAgentResponse
    options:
      show_root_heading: true
      show_source: false
      members: false
