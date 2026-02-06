# Test Assets

## e2e_test_retrieved_data.json

This file contains test data for e2e retrieval task tests. It is **generated** and should be regenerated whenever format variations in `tests/api/format_variations_utils.py` are modified.

### Regenerate

```bash
uv run python tests/assets/generate_format_variations.py
```

### Structure

```json
{
  "task_id": {
    "exact_match": <original_value>,
    "valid": {"fmt_variation_name": <transformed_value>, ...},
    "invalid": {"variation_name": <invalid_value>, ...}
  }
}
```

### When to regenerate

- After modifying `DURATION_VARIATIONS`, `CURRENCY_VARIATIONS`, etc. in `format_variations_utils.py`
- After adding new format variation types
- After changes to the dataset that affect retrieval tasks
