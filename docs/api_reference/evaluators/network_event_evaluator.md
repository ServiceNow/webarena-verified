# NetworkEventEvaluator

Validates captured network traffic to confirm the agent hit the right endpoints with the expected status, headers, and parameters.

## Configuration

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `evaluator` | `"NetworkEventEvaluator"` | — | Required discriminator. |
| `url_match_mode` | `"exact" \| "prefix" \| "regex"` | `"exact"` | How URLs are matched. |
| `last_event_only` | `bool` | `true` | Validate only the most recent matching event. |
| `ignored_query_params` | `tuple[str, ...]` | — | Literal query keys to drop before comparison. |
| `ignored_query_params_patterns` | `tuple[str, ...]` | — | Regex patterns for keys to drop. |
| `decode_base64_query` | `bool` | `false` | Decode base64 segments embedded in URL paths. |
| `query_params_schema` / `post_data_schema` | JSON Schema | — | Optional type-aware normalization. |
| `expected` | `NetworkEventExpected` | — | Required block describing the target event. |

`NetworkEventExpected` supports:

| Field | Type | Default |
|-------|------|---------|
| `url` | `str` | — |
| `headers` | `dict[str, str]` | `null` |
| `query_params` | `dict[str, list[str]]` | `null` |
| `post_data` | `dict[str, str]` | `null` |
| `response_status` | `int` | `200` |
| `event_type` | `"navigation" \| "modification" \| "other" \| null` | `null` |
| `http_method` | `str` | `"GET"` |

## Example

```json
{
  "evaluator": "NetworkEventEvaluator",
  "url_match_mode": "prefix",
  "ignored_query_params_patterns": ["^paging", "^sorting"],
  "expected": {
    "url": "__SHOPPING_ADMIN__/mui/index/render/",
    "headers": {
      "referer": "__SHOPPING_ADMIN__/sales/order/",
      "X-Requested-With": "XMLHttpRequest"
    },
    "query_string": {
      "namespace": "sales_order_grid"
    },
    "response_status": 200,
    "event_type": "navigation",
    "http_method": "GET"
  }
}
```

The evaluator searches captured events using the configured URL mode and headers. It then checks the last matching event (or any, if `last_event_only` is `false`) against the expected method, status, headers, query string, and optional schemas.
