"""Format variation utilities for E2E retrieval tests.

This module provides format transformation functions and a generator for cycling
through different format variations to ensure comprehensive test coverage.

Format variations include:
- Currency: $1234.56, 1234.56, $1,234.56, €1.234,56
- Date: 2024-01-15, 01/15/2024, January 15 2024, etc.
- Duration: 2hr 30min, 2 hours 30 minutes, 2h30m
- Distance: 10.5km, 6.5mi, 10500m, 10.5 km
"""

import logging
import re
from typing import Any

from dateutil import parser

logger = logging.getLogger(__name__)


class FormatVariationGenerator:
    """Generates different format variations each time it's called.

    Ensures coverage across all tasks - each task gets a different variation.
    This cycles through all variations to ensure complete coverage.
    """

    def __init__(self, variations: list[tuple[str, Any]]):
        """Initialize with list of (name, function) tuples."""
        self.variations = variations
        self.index = 0

    def next_variation(self, base_value: Any) -> tuple[str, Any]:
        """Get next variation for the given base value.

        Args:
            base_value: The original value to transform

        Returns:
            Tuple of (variation_name, transformed_value)
        """
        name, transform_func = self.variations[self.index % len(self.variations)]
        self.index += 1
        try:
            transformed = transform_func(base_value)
            return (name, transformed)
        except Exception as e:
            # If transformation fails, return original value
            logger.warning(f"Format variation {name} failed for {base_value}: {e}")
            return (name, base_value)


# Currency format variation functions
def _currency_with_symbol(value: Any) -> str:
    """Format: $1234.56"""
    if isinstance(value, dict) and "amount" in value:
        return f"${float(value['amount']):.2f}"
    return f"${float(value):.2f}"


def _currency_no_symbol(value: Any) -> str:
    """Format: 1234.56"""
    if isinstance(value, dict) and "amount" in value:
        return f"{float(value['amount']):.2f}"
    return f"{float(value):.2f}"


def _currency_comma_thousands(value: Any) -> str:
    """Format: $1,234.56"""
    if isinstance(value, dict) and "amount" in value:
        return f"${float(value['amount']):,.2f}"
    return f"${float(value):,.2f}"


def _currency_euro_format(value: Any) -> str:
    """Format: €1.234,56 (European format with dot as thousands separator)"""
    if isinstance(value, dict):
        if "amount" in value:
            val = float(value["amount"])
        else:
            val = float(value)
    else:
        val = float(value)
    # Format with comma as decimal separator and dot as thousands separator
    formatted = f"{val:,.2f}"
    # Swap comma and dot
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€{formatted}"


def _currency_negative_prefix(value: Any) -> str:
    """Format: -$1234.56"""
    if isinstance(value, dict):
        if "amount" in value:
            val = abs(float(value["amount"]))
        else:
            val = abs(float(value))
    else:
        val = abs(float(value))
    return f"-${val:.2f}"


def _currency_negative_suffix(value: Any) -> str:
    """Format: $-1234.56"""
    if isinstance(value, dict):
        if "amount" in value:
            val = abs(float(value["amount"]))
        else:
            val = abs(float(value))
    else:
        val = abs(float(value))
    return f"$-{val:.2f}"


# Date format variation functions
def _date_iso(value: Any) -> str:
    """Format: 2024-01-15 (ISO 8601)"""
    dt = parser.parse(str(value))
    return dt.strftime("%Y-%m-%d")


def _date_us(value: Any) -> str:
    """Format: 01/15/2024 (MM/DD/YYYY)"""
    dt = parser.parse(str(value))
    return dt.strftime("%m/%d/%Y")


def _date_us_short(value: Any) -> str:
    """Format: 1/15/2024 (M/D/YYYY)"""
    dt = parser.parse(str(value))
    return dt.strftime("%-m/%-d/%Y")


def _date_eu(value: Any) -> str:
    """Format: 15/01/2024 (DD/MM/YYYY)"""
    dt = parser.parse(str(value))
    return dt.strftime("%d/%m/%Y")


def _date_text_full(value: Any) -> str:
    """Format: January 15, 2024"""
    dt = parser.parse(str(value))
    return dt.strftime("%B %d, %Y")


def _date_text_short(value: Any) -> str:
    """Format: Jan 15, 2024"""
    dt = parser.parse(str(value))
    return dt.strftime("%b %d, %Y")


def _date_text_no_comma(value: Any) -> str:
    """Format: Jan 15 2024"""
    dt = parser.parse(str(value))
    return dt.strftime("%b %d %Y")


# Duration format variation functions
def _duration_hms_colon(value: Any) -> str:
    """Format: 2:30:45 or 30:45"""
    # Parse duration from various formats (e.g., "2hr 30min", "2h30m", "150min")
    text = str(value)
    # Extract hours and minutes
    hours = 0
    minutes = 0

    hour_match = re.search(r"(\d+)\s*h(?:r|our)?s?", text, re.IGNORECASE)
    min_match = re.search(r"(\d+)\s*m(?:in|inute)?s?", text, re.IGNORECASE)

    if hour_match:
        hours = int(hour_match.group(1))
    if min_match:
        minutes = int(min_match.group(1))

    # If only minutes, convert to H:MM format
    if hours == 0 and minutes > 0:
        return f"{minutes}min"
    return f"{hours}hr {minutes}min" if minutes > 0 else f"{hours}hr"


def _duration_text_long(value: Any) -> str:
    """Format: 2 hours 30 minutes"""
    text = str(value)
    hours = 0
    minutes = 0

    hour_match = re.search(r"(\d+)\s*h(?:r|our)?s?", text, re.IGNORECASE)
    min_match = re.search(r"(\d+)\s*m(?:in|inute)?s?", text, re.IGNORECASE)

    if hour_match:
        hours = int(hour_match.group(1))
    if min_match:
        minutes = int(min_match.group(1))

    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    return " ".join(parts) if parts else "0 minutes"


def _duration_short_abbrev(value: Any) -> str:
    """Format: 2h30m or 30m"""
    text = str(value)
    hours = 0
    minutes = 0

    hour_match = re.search(r"(\d+)\s*h(?:r|our)?s?", text, re.IGNORECASE)
    min_match = re.search(r"(\d+)\s*m(?:in|inute)?s?", text, re.IGNORECASE)

    if hour_match:
        hours = int(hour_match.group(1))
    if min_match:
        minutes = int(min_match.group(1))

    if hours > 0 and minutes > 0:
        return f"{hours}h{minutes}m"
    elif hours > 0:
        return f"{hours}h"
    elif minutes > 0:
        return f"{minutes}m"
    return "0m"


# Distance format variation functions
def _distance_km(value: Any) -> str:
    """Format: 10.5km or 10.5 km"""
    text = str(value)
    # Extract numeric value
    num_match = re.search(r"([\d.]+)", text)
    if num_match:
        num = float(num_match.group(1))
        # Check if it's in miles, convert to km
        if "mi" in text.lower() or "mile" in text.lower():
            num = num * 1.60934
        elif "m" in text.lower() and "k" not in text.lower():
            # meters, convert to km
            num = num / 1000
        # Format with enough precision to preserve original value
        return f"{num}km"
    return text


def _distance_miles(value: Any) -> str:
    """Format: 6.5mi or 6.5 miles"""
    text = str(value)
    num_match = re.search(r"([\d.]+)", text)
    if num_match:
        num = float(num_match.group(1))
        # Check if it's in km, convert to miles
        if "km" in text.lower():
            num = num * 0.621371
        elif "m" in text.lower() and "k" not in text.lower():
            # meters, convert to miles
            num = num * 0.000621371
        # Round to reasonable precision to avoid floating point errors
        # but maintain enough precision for tolerance comparison
        num = round(num, 6)
        return f"{num}mi"
    return text


def _distance_meters(value: Any) -> str:
    """Format: 10500m or 10500 meters"""
    text = str(value)
    num_match = re.search(r"([\d.]+)", text)
    if num_match:
        num = float(num_match.group(1))
        # Convert to meters
        if "km" in text.lower():
            num = num * 1000
        elif "mi" in text.lower() or "mile" in text.lower():
            num = num * 1609.34
        return f"{num}m"
    return text


def _distance_space_separated(value: Any) -> str:
    """Format: 10.5 km (with space)"""
    text = str(value)
    # Just add space between number and unit if not present
    return re.sub(r"(\d)([a-z])", r"\1 \2", text, flags=re.IGNORECASE)


# Create variation lists for each format type
CURRENCY_VARIATIONS = [
    ("with_symbol", _currency_with_symbol),
    ("no_symbol", _currency_no_symbol),
    ("comma_thousands", _currency_comma_thousands),
    ("euro_format", _currency_euro_format),
    # Note: Removed negative_prefix and negative_suffix variations
    # They change semantic meaning (positive -> negative) and would fail evaluation
]

DATE_VARIATIONS = [
    ("iso", _date_iso),
    ("us", _date_us),
    ("us_short", _date_us_short),
    ("eu", _date_eu),
    ("text_full", _date_text_full),
    ("text_short", _date_text_short),
    ("text_no_comma", _date_text_no_comma),
]

DURATION_VARIATIONS = [
    ("hms_colon", _duration_hms_colon),
    ("text_long", _duration_text_long),
    ("short_abbrev", _duration_short_abbrev),
]


# Duration tolerance variation functions (for testing tolerance-based comparison)
def _duration_plus_1min(value: Any) -> str:
    """Add 1 minute to duration (within tolerance)."""
    text = str(value)
    hours = 0
    minutes = 0

    hour_match = re.search(r"(\d+)\s*h(?:r|our)?s?", text, re.IGNORECASE)
    min_match = re.search(r"(\d+)\s*m(?:in|inute)?s?", text, re.IGNORECASE)

    if hour_match:
        hours = int(hour_match.group(1))
    if min_match:
        minutes = int(min_match.group(1))

    # Add 1 minute
    minutes += 1
    if minutes >= 60:
        hours += 1
        minutes -= 60

    if hours > 0:
        return f"{hours}h{minutes}m"
    return f"{minutes}m"


def _duration_minus_1min(value: Any) -> str:
    """Subtract 1 minute from duration (within tolerance)."""
    text = str(value)
    hours = 0
    minutes = 0

    hour_match = re.search(r"(\d+)\s*h(?:r|our)?s?", text, re.IGNORECASE)
    min_match = re.search(r"(\d+)\s*m(?:in|inute)?s?", text, re.IGNORECASE)

    if hour_match:
        hours = int(hour_match.group(1))
    if min_match:
        minutes = int(min_match.group(1))

    # Subtract 1 minute, but ensure at least 1 minute remains
    total_minutes = hours * 60 + minutes
    total_minutes = max(1, total_minutes - 1)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours > 0:
        return f"{hours}h{minutes}m"
    return f"{minutes}m"


def _duration_plus_2min(value: Any) -> str:
    """Add 2 minutes to duration (within tolerance)."""
    text = str(value)
    hours = 0
    minutes = 0

    hour_match = re.search(r"(\d+)\s*h(?:r|our)?s?", text, re.IGNORECASE)
    min_match = re.search(r"(\d+)\s*m(?:in|inute)?s?", text, re.IGNORECASE)

    if hour_match:
        hours = int(hour_match.group(1))
    if min_match:
        minutes = int(min_match.group(1))

    # Add 2 minutes
    minutes += 2
    if minutes >= 60:
        hours += 1
        minutes -= 60

    if hours > 0:
        return f"{hours}h{minutes}m"
    return f"{minutes}m"


# Duration out-of-tolerance variation functions (for negative testing)
def _duration_plus_outside_tolerance(value: Any) -> str:
    """Add duration that exceeds max(3min absolute, 10% relative) tolerance.

    Duration uses tolerance = max(3 minutes, 10% of max).
    For short durations (<30min), we need to exceed 3 min absolute.
    For long durations (>=30min), we need to exceed 10% relative.
    """
    text = str(value)
    hours = 0
    minutes = 0

    hour_match = re.search(r"(\d+)\s*h(?:r|our)?s?", text, re.IGNORECASE)
    min_match = re.search(r"(\d+)\s*m(?:in|inute)?s?", text, re.IGNORECASE)

    if hour_match:
        hours = int(hour_match.group(1))
    if min_match:
        minutes = int(min_match.group(1))

    total_minutes = hours * 60 + minutes

    # Calculate tolerance: max(3 min absolute, 10% relative)
    absolute_tolerance = 3
    relative_tolerance = total_minutes * 0.10

    # Add enough to exceed the tolerance (add 15% to be sure)
    tolerance = max(absolute_tolerance, relative_tolerance)
    new_total_minutes = total_minutes + int(tolerance * 1.15) + 1

    hours = new_total_minutes // 60
    minutes = new_total_minutes % 60

    if hours > 0:
        return f"{hours}h{minutes}m"
    return f"{minutes}m"


def _duration_double(value: Any) -> str:
    """Double the duration (outside tolerance)."""
    text = str(value)
    hours = 0
    minutes = 0

    hour_match = re.search(r"(\d+)\s*h(?:r|our)?s?", text, re.IGNORECASE)
    min_match = re.search(r"(\d+)\s*m(?:in|inute)?s?", text, re.IGNORECASE)

    if hour_match:
        hours = int(hour_match.group(1))
    if min_match:
        minutes = int(min_match.group(1))

    # Double the duration
    total_minutes = (hours * 60 + minutes) * 2
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours > 0:
        return f"{hours}h{minutes}m"
    return f"{minutes}m"


DURATION_TOLERANCE_VARIATIONS = [
    ("plus_1min", _duration_plus_1min),
    ("minus_1min", _duration_minus_1min),
    ("plus_2min", _duration_plus_2min),
]

DURATION_OUT_OF_TOLERANCE_VARIATIONS = [
    ("outside_tolerance", _duration_plus_outside_tolerance),
]

DISTANCE_VARIATIONS = [
    ("km", _distance_km),
    ("miles", _distance_miles),
    ("meters", _distance_meters),
    ("space_separated", _distance_space_separated),
]


# Distance tolerance variation functions (for testing tolerance-based comparison)
def _distance_plus_5m(value: Any) -> str:
    """Add 5 meters to distance (within 10m absolute tolerance)."""
    text = str(value)
    num_match = re.search(r"([\d.]+)", text)
    if num_match:
        num = float(num_match.group(1))
        # Convert to meters first
        if "km" in text.lower():
            num = num * 1000
        elif "mi" in text.lower() or "mile" in text.lower():
            num = num * 1609.34
        # Add 5 meters
        num += 5
        return f"{num}m"
    return text


def _distance_minus_5m(value: Any) -> str:
    """Subtract 5 meters from distance (within 10m absolute tolerance)."""
    text = str(value)
    num_match = re.search(r"([\d.]+)", text)
    if num_match:
        num = float(num_match.group(1))
        # Convert to meters first
        if "km" in text.lower():
            num = num * 1000
        elif "mi" in text.lower() or "mile" in text.lower():
            num = num * 1609.34
        # Subtract 5 meters (don't go below 1)
        num = max(1, num - 5)
        return f"{num}m"
    return text


def _distance_plus_1_percent(value: Any) -> str:
    """Add 1% to distance (within 2% relative tolerance)."""
    text = str(value)
    num_match = re.search(r"([\d.]+)", text)
    if num_match:
        num = float(num_match.group(1))
        # Convert to meters first
        if "km" in text.lower():
            num = num * 1000
        elif "mi" in text.lower() or "mile" in text.lower():
            num = num * 1609.34
        # Add 1%
        num = num * 1.01
        return f"{num}m"
    return text


# Distance out-of-tolerance variation functions (for negative testing)
def _distance_plus_outside_tolerance(value: Any) -> str:
    """Add distance that exceeds max(10m absolute, 2% relative) tolerance.

    Distance uses tolerance = max(10 meters, 2% of max).
    For short distances (<500m), we need to exceed 10m absolute.
    For long distances (>=500m), we need to exceed 2% relative.
    """
    text = str(value)
    num_match = re.search(r"([\d.]+)", text)
    if num_match:
        num = float(num_match.group(1))
        # Convert to meters first
        if "km" in text.lower():
            num = num * 1000
        elif "mi" in text.lower() or "mile" in text.lower():
            num = num * 1609.34

        # Calculate tolerance: max(10m absolute, 2% relative)
        absolute_tolerance = 10
        relative_tolerance = num * 0.02

        # Add enough to exceed the tolerance (add 15% to be sure)
        tolerance = max(absolute_tolerance, relative_tolerance)
        num = num + tolerance * 1.15 + 1

        return f"{num}m"
    return text


def _distance_double(value: Any) -> str:
    """Double the distance (outside tolerance)."""
    text = str(value)
    num_match = re.search(r"([\d.]+)", text)
    if num_match:
        num = float(num_match.group(1))
        # Convert to meters first
        if "km" in text.lower():
            num = num * 1000
        elif "mi" in text.lower() or "mile" in text.lower():
            num = num * 1609.34
        # Double the distance
        num = num * 2
        return f"{num}m"
    return text


DISTANCE_TOLERANCE_VARIATIONS = [
    ("plus_5m", _distance_plus_5m),
    ("minus_5m", _distance_minus_5m),
    ("plus_1_percent", _distance_plus_1_percent),
]

DISTANCE_OUT_OF_TOLERANCE_VARIATIONS = [
    ("outside_tolerance", _distance_plus_outside_tolerance),
    ("double", _distance_double),
]


# Boolean format variation functions
def _boolean_literal(value: Any) -> bool:
    """Format: True/False (Python boolean literal)"""
    return bool(value)


def _boolean_numeric(value: Any) -> int:
    """Format: 1/0 (numeric)"""
    return 1 if value else 0


def _boolean_string_lowercase(value: Any) -> str:
    """Format: "true"/"false" (lowercase string)"""
    return "true" if value else "false"


def _boolean_string_uppercase(value: Any) -> str:
    """Format: "TRUE"/"FALSE" (uppercase string)"""
    return "TRUE" if value else "FALSE"


def _boolean_string_yes_no(value: Any) -> str:
    """Format: "yes"/"no" (yes/no string)"""
    return "yes" if value else "no"


def _boolean_string_abbrev(value: Any) -> str:
    """Format: "y"/"n" (single character abbreviation)"""
    return "y" if value else "n"


def _boolean_string_on_off(value: Any) -> str:
    """Format: "on"/"off" (on/off string)"""
    return "on" if value else "off"


def _boolean_string_numeric(value: Any) -> str:
    """Format: "1"/"0" (numeric string)"""
    return "1" if value else "0"


# Number format variation functions
def _number_int(value: Any) -> int:
    """Format: 6 (integer)"""
    return int(float(value))


def _number_float(value: Any) -> float:
    """Format: 6.0 (float)"""
    return float(value)


def _number_string_int(value: Any) -> str:
    """Format: "6" (string integer)"""
    return str(int(float(value)))


def _number_string_float(value: Any) -> str:
    """Format: "6.0" (string float)"""
    return f"{float(value):.1f}"


def _number_word_form(value: Any) -> str:
    """Format: "six" (word form, for 0-20)"""
    words = [
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
    ]
    num = int(float(value))
    if 0 <= num <= 20:
        return words[num]
    # For numbers > 20, return string format
    return str(num)


# String format variation functions
def _string_original(value: Any) -> str:
    """Format: original string"""
    return str(value)


def _string_lowercase(value: Any) -> str:
    """Format: lowercase"""
    return str(value).lower()


def _string_uppercase(value: Any) -> str:
    """Format: UPPERCASE"""
    return str(value).upper()


def _string_trim_whitespace(value: Any) -> str:
    """Format: with leading/trailing whitespace"""
    return f" {value} "


def _string_extra_spaces(value: Any) -> str:
    """Format: with double spaces"""
    return re.sub(r" ", "  ", str(value))


def _string_with_quotes(value: Any) -> str:
    """Format: "value" (with quotes)"""
    return f'"{value}"'


def _string_with_period(value: Any) -> str:
    """Format: value. (with period suffix)"""
    return f"{value}."


def _string_tabs_to_spaces(value: Any) -> str:
    """Format: tabs instead of spaces"""
    return str(value).replace(" ", "\t")


def _string_en_dash(value: Any) -> str:
    """Format: spaces replaced with en-dash (–)"""
    return str(value).replace(" ", "–")  # U+2013


def _string_em_dash(value: Any) -> str:
    """Format: spaces replaced with em-dash (—)"""
    return str(value).replace(" ", "—")  # U+2014


def _string_hyphen_minus(value: Any) -> str:
    """Format: spaces replaced with hyphen-minus (-)"""
    return str(value).replace(" ", "-")  # U+002D


# Coordinates format variation functions
def _coordinates_dict_full_keys(value: Any) -> dict:
    """Format: {"latitude": ..., "longitude": ...}"""
    if isinstance(value, dict):
        lat = value.get("latitude") or value.get("lat")
        lon = value.get("longitude") or value.get("lon") or value.get("lng")
        return {"latitude": float(lat), "longitude": float(lon)}
    return value


def _coordinates_dict_short_keys(value: Any) -> dict:
    """Format: {"lat": ..., "lon": ...}"""
    if isinstance(value, dict):
        lat = value.get("latitude") or value.get("lat")
        lon = value.get("longitude") or value.get("lon") or value.get("lng")
        return {"lat": float(lat), "lon": float(lon)}
    return value


def _coordinates_dict_string_values(value: Any) -> dict:
    """Format: {"latitude": "...", "longitude": "..."}"""
    if isinstance(value, dict):
        lat = value.get("latitude") or value.get("lat")
        lon = value.get("longitude") or value.get("lon") or value.get("lng")
        return {"latitude": str(lat), "longitude": str(lon)}
    return value


def _coordinates_array(value: Any) -> list:
    """Format: [lat, lon]"""
    if isinstance(value, dict):
        lat = value.get("latitude") or value.get("lat")
        lon = value.get("longitude") or value.get("lon") or value.get("lng")
        return [float(lat), float(lon)]
    return value


def _coordinates_string_comma(value: Any) -> str:
    """Format: "lat, lon" (comma-separated string)"""
    if isinstance(value, dict):
        lat = value.get("latitude") or value.get("lat")
        lon = value.get("longitude") or value.get("lon") or value.get("lng")
        return f"{lat}, {lon}"
    return str(value)


def _coordinates_uppercase_keys(value: Any) -> dict:
    """Format: {"LATITUDE": ..., "LONGITUDE": ...}"""
    if isinstance(value, dict):
        lat = value.get("latitude") or value.get("lat")
        lon = value.get("longitude") or value.get("lon") or value.get("lng")
        return {"LATITUDE": float(lat), "LONGITUDE": float(lon)}
    return value


def _coordinates_mixed_case_keys(value: Any) -> dict:
    """Format: {"Lat": ..., "Lon": ...}"""
    if isinstance(value, dict):
        lat = value.get("latitude") or value.get("lat")
        lon = value.get("longitude") or value.get("lon") or value.get("lng")
        return {"Lat": float(lat), "Lon": float(lon)}
    return value


def _coordinates_scientific_notation(value: Any) -> dict:
    """Format: {"latitude": 4.04e+01, "longitude": -7.99e+01}"""
    if isinstance(value, dict):
        lat = value.get("latitude") or value.get("lat")
        lon = value.get("longitude") or value.get("lon") or value.get("lng")
        return {"latitude": float(f"{float(lat):.6e}"), "longitude": float(f"{float(lon):.6e}")}
    return value


# Month format variation functions
def _month_numeric_zero(value: Any) -> str:
    """Format: "01" (numeric with leading zero)"""
    import calendar

    months = list(calendar.month_name)[1:]  # Skip empty first element
    if isinstance(value, str) and value in months:
        return f"{months.index(value) + 1:02d}"
    return str(value)


def _month_numeric_no_zero(value: Any) -> str:
    """Format: "1" (numeric without leading zero)"""
    import calendar

    months = list(calendar.month_name)[1:]
    if isinstance(value, str) and value in months:
        return str(months.index(value) + 1)
    return str(value)


def _month_abbreviated(value: Any) -> str:
    """Format: "Jan" (abbreviated)"""
    import calendar

    months = list(calendar.month_name)[1:]
    if isinstance(value, str) and value in months:
        return calendar.month_abbr[months.index(value) + 1]
    return str(value)


def _month_full_name(value: Any) -> str:
    """Format: "January" (full name)"""
    return str(value)


# FullAddress format variation functions
def _address_exact_match(value: Any) -> dict:
    """Format: exact match (original)"""
    return value if isinstance(value, dict) else {}


def _address_lowercase(value: Any) -> dict:
    """Format: all lowercase"""
    if isinstance(value, dict):
        return {k: v.lower() if isinstance(v, str) else v for k, v in value.items()}
    return value


def _address_uppercase(value: Any) -> dict:
    """Format: all UPPERCASE"""
    if isinstance(value, dict):
        return {k: v.upper() if isinstance(v, str) else v for k, v in value.items()}
    return value


def _address_extra_whitespace(value: Any) -> dict:
    """Format: with extra whitespace"""
    if isinstance(value, dict):
        return {k: f" {v} " if isinstance(v, str) else v for k, v in value.items()}
    return value


def _address_state_abbrev(value: Any) -> dict:
    """Format: state abbreviation (PA <-> Pennsylvania)"""
    state_abbrev_map = {
        "Pennsylvania": "PA",
        "California": "CA",
        "New York": "NY",
        "PA": "Pennsylvania",
        "CA": "California",
        "NY": "New York",
    }
    if isinstance(value, dict) and "state" in value:
        result = value.copy()
        state = value["state"]
        result["state"] = state_abbrev_map.get(state, state)
        return result
    return value


def _address_field_order_changed(value: Any) -> dict:
    """Format: field order reversed"""
    if isinstance(value, dict):
        return dict(reversed(list(value.items())))
    return value


# Create variation lists for each format type (existing + new)
BOOLEAN_VARIATIONS = [
    ("bool_literal", _boolean_literal),
    ("numeric", _boolean_numeric),
    ("string_lowercase", _boolean_string_lowercase),
    ("string_uppercase", _boolean_string_uppercase),
    ("string_yes_no", _boolean_string_yes_no),
    ("string_abbrev", _boolean_string_abbrev),
    ("string_on_off", _boolean_string_on_off),
    ("string_numeric", _boolean_string_numeric),
]

NUMBER_VARIATIONS = [
    ("int", _number_int),
    ("float", _number_float),
    ("string_int", _number_string_int),
    ("string_float", _number_string_float),
    ("word_form", _number_word_form),
]

STRING_VARIATIONS = [
    ("original", _string_original),
    ("lowercase", _string_lowercase),
    ("uppercase", _string_uppercase),
    ("trim_whitespace", _string_trim_whitespace),
    ("extra_spaces", _string_extra_spaces),
    ("with_quotes", _string_with_quotes),
    ("with_period", _string_with_period),
    ("tabs_to_spaces", _string_tabs_to_spaces),
    ("en_dash", _string_en_dash),
    ("em_dash", _string_em_dash),
    ("hyphen_minus", _string_hyphen_minus),
]

COORDINATES_VARIATIONS = [
    ("dict_full_keys", _coordinates_dict_full_keys),
    ("dict_short_keys", _coordinates_dict_short_keys),
    ("dict_string_values", _coordinates_dict_string_values),
    ("array", _coordinates_array),
    ("string_comma", _coordinates_string_comma),
    ("uppercase_keys", _coordinates_uppercase_keys),
    ("mixed_case_keys", _coordinates_mixed_case_keys),
    ("scientific_notation", _coordinates_scientific_notation),
]

MONTH_VARIATIONS = [
    ("numeric_zero", _month_numeric_zero),
    ("numeric_no_zero", _month_numeric_no_zero),
    ("abbreviated", _month_abbreviated),
    ("full_name", _month_full_name),
]

ADDRESS_VARIATIONS = [
    ("exact_match", _address_exact_match),
    ("lowercase", _address_lowercase),
    ("uppercase", _address_uppercase),
    ("extra_whitespace", _address_extra_whitespace),
    ("state_abbrev", _address_state_abbrev),
    ("field_order_changed", _address_field_order_changed),
]


# LocationName format variation functions
def _location_name_exact(value: Any) -> str:
    """Format: exact string (original)"""
    return str(value)


def _location_name_lowercase(value: Any) -> str:
    """Format: lowercase"""
    return str(value).lower()


def _location_name_uppercase(value: Any) -> str:
    """Format: UPPERCASE"""
    return str(value).upper()


def _location_name_abbreviation(value: Any) -> str:
    """Format: common abbreviations (University -> Univ, Street -> St)"""
    s = str(value)
    abbreviations = {
        "University": "Univ",
        "university": "univ",
        "Street": "St",
        "street": "st",
        "International": "Intl",
        "international": "intl",
        "Airport": "Arpt",
        "airport": "arpt",
        "Avenue": "Ave",
        "avenue": "ave",
        "Boulevard": "Blvd",
        "boulevard": "blvd",
    }
    for full, abbrev in abbreviations.items():
        # Use word boundaries to avoid replacing parts of words
        s = re.sub(rf"\b{re.escape(full)}\b", abbrev, s)
    return s


def _location_name_ampersand_to_and(value: Any) -> str:
    """Format: & replaced with 'and'"""
    return str(value).replace("&", "and")


def _location_name_and_to_ampersand(value: Any) -> str:
    """Format: 'and' replaced with &"""
    return re.sub(r"\band\b", "&", str(value), flags=re.IGNORECASE)


def _location_name_word_order_swap(value: Any) -> str:
    """Format: swap first and last word (for multi-word strings)"""
    words = str(value).split()
    if len(words) >= 2:
        words[0], words[-1] = words[-1], words[0]
    return " ".join(words)


def _location_name_extra_whitespace(value: Any) -> str:
    """Format: with extra whitespace"""
    return f"  {value}  "


LOCATION_NAME_VARIATIONS = [
    ("exact", _location_name_exact),
    ("lowercase", _location_name_lowercase),
    ("uppercase", _location_name_uppercase),
    ("abbreviation", _location_name_abbreviation),
    ("ampersand_to_and", _location_name_ampersand_to_and),
    ("and_to_ampersand", _location_name_and_to_ampersand),
    ("word_order_swap", _location_name_word_order_swap),
    ("extra_whitespace", _location_name_extra_whitespace),
]


def distribute_variations_round_robin(
    task_ids: list[int],
    variations: list[tuple[str, Any]],
) -> dict[int, list[tuple[str, Any]]]:
    """Distribute format variations across tasks using round-robin.

    Instead of testing ALL variations for EVERY task (N variations × T tasks = N*T tests),
    this distributes variations across tasks so each task tests only one variation,
    reducing test count to max(N, T) while maintaining full variation coverage.

    Args:
        task_ids: List of task IDs that use this format type
        variations: List of (variation_name, variation_func) tuples

    Returns:
        Mapping from task_id to list containing single (variation_name, variation_func) tuple

    Example:
        task_ids = [52, 53, 54, 55, 56]
        variations = [("fmt_a", func_a), ("fmt_b", func_b), ("fmt_c", func_c)]

        Result:
        {
            52: [("fmt_a", func_a)],  # index 0 % 3 = 0
            53: [("fmt_b", func_b)],  # index 1 % 3 = 1
            54: [("fmt_c", func_c)],  # index 2 % 3 = 2
            55: [("fmt_a", func_a)],  # index 3 % 3 = 0 (cycles back)
            56: [("fmt_b", func_b)],  # index 4 % 3 = 1
        }
    """
    if not task_ids or not variations:
        return {}

    num_variations = len(variations)
    result = {}

    for i, task_id in enumerate(sorted(task_ids)):
        variation_index = i % num_variations
        result[task_id] = [variations[variation_index]]

    return result


def get_coverage_stats(
    task_ids: list[int],
    variations: list[tuple[str, Any]],
) -> dict[str, int]:
    """Get statistics about variation coverage after round-robin distribution.

    Args:
        task_ids: List of task IDs
        variations: List of (variation_name, variation_func) tuples

    Returns:
        Mapping from variation_name to count of tasks testing that variation
    """
    distribution = distribute_variations_round_robin(task_ids, variations)
    stats: dict[str, int] = {name: 0 for name, _ in variations}

    for assigned_variations in distribution.values():
        for var_name, _ in assigned_variations:
            stats[var_name] += 1

    return stats
