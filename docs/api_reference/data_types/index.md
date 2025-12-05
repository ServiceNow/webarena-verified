# Evaluation Data Types

The evaluation framework normalizes structured values before comparing them. Normalization is built
on a registry of specialized data types that understand how to parse, coerce, and compare values
such as dates, currencies, or geographic coordinates.

## Registry Overview

The type registry lives in `src/webarena_verified/core/evaluation/data_types/__init__.py` and maps
string identifiers (for example, `"date"` or `"currency"`) to concrete `NormalizedType`
implementations.

| Identifier | Description | Normalization Highlights |
|------------|-------------|--------------------------|
| `currency` | Monetary amounts | Handles currency symbols, separators, and precision. |
| `date` | Calendar dates | Accepts multiple string formats and normalizes to ISO dates. |
| `duration` | Time durations | Parses human-readable durations (e.g., `\"1h 30m\"`). |
| `distance` | Distance measurements | Converts common distance units to a canonical value. |
| `coordinates` | Latitude and longitude pairs | Applies tolerance-based comparison for geo points. |
| `full_address` | Street addresses | Normalizes casing, whitespace, and common abbreviations. |
| `url` | Web URLs | Standardizes schemes, hosts, and query parameters. |
| `boolean` | Boolean values | Interprets `\"yes\"`, `\"true\"`, `\"1\"`, and related forms. |
| `string` | Plain strings | Trims whitespace and normalizes casing when needed. |
| `number` | Numeric values | Converts textual numbers to decimals for comparison. |
| `null` | Empty values | Represents missing data explicitly. |

Each specialized type inherits from `NormalizedType` and defines matching logic that is used by the
`value_normalizer` and schema-based comparators (for example in the
[`NetworkEventEvaluator`](../evaluators/network_event_evaluator.md)).
