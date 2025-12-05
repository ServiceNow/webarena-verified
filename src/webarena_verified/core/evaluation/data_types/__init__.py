"""Data type definitions for evaluation framework."""

from .base import NormalizedType
from .base64_string import Base64String
from .boolean import Boolean
from .coordinates import Coordinates
from .currency import Currency
from .date import Date
from .distance import Distance
from .duration import Duration
from .empty import Empty
from .full_address import FullAddress
from .json_string import JsonString
from .location_name import LocationName
from .markdown_string import MarkdownString
from .month import Month
from .number import Number
from .string import NormalizedString
from .string_list import StringList
from .url import URL

TYPE_REGISTRY: dict[str, type[NormalizedType]] = {
    "currency": Currency,
    "date": Date,
    "duration": Duration,
    "distance": Distance,
    "coordinates": Coordinates,
    "full_address": FullAddress,
    "url": URL,
    "boolean": Boolean,
    "string": NormalizedString,
    "string_list": StringList,
    "number": Number,
    "integer": Number,
    "month": Month,
    "null": Empty,
    "json": JsonString,
    "markdown": MarkdownString,
    "base64": Base64String,
    "location-name": LocationName,
}

__all__ = [
    "Base64String",
    "Boolean",
    "Coordinates",
    "Currency",
    "Date",
    "Distance",
    "Duration",
    "Empty",
    "FullAddress",
    "LocationName",
    "JsonString",
    "MarkdownString",
    "Month",
    "NormalizedString",
    "NormalizedType",
    "Number",
    "StringList",
    "URL",
]
