# E2E Test Expected Data

This directory contains **special case** agent response test data for evaluation API tests.

## Test Design

The test framework automatically generates a "default" test variation for every task by reading the expected values directly from `assets/dataset/webarena-verified.json`. This directory should **only** contain special case variations that differ from the dataset defaults.

## Default Test Generation

For each task in `TEST_TASKS`, the test framework automatically generates:

### Valid Tests
- **"default"** variation - Loaded from dataset's `eval[].expected`
- Tests multiple format variations (case, whitespace, markdown, etc.)

### Invalid Tests
- **"default_wrong_status"** - SUCCESS ↔ FAILURE
- **"default_null_data"** - retrieved_data = null
- **"default_empty_array"** - retrieved_data = []
- **"default_wrong_type_string"** - retrieved_data as string
- **"default_wrong_type_number"** - retrieved_data as number
- **"default_wrong_type_object"** - retrieved_data as object
- **"default_missing_field"** - remove retrieved_data
- **"default_wrong_task_type"** - invalid task_type
- **"default_extra_items"** - extra items in array

## When to Add Special Cases

Only create test data files when you need to test:
1. **Alternative valid formats** - Different but valid response structures
2. **Edge cases** - Special invalid scenarios not covered by default variations
3. **Regression tests** - Specific bugs that need dedicated test cases

## File Structure

Each file follows the pattern: `{task_id}_agent_response.json`

```json
{
  "valid": {
    "alternative_format": {
      "task_type": "RETRIEVE",
      "status": "SUCCESS",
      "retrieved_data": [...],
      "error_details": null
    }
  },
  "invalid": {
    "special_edge_case": {
      "task_type": "RETRIEVE",
      "status": "SUCCESS",
      "retrieved_data": "edge case value"
    }
  }
}
```

**Note:** Do NOT add a "default" or "correct" variation - these are automatically loaded from the dataset.

## Adding Special Case Tests

### 1. Create the Test Data File

```bash
cat > tests/assets/e2e_test_expected/0_agent_response.json << 'EOF'
{
  "valid": {
    "nested_array_format": {
      "task_type": "RETRIEVE",
      "status": "SUCCESS",
      "retrieved_data": [[["nested", "array"]]]
    }
  },
  "invalid": {
    "partially_correct": {
      "task_type": "RETRIEVE",
      "status": "SUCCESS",
      "retrieved_data": ["correct_item", "wrong_item"]
    }
  }
}
EOF
```

### 2. Run Tests

The special case variations will be automatically discovered and added to the test suite:

```bash
uv run pytest tests/api/test_evaluation_api_retrieval_tasks.py::test_evaluate_retrieval_task_valid_variations[task_0_nested_array_format] -v
```

## Managing Test Tasks

Edit `tests/api/test_evaluation_api_retrieval_tasks.py` to control which tasks are tested:

```python
TEST_TASKS = [0, 1, 2, 3, ...]  # Add or remove task IDs here
```

All tasks in `TEST_TASKS` automatically get:
- 1 valid "default" test (+ format variations)
- 9 invalid "default_*" tests
- Any additional special cases from JSON files in this directory
