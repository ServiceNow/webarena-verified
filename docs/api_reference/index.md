# API Reference

This section documents the public interfaces exposed by WebArena-Verified.

## WebArenaVerified API

Access all framework functionality through the **[`WebArenaVerified`](webarena_verified.md)** facade class. This provides a stable interface for task retrieval and evaluation.

See the **[WebArenaVerified API reference](webarena_verified.md)** for complete method documentation, or check the **[Usage Guide](../getting_started/usage.md#using-the-programmatic-api)** for practical examples.

## Data Types

WebArena-Verified uses type-aware normalization for deterministic evaluation. The framework includes specialized types for dates, currency, URLs, coordinates, and more - each handling parsing and comparison without LLM-based evaluation.

See the **[Data Types reference](data_types/index.md)** for the complete list of supported types and their normalization behavior.
