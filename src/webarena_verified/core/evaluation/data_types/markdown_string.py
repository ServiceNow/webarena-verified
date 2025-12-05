"""Markdown string data type for normalized comparison."""

import re
from typing import Any

from .base import NormalizedType


class MarkdownString(NormalizedType[str]):
    """Markdown string normalization for basic comparison.

    This type normalizes simple markdown text including headers, lists, and links.
    It handles common formatting variations like line endings, whitespace, list markers,
    and link formatting to enable structural comparison regardless of minor formatting
    differences.

    Input must be a string containing markdown. Non-string inputs will raise ValueError.

    Alternatives: To specify alternative valid values, pass a list of 2+ markdown strings:
        MarkdownString(['# Header', '## Header'])  # Two alternative markdown formats

    Examples:
        >>> MarkdownString('##  Most Active DIY Threads\\n  * Item 1')
        MarkdownString('## Most Active DIY Threads\\n  - Item 1')

        >>> MarkdownString('[GE water heater pilot light won\\'t stay\\nlit](http://example.com)')
        MarkdownString('[GE water heater pilot light won\\'t stay lit](http://example.com)')

        >>> MarkdownString('# Header\\n\\n\\n\\nContent')
        MarkdownString('# Header\\n\\nContent')
    """

    def _normalize_string(self, s: str) -> str:
        """Override to skip Unicode/lowercase normalization for markdown content.

        Markdown strings should preserve their exact content including:
        - Unicode characters
        - Case sensitivity
        - Special characters

        We only strip leading/trailing whitespace.
        """
        return s.strip()

    def _type_normalize(self, value: Any) -> str:
        """Normalize markdown string for comparison.

        Handles:
        - Line endings (Windows/Mac/Linux)
        - Trailing whitespace
        - Multiple blank lines
        - Inconsistent list markers
        - Header spacing
        - Link line breaks

        Args:
            value: Must be a string containing markdown

        Returns:
            Normalized markdown string

        Raises:
            ValueError: If value is not a string or is empty
        """
        # Only accept strings
        if not isinstance(value, str):
            raise ValueError(f"MarkdownString only accepts string input. Got {type(value).__name__}: {value!r}")

        # Handle empty strings
        if not value:
            raise ValueError("Markdown string is empty")

        content = value

        # Normalize line endings to \n
        content = content.replace("\r\n", "\n").replace("\r", "\n")

        # Remove trailing whitespace from each line
        content = re.sub(r"[ \t]+$", "", content, flags=re.MULTILINE)

        # Normalize multiple blank lines to double newline
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Normalize headers - ensure single space after #
        content = re.sub(r"^(\s*)(#{1,6})[ \t]+", r"\1\2 ", content, flags=re.MULTILINE)

        # Normalize list markers - convert *, + to -
        content = re.sub(r"^(\s*)[\*\+][ \t]+", r"\1- ", content, flags=re.MULTILINE)

        # Normalize list indentation - convert multiple spaces to 2 spaces
        content = re.sub(r"^[ \t]+(-)", r"  \1", content, flags=re.MULTILINE)

        # Fix links split across lines - join them
        # Pattern: [text
        # more text](url)
        content = re.sub(
            r"\[([^\]]*?)\n\s*([^\]]*?)\](\([^\)]+\))",
            lambda m: f"[{m.group(1)} {m.group(2)}]{m.group(3)}",
            content,
        )

        # Remove extra spaces in link text
        content = re.sub(r"\[([^\]]+)\]", lambda m: "[" + " ".join(m.group(1).split()) + "]", content)

        # Remove spaces around link URLs
        content = re.sub(r"\(\s*([^\)]+?)\s*\)", r"(\1)", content)

        # Strip leading/trailing whitespace from entire content
        content = content.strip()

        return content
