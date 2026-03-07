# Unit Test Cleanup Tasks

This document captures issues found in the current unit test suite and proposes concrete fixes. Each subsection is one actionable issue.

## Skipped Tests

### 1) `tests/types/test_network_trace.py:30` - `test_trace_properties` is hard-skipped
- **Issue**: The test is marked with a generic skip reason ("focus on other tests"), so property-level behavior is not validated.
- **Why we need to fix**: Skipping this test creates a blind spot in an important core type. Regressions can slip in undetected.
- **Suggested fix**: Remove the skip marker, run the test, and either (a) fix production behavior if it fails or (b) narrow the test scope to deterministic properties only.

### 2) `tests/core/evaluation/data_types/test_json_string.py:359` - `test_unicode_characters` skipped
- **Issue**: Unicode normalization behavior is not actively tested because the test is skipped.
- **Why we need to fix**: Unicode handling is a common source of subtle bugs and cross-platform inconsistencies.
- **Suggested fix**: Re-enable the test and define explicit normalization expectations (for example: canonical form decisions, escaping rules, and locale-independent behavior).

### 3) `tests/core/evaluation/data_types/test_json_string.py:372` - `test_special_characters_in_strings` skipped
- **Issue**: Escaped characters and path-like strings are excluded from normal CI coverage.
- **Why we need to fix**: These inputs are high-risk for parser and canonicalization bugs.
- **Suggested fix**: Unskip and split into smaller parameterized cases grouped by character class (escape sequences, path separators, punctuation) with exact expected outputs.

### 4) `tests/core/evaluation/data_types/test_base.py:184` - skipped parameter in `test_hash_single_value`
- **Issue**: One `Number` hashing case is skipped in a parameterized test.
- **Why we need to fix**: Partial hash coverage weakens the equality/hash contract and may allow dict/set behavior regressions.
- **Suggested fix**: Re-enable the skipped parameter and make the expected hash semantics explicit for numeric normalization.

## Redundant or Low-Signal Tests

### 5) `tests/core/evaluation/data_types/test_json_string.py:40` - overlapping normalization tests
- **Issue**: `test_normalization_various_json` substantially duplicates `test_normalization_from_string`.
- **Why we need to fix**: Duplicate coverage increases maintenance cost without adding meaningful signal.
- **Suggested fix**: Merge into one parameterized test table and keep only distinct edge-case dimensions.

### 6) `tests/core/evaluation/data_types/test_base.py:162` - reflexivity test (`x == x`) is mostly tautological
- **Issue**: The test mostly verifies Python's default equality expectations, not domain-specific behavior.
- **Why we need to fix**: Low-signal tests consume runtime and review time while catching few real defects.
- **Suggested fix**: Replace with invariants that target custom logic (normalization side effects, cross-type comparisons, and custom equality branches).

### 7) `tests/core/evaluation/data_types/test_base.py:106` - generic symmetry checks dominate
- **Issue**: Broad symmetry-law checks are repeated with little type-specific intent.
- **Why we need to fix**: Laws are useful, but repetitive law-only tests crowd out behavioral edge cases.
- **Suggested fix**: Keep one shared symmetry/law helper and move remaining effort to feature-level assertions per type.

### 8) `tests/core/evaluation/data_types/test_markdown_string.py:434` - repeated equality-law boilerplate
- **Issue**: Equality law tests duplicate patterns already exercised elsewhere.
- **Why we need to fix**: Boilerplate-heavy suites become noisy and harder to evolve safely.
- **Suggested fix**: Consolidate equality law tests into a reusable base fixture/helper and keep Markdown-specific assertions only in this file.

### 9) `tests/core/evaluation/data_types/test_base64_string.py:477` - repeated equality-law boilerplate
- **Issue**: Same structural law checks are repeated again with minimal Base64-specific value.
- **Why we need to fix**: Repetition creates maintenance drag and weakens test readability.
- **Suggested fix**: Deduplicate by reusing shared law tests and retain only Base64-specific edge cases (padding, invalid alphabet, URL-safe variants).

### 10) `tests/core/evaluation/data_types/test_base64_string.py:355` - set/dict usability test is low signal
- **Issue**: The test mostly verifies Python container behavior, not custom domain semantics.
- **Why we need to fix**: It does not strongly guard against real regressions in normalization/comparison behavior.
- **Suggested fix**: Replace with tests that assert stable hash/equality under equivalent but differently formatted Base64 inputs.

### 11) `tests/core/evaluation/data_types/test_markdown_string.py:357` - set/dict usability test is low signal
- **Issue**: Similar to Base64 case, this primarily re-tests language-level container semantics.
- **Why we need to fix**: It adds little confidence relative to cost.
- **Suggested fix**: Focus on Markdown-specific canonicalization/equivalence behavior (whitespace normalization, emphasis token variants, link syntax differences).

## Invalid, Incorrect, or Fragile Tests

### 12) `tests/types/test_eval_types.py:341` - tuple test does not use a tuple
- **Issue**: `test_tuple_with_normalized_types_serializes` passes a list, not a tuple.
- **Why we need to fix**: Name/intent mismatch can hide real tuple serialization bugs.
- **Suggested fix**: Update fixture input to an actual tuple and add a paired test asserting list-vs-tuple behavior explicitly.

### 13) `tests/core/evaluation/data_types/test_json_string.py:104` - contradiction between name and assertion
- **Issue**: Test name/doc says nested keys are not sorted, but assertions expect sorted nested keys.
- **Why we need to fix**: Contradictory tests confuse maintainers and can block correct refactoring.
- **Suggested fix**: Decide the intended behavior, then align the test name, docstring, and expected value to a single contract.

### 14) `tests/core/evaluation/data_types/test_base.py:151` - vacuous transitivity check
- **Issue**: Test only asserts transitivity conditionally (`if A==B and B==C`), so many failures pass without detection.
- **Why we need to fix**: Vacuous truth turns a core algebraic property into a near no-op.
- **Suggested fix**: Build explicit triples that satisfy the premise by construction, then assert `A==C` unconditionally.

### 15) `tests/core/evaluation/test_value_comparator.py:989` - performance test without performance assertions
- **Issue**: The test is named as a performance check but validates only correctness.
- **Why we need to fix**: Misnamed tests create false expectations and mask real performance regressions.
- **Suggested fix**: Either rename to correctness-focused wording or add bounded runtime assertions via benchmark tooling/timeout thresholds.

### 16) `tests/api/test_data_reader.py:146` - brittle fixed-size expectations
- **Issue**: The test expects minimum counts tied to the current dataset composition.
- **Why we need to fix**: Legitimate data updates can break tests for non-code reasons.
- **Suggested fix**: Replace hard thresholds with deterministic fixture datasets and assert exact behavior from controlled inputs.

## Tests That Need Improvement

### 17) `tests/types/test_agent_response.py` - limited to happy paths
- **Issue**: Validation and parsing checks are mostly positive-path.
- **Why we need to fix**: Error handling and contract robustness are under-tested.
- **Suggested fix**: Add negative cases (missing required fields, bad types, conflicting aliases) and assert error messages/types.

### 18) `tests/types/test_config.py` - missing stronger invariant checks
- **Issue**: Good breadth exists, but important round-trip invariants are not deeply stress-tested.
- **Why we need to fix**: Config transformations can regress silently when only example-driven tests exist.
- **Suggested fix**: Add property-style checks for `render_url`/`derender_url` round-trips, mixed-site cases, and malformed input boundaries.

### 19) `tests/core/evaluation/test_value_comparator.py` - example-heavy, insufficient property coverage
- **Issue**: The suite is broad but relies heavily on hand-picked examples.
- **Why we need to fix**: Complex comparators benefit from permutation/property tests to expose corner-case interactions.
- **Suggested fix**: Add parameterized/permutation tests for unordered matching, deep nesting, circular references, and normalization toggles.

### 20) `tests/cli/test_eval_commands.py` - over-mocked command path
- **Issue**: Heavy mocking of evaluator internals reduces confidence in real CLI contracts.
- **Why we need to fix**: Tests may pass while actual command behavior/output shape regresses.
- **Suggested fix**: Keep unit mocks for failure branches, but add thin contract tests that assert emitted files, JSON schema shape, and exit codes.

### 21) `tests/cli/test_dataset_commands.py` - over-mocked dataset interactions
- **Issue**: Excessive mocking can bypass real serialization/filter semantics.
- **Why we need to fix**: False confidence risk increases when production seams are not exercised.
- **Suggested fix**: Add small deterministic temp-dataset tests that exercise real command parsing and filtering behavior.

### 22) `tests/types/test_eval_types.py` - test-defined serializer helpers may mask production behavior
- **Issue**: Custom helper conversion in tests can drift from production logic.
- **Why we need to fix**: Tests may validate helper behavior rather than the real serializer.
- **Suggested fix**: Prefer production serializer entry points and use fixture builders only for data setup, not behavior duplication.

### 23) `tests/api/test_data_reader.py` - global dataset dependency reduces determinism
- **Issue**: Assertions rely on shared repository dataset state.
- **Why we need to fix**: Unit tests should be isolated, reproducible, and resilient to unrelated data changes.
- **Suggested fix**: Introduce dedicated synthetic fixtures (small curated records) and validate filtering/parsing outcomes deterministically.

## Recommended Execution Order

1. Fix invalid/contradictory tests first (Tasks 12-16).
2. Unskip high-value tests (Tasks 1-4).
3. Remove redundancy and consolidate law tests (Tasks 5-11).
4. Strengthen weak suites with deterministic fixtures and edge cases (Tasks 17-23).
