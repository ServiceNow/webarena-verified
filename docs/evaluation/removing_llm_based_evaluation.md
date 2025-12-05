# Removing LLM-Based Evaluation

WebArena-Verified removed LLM-as-judge evaluation in favor of deterministic, data type-aware exact matching. This improves stability and reproducibility.

## What Changed

- Replaced subjective LLM judgments with exact-match checks over structured outputs.
- Introduced two complementary strategies to make outputs verifiable without an LLM:
  1) Explicit format specification
  2) Intent phrasing that yields verifiable data

## 1) Explicit Format Specification

Format specifications describe the expected output structure when the task can return structured data. These are stored in `instantiation_dict` as `retrieved_data_format_spec` and are integrated into the `intent_template`, making them part of the natural task description that agents see.

Guidelines:

- Include format requirements directly in the `intent` via the template.
- Store format specification in `instantiation_dict["retrieved_data_format_spec"]` for tasks instantiated from templates.
- Reference it in `intent_template` using `{{retrieved_data_format_spec}}`.
- Validate results by parsing the agent's output according to the spec and performing exact comparisons.

Example (Task 107)

```json
{
  "sites": ["shopping_admin"],
  "task_id": 107,
  "intent_template_id": 270,
  "start_urls": ["__SHOPPING_ADMIN__"],
  "intent": "Get the monthly count of successful orders from May to December 2022. Return a list of objects, where each object includes a \"month\" field for the month and a \"count\" field for the count.",
  "intent_template": "Get the monthly count of successful orders from {{start_month}} to {{end_month}} {{year}}. {{retrieved_data_format_spec}}.",
  "instantiation_dict": {
    "start_month": "May",
    "end_month": "December",
    "year": 2022,
    "retrieved_data_format_spec": "Return a list of objects, where each object includes a \"month\" field for the month and a \"count\" field for the count"
  }
}
```

Rationale

- Integrates format requirements naturally into the task description.
- Makes output objectively checkable with strict, data type-aware exact matching.
- Enables template reusability with different format specifications for different instantiations.

## 2) Make the Intent Verifiable

When a task is too open-ended for a clear schema, rephrase the intent so the answer is directly checkable against ground truth.

Example (IG 163)

- Before: `What are the main criticisms of this product? Please extract the relevant sentences.`
- After: `List all review titles with 2 stars or below for this product.`

Rationale

- Shifts from subjective summarization to objective retrieval.
- Lets the evaluator verify via exact matching of known review titles/ratings.

## Why Remove LLM-Based Evaluation

- Stability: Not sensitive to UI or prompt drift.
- Determinism: Produces consistent, reproducible outcomes without sampling variance.

## Related Docs

- [Evaluation Results](evaluation_results.md)
