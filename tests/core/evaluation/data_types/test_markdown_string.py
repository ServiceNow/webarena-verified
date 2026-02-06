"""Unit tests for MarkdownString data type."""

import pytest

from webarena_verified.core.evaluation.data_types import MarkdownString

# ===== Basic Functionality Tests =====


@pytest.mark.parametrize(
    "value,expected",
    [
        # Headers with extra spaces
        ("##  Header", "## Header"),
        ("###   Title", "### Title"),
        ("# Single space", "# Single space"),
        # List markers normalization
        ("* Item 1", "- Item 1"),
        ("+ Item 2", "- Item 2"),
        ("- Item 3", "- Item 3"),
        # Basic content preservation
        ("Plain text", "Plain text"),
        ("# Header\n\nParagraph", "# Header\n\nParagraph"),
    ],
)
def test_normalization_basic(value, expected):
    """Test that markdown strings are normalized correctly."""
    md = MarkdownString(value)
    assert md.normalized == expected
    assert isinstance(md.normalized, str)


# ===== Whitespace Normalization Tests =====


@pytest.mark.parametrize(
    "value,expected",
    [
        # Line endings
        ("Line 1\r\nLine 2", "Line 1\nLine 2"),
        ("Line 1\rLine 2", "Line 1\nLine 2"),
        ("Line 1\nLine 2", "Line 1\nLine 2"),
        # Trailing whitespace
        ("Line with spaces  \nNext line", "Line with spaces\nNext line"),
        ("Tabs\t\t\nNext", "Tabs\nNext"),
        # Multiple blank lines
        ("Para 1\n\n\n\nPara 2", "Para 1\n\nPara 2"),
        ("Start\n\n\n\n\nEnd", "Start\n\nEnd"),
        # Leading/trailing whitespace
        ("  Content  ", "Content"),
        ("\n\nContent\n\n", "Content"),
    ],
)
def test_whitespace_normalization(value, expected):
    """Test that whitespace variations are normalized."""
    md = MarkdownString(value)
    assert md.normalized == expected


# ===== Header Normalization Tests =====


@pytest.mark.parametrize(
    "value,expected",
    [
        ("##  Header", "## Header"),
        ("###   Multiple   Spaces", "### Multiple   Spaces"),  # Only first space normalized
        ("  ## Indented Header", "## Indented Header"),  # Leading whitespace preserved in (\s*)
        ("#Header", "#Header"),  # No space - left as is (regex requires at least one space/tab)
        ("# # Not a header", "# # Not a header"),
    ],
)
def test_header_normalization(value, expected):
    """Test that header spacing is normalized."""
    md = MarkdownString(value)
    assert md.normalized == expected


# ===== List Normalization Tests =====


@pytest.mark.parametrize(
    "value,expected",
    [
        # Marker normalization
        ("* Item", "- Item"),
        ("+ Item", "- Item"),
        ("- Item", "- Item"),
        # Indented lists - leading whitespace stripped by .strip() at end for single-line content
        ("  * Nested", "- Nested"),
        ("    + Deep nested", "- Deep nested"),
        ("        - Very deep", "- Very deep"),
        # Multiple spaces after marker
        ("* Item  with  spaces", "- Item  with  spaces"),
    ],
)
def test_list_normalization(value, expected):
    """Test that list markers are normalized and single-line indentation is removed."""
    md = MarkdownString(value)
    assert md.normalized == expected


def test_list_indentation_multiline():
    """Test that indentation IS preserved in multi-line content."""
    value = """- Item 1
  - Nested item
    + Deep nested item
        * Very deep"""

    expected = """- Item 1
  - Nested item
  - Deep nested item
  - Very deep"""

    md = MarkdownString(value)
    assert md.normalized == expected


# ===== Link Normalization Tests =====


@pytest.mark.parametrize(
    "value,expected",
    [
        # Links split across lines
        ("[Text\nmore text](http://example.com)", "[Text more text](http://example.com)"),
        ("[Multi\nline\nlink](url)", "[Multi line link](url)"),
        # Extra spaces in link text
        ("[Text  with   spaces](url)", "[Text with spaces](url)"),
        ("[  Padded  ](url)", "[Padded](url)"),
        # Spaces around URLs
        ("( http://example.com )", "(http://example.com)"),
        ("[Text](  http://example.com  )", "[Text](http://example.com)"),
        # Complete example
        ("[Link  text\nwith break](  url  )", "[Link text with break](url)"),
    ],
)
def test_link_normalization(value, expected):
    """Test that links are normalized correctly."""
    md = MarkdownString(value)
    assert md.normalized == expected


# ===== Equality Tests =====


@pytest.mark.parametrize(
    "value1,value2",
    [
        # Same content, different whitespace
        ("# Header", "#  Header"),
        ("* Item", "+ Item"),
        ("Text\r\n", "Text\n"),
        # Multiple blank lines
        ("Para 1\n\n\nPara 2", "Para 1\n\nPara 2"),
        # List markers
        ("* Item 1\n* Item 2", "- Item 1\n- Item 2"),
    ],
)
def test_equality_different_formats(value1, value2):
    """Test that different input formats with same content are equal."""
    md1 = MarkdownString(value1)
    md2 = MarkdownString(value2)
    assert md1 == md2
    assert md2 == md1  # Symmetric


@pytest.mark.parametrize(
    "value1,value2",
    [
        # Different content
        ("# Header 1", "# Header 2"),
        ("* Item A", "* Item B"),
        ("Text", "Different"),
        # Different structure
        ("# H1", "## H2"),
        ("- Item", "Item"),
    ],
)
def test_inequality(value1, value2):
    """Test that different markdown values are not equal."""
    md1 = MarkdownString(value1)
    md2 = MarkdownString(value2)
    assert md1 != md2
    assert md2 != md1  # Symmetric


# ===== Real-World Example Test =====


def test_real_world_example():
    """Test the real-world example from the user's message."""
    md1 = """## My Project

  ## Most Active DIY Threads
  - [Separate glued plastic parts](http://localhost:9999/f/DIY/118903/separate-glued-plastic-parts)
  - [How would you fix this dryer vent mess](http://localhost:9999/f/DIY/118923/how-would-you-fix-this-dryer-vent-mess)
  - [Basement bulkhead soffit wall framing](http://localhost:9999/f/DIY/118935/basement-bulkhead-soffit-wall-framing)
  - [GE water heater pilot light won't stay
  lit](http://localhost:9999/f/DIY/118904/ge-water-heater-pilot-light-won-t-stay-lit)
  - [Attempting to move a wall outlet in my basement a few
  inches](http://localhost:9999/f/DIY/118960/attempting-to-move-a-wall-outlet-in-my-basement-a-few-inches)
  - [AFCI outlet question](http://localhost:9999/f/DIY/118931/afci-outlet-question)
"""

    # Same content with different formatting
    md2 = """## My Project

  ##  Most Active DIY Threads
  * [Separate glued plastic parts](http://localhost:9999/f/DIY/118903/separate-glued-plastic-parts)
  * [How would you fix this dryer vent mess](http://localhost:9999/f/DIY/118923/how-would-you-fix-this-dryer-vent-mess)
  * [Basement bulkhead soffit wall framing](http://localhost:9999/f/DIY/118935/basement-bulkhead-soffit-wall-framing)
  * [GE water heater pilot light won't stay lit](http://localhost:9999/f/DIY/118904/ge-water-heater-pilot-light-won-t-stay-lit)
  * [Attempting to move a wall outlet in my basement a few inches](http://localhost:9999/f/DIY/118960/attempting-to-move-a-wall-outlet-in-my-basement-a-few-inches)
  * [AFCI outlet question](http://localhost:9999/f/DIY/118931/afci-outlet-question)
"""

    markdown1 = MarkdownString(md1)
    markdown2 = MarkdownString(md2)

    # Should normalize to the same value
    assert markdown1 == markdown2
    assert markdown1.normalized == markdown2.normalized


# ===== Alternatives Support Tests =====


@pytest.mark.parametrize(
    "values,expected_count",
    [
        # 2 alternatives with different content
        (["# Header 1", "# Header 2"], 2),
        (["* Item A", "* Item B"], 2),
        # 3+ alternatives
        (["# H1", "## H2", "### H3"], 3),
    ],
)
def test_alternatives_support(values, expected_count):
    """Test that alternatives work correctly."""
    md = MarkdownString(values)
    assert len(md.alternatives) == expected_count


def test_alternatives_equality_with_overlap():
    """Test that equality works when alternatives overlap."""
    # Expected with alternatives (different list markers)
    expected = MarkdownString(["* Item A", "+ Item B"])
    # Actual matches first alternative (uses - marker)
    actual = MarkdownString("- Item A")
    assert expected == actual
    assert actual == expected  # Symmetric


def test_alternatives_equality_with_second_alternative():
    """Test that equality works when matching second alternative."""
    expected = MarkdownString(["# Header 1", "# Header 2"])
    actual = MarkdownString("# Header 2")
    assert expected == actual
    assert actual == expected  # Symmetric


def test_alternatives_no_overlap():
    """Test that values with no overlapping alternatives don't match."""
    expected = MarkdownString(["# Header A", "# Header B"])
    actual = MarkdownString("# Header C")
    assert expected != actual
    assert actual != expected  # Symmetric


# ===== Error Handling Tests =====


@pytest.mark.parametrize(
    "invalid_value",
    [
        "",
        "   ",
        "  \n\n  ",
    ],
)
def test_empty_markdown_raises_error(invalid_value):
    """Test that empty markdown strings raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        MarkdownString(invalid_value)

    error_msg = str(exc_info.value).lower()
    assert "empty" in error_msg


def test_none_value_raises_error():
    """Test that None raises ValueError about type."""
    with pytest.raises(ValueError) as exc_info:
        MarkdownString(None)

    error_msg = str(exc_info.value).lower()
    assert "only accepts string input" in error_msg


def test_single_item_list_raises_error():
    """Test that single-item list raises ValueError (alternatives require 2+)."""
    with pytest.raises(ValueError) as exc_info:
        MarkdownString(["# Header"])

    error_msg = str(exc_info.value)
    assert "Alternatives require 2+ items" in error_msg


def test_empty_list_raises_error():
    """Test that empty list raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        MarkdownString([])

    error_msg = str(exc_info.value).lower()
    assert "alternatives require 2+ items" in error_msg


@pytest.mark.parametrize(
    "invalid_type",
    [
        123,
        45.67,
        True,
        False,
        {"a": 1},
        [1, 2, 3],
    ],
)
def test_invalid_type_raises_error(invalid_type):
    """Test that non-string types raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        MarkdownString(invalid_type)

    error_msg = str(exc_info.value).lower()
    assert "only accepts string input" in error_msg


# ===== Hash and Set/Dict Usage Tests =====


def test_hash_single_value():
    """Test that single values hash correctly."""
    md1 = MarkdownString("* Item")
    md2 = MarkdownString("- Item")  # Same content, different marker
    # Should have same hash since they're equal
    assert md1 == md2
    assert hash(md1) == hash(md2)


def test_hash_alternatives():
    """Test that alternatives hash consistently."""
    md1 = MarkdownString(["# Header 1", "# Header 2"])
    md2 = MarkdownString(["# Header 1", "# Header 2"])
    assert hash(md1) == hash(md2)


def test_hash_usable_in_set():
    """Test that MarkdownString instances can be used in sets."""
    md1 = MarkdownString("# Header")
    md2 = MarkdownString("# Header")  # Same content
    md3 = MarkdownString("## Different")  # Different content

    md_set = {md1, md2, md3}
    assert len(md_set) == 2  # md1 and md2 are equal, so only 2 unique


def test_hash_usable_in_dict():
    """Test that MarkdownString instances can be used as dict keys."""
    md1 = MarkdownString("# Header")
    md2 = MarkdownString("# Header")  # Same content
    md3 = MarkdownString("## Different")

    result_dict = {md1: "value1", md3: "value2"}
    assert len(result_dict) == 2

    # Same content should retrieve same value
    assert result_dict[md2] == "value1"


# ===== Complex Data Tests =====


def test_complex_markdown_document():
    """Test handling of complex markdown with multiple features."""
    value = """# Main Title

## Section 1

This is a paragraph with some text.

* List item 1
* List item 2
  * Nested item

## Section 2

[Link text](http://example.com)

### Subsection

More content here.
"""
    md = MarkdownString(value)
    # Should normalize successfully
    assert isinstance(md.normalized, str)
    # Check some normalizations
    assert "- List item 1" in md.normalized
    assert "- List item 2" in md.normalized
    assert "  - Nested item" in md.normalized


def test_unicode_characters():
    """Test handling of Unicode characters in markdown."""
    value = "# Hello 世界\n\n* Item with emoji 🎉"
    md = MarkdownString(value)
    # Should preserve Unicode
    assert "世界" in md.normalized
    assert "🎉" in md.normalized


def test_special_characters():
    """Test handling of special characters in markdown."""
    value = "# Title with `code` and **bold**\n\n* Item with [link](http://example.com)"
    md = MarkdownString(value)
    # Should preserve special markdown syntax
    assert "`code`" in md.normalized
    assert "**bold**" in md.normalized
    assert "[link](http://example.com)" in md.normalized


# ===== Equality Properties Tests =====


def test_equality_reflexivity():
    """Test that equality is reflexive: A == A."""
    md = MarkdownString("# Header")
    assert md == md


@pytest.mark.parametrize(
    "value1,value2",
    [
        ("* Item", "- Item"),
        ("# Header", "#  Header"),
        (["# H1", "# H2"], ["# H1", "# H2"]),
    ],
)
def test_equality_symmetry(value1, value2):
    """Test that equality is symmetric: A == B implies B == A."""
    md1 = MarkdownString(value1)
    md2 = MarkdownString(value2)
    assert md1 == md2
    assert md2 == md1


def test_equality_transitivity():
    """Test that equality is transitive: if A == B and B == C, then A == C."""
    md1 = MarkdownString("* Item")
    md2 = MarkdownString("+ Item")
    md3 = MarkdownString("- Item")

    assert md1 == md2
    assert md2 == md3
    assert md1 == md3
