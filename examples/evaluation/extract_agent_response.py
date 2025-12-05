#!/usr/bin/env python3
"""
Transform script that extracts JSON from agent response text.

This script handles cases where the agent response is embedded in markdown,
surrounded by extra text, or contains code blocks.

Usage:
    chmod +x examples/evaluation/extract_agent_response.py
    webarena-verified eval-tasks --task-ids 42 --output-dir output --agent-response-transform examples/evaluation/extract_agent_response.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def extract_plain_json(text: str) -> dict | None:
    """Try parsing text as plain JSON.

    Example input:
        {
          "task_type": "RETRIEVE",
          "status": "SUCCESS",
          "retrieved_data": ["value"]
        }

    Args:
        text: Raw text to parse

    Returns:
        Parsed JSON dict if successful, None otherwise
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def extract_json_from_markdown_code_block(text: str) -> dict | None:
    """Extract JSON from markdown code blocks.

    Example input:
        Here's the response:

        ```json
        {
          "task_type": "MUTATE",
          "status": "SUCCESS"
        }
        ```

    Or:
        ```
        {"task_type": "RETRIEVE", "status": "SUCCESS"}
        ```

    Args:
        text: Text that may contain markdown code blocks

    Returns:
        Parsed JSON dict if found, None otherwise
    """
    # Matches: ```json\n{...}\n``` or ```\n{...}\n```
    code_block_pattern = r'```(?:json)?\s*\n?([\s\S]*?)\n?```'
    code_blocks = re.findall(code_block_pattern, text)

    for block in code_blocks:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue

    return None


def extract_json_by_brace_matching(text: str) -> dict | None:
    """Extract JSON object by finding matching braces.

    Example input:
        Final Response

        {
          "task_type": "MUTATE",
          "status": "PERMISSION_DENIED_ERROR",
          "retrieved_data": null,
          "error_details": "Some error message"
        }

        Additional context here...

    Args:
        text: Text containing a JSON object somewhere

    Returns:
        First valid JSON object found, None otherwise
    """
    brace_count = 0
    start_idx = None

    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx is not None:
                # Found a complete JSON object
                candidate = text[start_idx:i+1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # This wasn't valid JSON, keep looking
                    start_idx = None
                    continue

    return None


def extract_json_line_by_line(text: str) -> dict | None:
    """Extract JSON by scanning lines for object start/end.

    Example input:
        Some header text
        More information
        {
          "task_type": "RETRIEVE",
          "status": "SUCCESS",
          "retrieved_data": [
            "item1",
            "item2"
          ]
        }
        Footer text

    Args:
        text: Multi-line text with JSON somewhere

    Returns:
        Parsed JSON dict if found, None otherwise
    """
    lines = text.split('\n')
    json_lines = []
    in_json = False

    for line in lines:
        stripped = line.strip()

        # Start of JSON object
        if stripped.startswith('{'):
            in_json = True
            json_lines = [stripped]
        # Inside JSON object
        elif in_json:
            json_lines.append(stripped)
            # End of JSON object
            if stripped.endswith('}') and not stripped.endswith(',}'):
                candidate = '\n'.join(json_lines)
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # Not valid JSON, keep trying
                    in_json = False
                    json_lines = []

    return None


def extract_json_from_text(text: str) -> dict:
    """Extract JSON object from text using multiple strategies.

    Tries various extraction methods in order:
    1. Plain JSON parsing
    2. Markdown code blocks
    3. Brace matching
    4. Line-by-line scanning

    Args:
        text: Raw text that may contain JSON

    Returns:
        Parsed JSON dict

    Raises:
        ValueError: If no valid JSON found in text
    """
    # Try each extraction method in order
    result = extract_plain_json(text)
    if result is not None:
        return result

    result = extract_json_from_markdown_code_block(text)
    if result is not None:
        return result

    result = extract_json_by_brace_matching(text)
    if result is not None:
        return result

    result = extract_json_line_by_line(text)
    if result is not None:
        return result

    raise ValueError("No valid JSON object found in text")


def main():
    """Main entry point for the transform script."""
    if len(sys.argv) != 2:
        print("Error: Expected agent response file path as argument", file=sys.stderr)
        sys.exit(1)

    agent_response_file = Path(sys.argv[1])

    if not agent_response_file.exists():
        print(f"Error: File not found: {agent_response_file}", file=sys.stderr)
        sys.exit(1)

    # Read the file
    text = agent_response_file.read_text()

    try:
        # Extract JSON from text
        data = extract_json_from_text(text)

        # Validate that it has the expected structure
        if not isinstance(data, dict):
            print("Error: Extracted JSON is not an object/dict", file=sys.stderr)
            sys.exit(1)

        # Set default values for missing fields
        expected_fields = ['task_type', 'status', 'retrieved_data', 'error_details']
        for field in expected_fields:
            if field not in data:
                data[field] = ""
                print(f"Warning: Missing field '{field}', set to empty string", file=sys.stderr)

        # Output the clean JSON to stdout
        print(json.dumps(data, indent=2))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
