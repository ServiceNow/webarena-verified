"""Value comparison with recursive structural matching.

This comparator performs recursive structural comparison for nested objects and arrays,
delegating value comparison to NormalizedType.__eq__. Alternatives are handled internally
by NormalizedType instances.
"""

from types import MappingProxyType
from typing import Any

from webarena_verified.core.evaluation.data_types import NormalizedType
from webarena_verified.types.eval import EvalAssertion, EvalStatus


class ValueComparator:
    """Compares normalized values using recursive structural matching.

    Performs recursive comparison for nested structures (arrays, objects) and delegates
    value equality to NormalizedType.__eq__ for handling alternatives. Includes circular
    reference detection to prevent infinite recursion.

    Responsibilities:
    - Recursive structural comparison (arrays, objects, nested structures)
    - Circular reference detection and prevention
    - Clear error messages with full path information

    NOT responsible for:
    - Alternative handling (done by NormalizedType.__eq__)
    - Value normalization (done by ValueNormalizer)

    Example:
        comparator = ValueComparator()

        # Single value with alternatives
        expected = NormalizedString(['success', 'ok'])
        actual = NormalizedString('success')
        comparator.compare(actual, expected)
        # → [] (success)

        # Nested structures
        expected = {'status': NormalizedString('ok'), 'items': [Number(1), Number(2)]}
        actual = {'status': NormalizedString('ok'), 'items': [Number(1), Number(2)]}
        comparator.compare(actual, expected)
        # → [] (success)
    """

    def compare(
        self,
        actual: Any,
        expected: Any,
        ordered: bool = False,
        value_name: str = "value",
        ignored_values_keys: set | None = None,
        ignore_extra_keys: bool = False,
    ) -> list[EvalAssertion]:
        """Compare actual against expected values recursively.

        Args:
            actual: Actual value (primitives, NormalizedType, list, tuple, dict, MappingProxyType)
            expected: Expected value (may contain alternatives via NormalizedType)
            ordered: Whether order matters for array comparisons
            value_name: Root name for error paths (default: "value")
            ignored_values_keys: Object keys to ignore during comparison
            ignore_extra_keys: Whether to allow extra keys in actual objects

        Returns:
            List of EvalAssertion (empty = success, non-empty = failure)

        Raises:
            ValueError: If circular reference detected in actual value
        """
        # Initialize visited tracking for circular reference detection
        visited: set[int] = set()

        return self._compare_recursive(
            actual=actual,
            expected=expected,
            ordered=ordered,
            path=value_name,
            ignored_values_keys=ignored_values_keys,
            ignore_extra_keys=ignore_extra_keys,
            visited=visited,
        )

    def _compare_arrays(
        self,
        *,
        expected_array: list | tuple,
        actual_array: Any,
        value_name: str,
        ordered: bool = False,
        visited: set[int] | None = None,
        **kwargs: Any,
    ) -> list[EvalAssertion]:
        """Dispatch array comparison to ordered or unordered method.

        Args:
            expected_array: Expected array
            actual_array: Actual value (validated to be array)
            value_name: Path name for error messages
            ordered: Whether to use ordered comparison
            visited: Set of visited object IDs for circular reference detection

        Returns:
            List of EvalAssertion (empty if match)
        """
        if not isinstance(expected_array, (list, tuple)):
            raise TypeError(f"Expected array must be list or tuple, got {type(expected_array).__name__}")

        if not isinstance(actual_array, (list, tuple)):
            return [
                EvalAssertion.create(
                    assertion_name=f"{value_name}_invalid_format",
                    status=EvalStatus.FAILURE,
                    assertion_msgs=[f"Expected an array, but got: {type(actual_array).__name__}"],
                )
            ]

        if ordered:
            return self._compare_arrays_ordered(
                expected_array, actual_array, value_name, ordered, visited=visited, **kwargs
            )
        else:
            return self._compare_arrays_unordered(
                expected_array, actual_array, value_name, ordered, visited=visited, **kwargs
            )

    def _compare_arrays_unordered(
        self,
        expected_array: list | tuple,
        actual_array: list | tuple,
        value_name: str,
        ordered: bool,
        visited: set[int] | None = None,
        **kwargs: Any,
    ) -> list[EvalAssertion]:
        """Compare arrays ignoring order using greedy matching.

        For each expected element, finds first unmatched actual element that equals it.
        Handles duplicates correctly (e.g., expected=[X, X] requires actual to have 2+ copies of X).
        Uses trial visited sets to avoid false circular reference detection during matching.

        Args:
            expected_array: Expected array
            actual_array: Actual array
            value_name: Path name for error messages
            ordered: Whether nested sequences are order-sensitive
            visited: Set of visited object IDs for circular reference detection

        Returns:
            List of EvalAssertion (empty if match)
        """
        assertions = []

        # Track which actual elements have been matched
        actual_matched = [False] * len(actual_array)

        # Track expected elements that couldn't be matched
        unmatched_expected_indices = []

        # For each expected element, try to find a matching actual element
        for exp_idx, expected_val in enumerate(expected_array):
            matched = False

            # Find first unmatched actual element that equals this expected element
            for act_idx, actual_val in enumerate(actual_array):
                if not actual_matched[act_idx]:
                    # Use recursive comparison for nested structures
                    # Copy visited set for trial comparisons in unordered matching
                    # This prevents false circular reference detection when trying
                    # the same actual item against multiple expected items
                    trial_visited = visited.copy() if visited else set()
                    nested_assertions = self._compare_recursive(
                        actual=actual_val,
                        expected=expected_val,
                        ordered=ordered,
                        path=f"{value_name}[{exp_idx}]",
                        visited=trial_visited,
                        **kwargs,
                    )
                    if not nested_assertions:  # Empty list means match
                        # Found a match - update the main visited set with the trial results
                        if visited is not None:
                            visited.update(trial_visited)
                        actual_matched[act_idx] = True
                        matched = True
                        break

            if not matched:
                unmatched_expected_indices.append(exp_idx)

        # Find extra actual elements (those that weren't matched)
        extra_actual_indices = [i for i, matched in enumerate(actual_matched) if not matched]

        # Generate assertion for mismatches
        if unmatched_expected_indices or extra_actual_indices:
            # Calculate how many expected elements were successfully matched
            matched_count = len(expected_array) - len(unmatched_expected_indices)
            total_expected = len(expected_array)
            num_missing = len(unmatched_expected_indices)
            num_extra = len(extra_actual_indices)

            # Format arrays for display
            expected_display = self._format_array_for_display(expected_array)
            actual_display = self._format_array_for_display(actual_array)

            # Create contextual message based on failure type
            if num_missing == 0 and num_extra > 0:
                # All expected found, but extras present
                message = (
                    f"Array contains all expected elements ({matched_count}/{total_expected}) "
                    f"but has {num_extra} extra element(s)"
                )
            elif num_missing > 0 and num_extra == 0:
                # Some expected missing, no extras
                message = (
                    f"Array is missing {num_missing} expected element(s). Matched ({matched_count}/{total_expected})"
                )
            else:
                # Both missing and extras
                message = (
                    f"Array value mismatch (unordered). "
                    f"Matched ({matched_count}/{total_expected}), Missing: {num_missing}, Extra: {num_extra}"
                )

            assertions.append(
                EvalAssertion.create(
                    assertion_name=f"{value_name}_array_values_mismatch",
                    status=EvalStatus.FAILURE,
                    assertion_msgs=[
                        message,
                        f"Expected: {expected_display}, Got: {actual_display}",
                    ],
                )
            )

        return assertions

    def _compare_arrays_ordered(
        self,
        expected_array: list | tuple,
        actual_array: list | tuple,
        value_name: str,
        ordered: bool,
        visited: set[int] | None = None,
        **kwargs: Any,
    ) -> list[EvalAssertion]:
        """Compare arrays element-by-element in order.

        Compares arrays positionally: expected[i] must match actual[i].
        Reports length mismatches and value mismatches at specific indices.

        Args:
            expected_array: Expected array
            actual_array: Actual array
            value_name: Path name for error messages
            ordered: Whether nested sequences are order-sensitive
            visited: Set of visited object IDs for circular reference detection

        Returns:
            List of EvalAssertion (empty if match)
        """
        assertions = []

        # Compare element-by-element
        min_length = min(len(expected_array), len(actual_array))
        mismatched_indices = []

        for i in range(min_length):
            expected_val = expected_array[i]
            actual_val = actual_array[i]

            # Use recursive comparison for nested structures
            nested_assertions = self._compare_recursive(
                actual=actual_val,
                expected=expected_val,
                ordered=ordered,
                path=f"{value_name}[{i}]",
                visited=visited,
                **kwargs,
            )
            if nested_assertions:  # Non-empty list means mismatch
                mismatched_indices.append(i)
                # Accumulate nested assertions
                assertions.extend(nested_assertions)

        # Check for length mismatch and add missing/extra indices
        if len(expected_array) != len(actual_array):
            if len(actual_array) < len(expected_array):
                # Missing elements at the end
                missing_indices = list(range(len(actual_array), len(expected_array)))
                mismatched_indices.extend(missing_indices)
            else:
                # Extra elements at the end
                extra_indices = list(range(len(expected_array), len(actual_array)))
                mismatched_indices.extend(extra_indices)

        if mismatched_indices:
            # Calculate matched count
            matched_count = min_length - len([i for i in mismatched_indices if i < min_length])
            total_expected = len(expected_array)

            # Format arrays for display
            expected_display = self._format_array_for_display(expected_array)
            actual_display = self._format_array_for_display(actual_array)

            # Only add summary assertion if we don't already have detailed nested assertions
            # or if there's a length mismatch
            if len(expected_array) != len(actual_array) or not assertions:
                assertions.append(
                    EvalAssertion.create(
                        assertion_name=f"{value_name}_array_values_mismatch",
                        status=EvalStatus.FAILURE,
                        assertion_msgs=[
                            f"Array value mismatch (ordered). Matched ({matched_count}/{total_expected})",
                            f"Expected: {expected_display}, Got: {actual_display}",
                        ],
                    )
                )

        return assertions

    def _compare_objects(
        self,
        *,
        expected_object: dict | MappingProxyType,
        actual_object: Any,
        value_name: str,
        ignored_values_keys: set | None = None,
        ignore_extra_keys: bool = False,
        ordered: bool = False,
        visited: set[int] | None = None,
        **kwargs: Any,
    ) -> list[EvalAssertion]:
        """Compare object structures key-by-key.

        Validates keys match (unless ignore_extra_keys=True), then recursively
        compares values for common keys.

        Args:
            expected_object: Expected object (dict or MappingProxyType)
            actual_object: Actual value (validated to be dict-like)
            value_name: Path name for error messages
            ignored_values_keys: Keys to skip during value comparison
            ignore_extra_keys: Whether to allow extra keys in actual
            ordered: Whether nested sequences are order-sensitive
            visited: Set of visited object IDs for circular reference detection

        Returns:
            List of EvalAssertion (empty if match)
        """
        if not isinstance(expected_object, (dict, MappingProxyType)):
            raise TypeError(f"Expected object must be dict or MappingProxyType, got {type(expected_object).__name__}")

        # Check if actual is a structured object
        if not isinstance(actual_object, (dict, MappingProxyType)):
            return [
                EvalAssertion.create(
                    assertion_name=f"{value_name}_invalid_format",
                    status=EvalStatus.FAILURE,
                    assertion_msgs=[f"Expected a structured object, but got: {type(actual_object).__name__}"],
                )
            ]

        # compare values
        ref_keys = set(expected_object.keys())
        if len(ref_keys) == 0:
            raise ValueError("Expected object must have at least one key")

        actual_keys = set(actual_object.keys())

        missing_keys = ref_keys - actual_keys
        extra_keys = actual_keys - ref_keys

        assertions = []
        if missing_keys or extra_keys:
            msgs = []
            if extra_keys and not ignore_extra_keys:
                msgs.append(f"Extra keys in actual object: {sorted(extra_keys)}")
            if missing_keys:
                msgs.append(f"Missing keys in actual object: {sorted(missing_keys)}")

            # Only create assertion if there are actual error messages
            if msgs:
                assertions.append(
                    EvalAssertion.create(
                        assertion_name=f"{value_name}_keys_mismatch",
                        status=EvalStatus.FAILURE,
                        assertion_msgs=msgs,
                    )
                )

        keys_for_value_check = ref_keys & actual_keys
        if ignored_values_keys:
            keys_for_value_check -= set(ignored_values_keys)

        # Recursively compare values for each key
        for k in keys_for_value_check:
            nested_assertions = self._compare_recursive(
                actual=actual_object[k],
                expected=expected_object[k],
                ordered=ordered,
                path=f"{value_name}.{k}",
                ignored_values_keys=ignored_values_keys,
                ignore_extra_keys=ignore_extra_keys,
                visited=visited,
                **kwargs,
            )
            assertions.extend(nested_assertions)

        return assertions

    def _compare_recursive(
        self,
        actual: Any,
        expected: Any,
        ordered: bool,
        path: str,
        ignored_values_keys: set | None = None,
        ignore_extra_keys: bool = False,
        visited: set[int] | None = None,
        **kwargs: Any,
    ) -> list[EvalAssertion]:
        """Recursively compare values with circular reference protection.

        Dispatches to specialized methods based on expected type (dict, list, or primitive).
        Detects circular references by tracking visited object IDs.

        Args:
            actual: Actual value
            expected: Expected value
            ordered: Whether order matters for arrays
            path: Current path for error messages (e.g., "value.items[0]")
            ignored_values_keys: Object keys to skip during comparison
            ignore_extra_keys: Whether to allow extra keys in actual objects
            visited: Object IDs already visited (for circular reference detection)

        Returns:
            List of EvalAssertion (empty = success)

        Raises:
            ValueError: If circular reference detected in actual value
        """
        # Initialize visited set if not provided (for backwards compatibility)
        if visited is None:
            visited = set()

        # Check for circular references in container types
        # Only check actual value (we control expected, it shouldn't have circular refs)
        if isinstance(actual, (dict, MappingProxyType, list, tuple)):
            actual_id = id(actual)
            if actual_id in visited:
                raise ValueError(
                    f"Circular reference detected at path '{path}'. "
                    f"Object has already been visited during comparison. "
                    f"This indicates the actual value contains a circular reference, "
                    f"which is not supported for comparison."
                )
            visited.add(actual_id)

        # Handle None values
        if expected is None and actual is None:
            return []

        if expected is None or actual is None:
            return [
                EvalAssertion.create(
                    assertion_name=f"{path}_none_mismatch",
                    status=EvalStatus.FAILURE,
                    assertion_msgs=[f"Expected {expected}, got {actual}"],
                )
            ]

        # Dispatch based on expected type
        if isinstance(expected, (dict, MappingProxyType)):
            return self._compare_objects(
                expected_object=expected,
                actual_object=actual,
                value_name=path,
                ordered=ordered,  # Pass down for nested arrays
                ignored_values_keys=ignored_values_keys,
                ignore_extra_keys=ignore_extra_keys,
                visited=visited,
                **kwargs,
            )
        elif isinstance(expected, (list, tuple)):
            return self._compare_arrays(
                expected_array=expected,
                actual_array=actual,
                value_name=path,
                ordered=ordered,
                ignored_values_keys=ignored_values_keys,
                ignore_extra_keys=ignore_extra_keys,
                visited=visited,
                **kwargs,
            )
        else:
            # Direct comparison for all other types (NormalizedType and primitives)
            # NormalizedType.__eq__ handles alternatives automatically
            if expected != actual:
                return [
                    EvalAssertion.create(
                        assertion_name=f"{path}_mismatch",
                        status=EvalStatus.FAILURE,
                        assertion_msgs=[f"Expected {expected}, got {actual}"],
                    )
                ]
            return []

    def _format_value(self, value: Any) -> Any:
        """Format value for display in error messages.

        Extracts normalized value from NormalizedType instances.

        Args:
            value: Value to format

        Returns:
            Formatted value (.normalized for NormalizedType, otherwise unchanged)
        """
        if isinstance(value, NormalizedType):
            return value.normalized
        return value

    def _format_array_for_display(self, array: list | tuple) -> str:
        """Format array for display in error messages.

        Shows first 2 and last 1 elements with ellipsis for arrays longer than 3 elements.

        Args:
            array: Array to format

        Returns:
            Formatted string (e.g., "[1, 2, ..., 5]" or "[1, 2, 3]")
        """
        if len(array) == 0:
            return "[]"

        # Format each element
        formatted_elements = [str(self._format_value(elem)) for elem in array]

        # If array is short, show all elements
        if len(formatted_elements) <= 3:
            return f"[{', '.join(formatted_elements)}]"

        # Otherwise, show first 2 and last 1 with ellipsis
        return f"[{formatted_elements[0]}, {formatted_elements[1]}, ..., {formatted_elements[-1]}]"
