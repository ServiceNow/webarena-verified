"""Unit tests for NormalizedType serialization with Pydantic models.

Tests that NormalizedType subclasses (Number, Currency, String, Boolean, etc.)
properly serialize when used in Pydantic models, including:
- Direct field types
- Nested in dicts (MappingProxyType)
- Nested in lists
- Complex nested structures
- EvaluatorResult serialization (real-world use case)
"""

import json
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, model_serializer

from webarena_verified.core.evaluation.data_types import (
    URL,
    Boolean,
    Currency,
    NormalizedString,
    NormalizedType,
    Number,
)
from webarena_verified.types.eval import EvaluatorResult


# Test Models
class SimpleModel(BaseModel):
    """Model with direct NormalizedType fields."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    number: Number
    currency: Currency
    string: NormalizedString
    boolean: Boolean


class NestedDictModel(BaseModel):
    """Model with NormalizedTypes nested in dicts.

    Requires custom serializer to handle NormalizedTypes in generic dict fields.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: dict

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        """Custom serializer to handle nested NormalizedTypes."""

        def convert_nested(obj: Any) -> Any:
            if isinstance(obj, (MappingProxyType, dict)):
                return {k: convert_nested(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_nested(item) for item in obj]
            elif isinstance(obj, NormalizedType):
                return obj.normalized
            return obj

        return {"data": convert_nested(self.data)}


class NestedListModel(BaseModel):
    """Model with NormalizedTypes nested in lists.

    Requires custom serializer to handle NormalizedTypes in generic list fields.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        """Custom serializer to handle nested NormalizedTypes."""

        def convert_nested(obj: Any) -> Any:
            if isinstance(obj, (MappingProxyType, dict)):
                return {k: convert_nested(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_nested(item) for item in obj]
            elif isinstance(obj, NormalizedType):
                return obj.normalized
            return obj

        return {"items": convert_nested(self.items)}


class ComplexNestedModel(BaseModel):
    """Model with deeply nested NormalizedTypes.

    Requires custom serializer to handle NormalizedTypes in generic dict fields.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: dict

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        """Custom serializer to handle nested NormalizedTypes."""

        def convert_nested(obj: Any) -> Any:
            if isinstance(obj, (MappingProxyType, dict)):
                return {k: convert_nested(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_nested(item) for item in obj]
            elif isinstance(obj, NormalizedType):
                return obj.normalized
            return obj

        return {"data": convert_nested(self.data)}


# Basic Serialization Tests
def test_simple_normalized_types_serialize():
    """Test that NormalizedType instances serialize as direct Pydantic fields.

    Scenario: Create Pydantic model with NormalizedType fields
    Expected: model_dump_json() serializes to normalized values
    """
    model = SimpleModel(
        number=Number(42.5),
        currency=Currency("$100.00"),
        string=NormalizedString("Hello World"),
        boolean=Boolean("yes"),
    )

    # Test model_dump_json
    json_str = model.model_dump_json()
    data = json.loads(json_str)

    assert data["number"] == 42.5
    assert data["currency"] == "100.0"  # Currency normalizes to decimal string
    assert data["string"] == "hello world"  # NormalizedString lowercases
    assert data["boolean"] is True

    # Test model_dump
    dict_data = model.model_dump()
    assert dict_data["number"] == 42.5
    assert dict_data["currency"] == Decimal("100.0")  # Decimal in dict mode
    assert dict_data["string"] == "hello world"
    assert dict_data["boolean"] is True


def test_normalized_types_with_alternatives_serialize():
    """Test that NormalizedType instances with alternatives serialize correctly.

    Scenario: Create NormalizedTypes with multiple alternative values
    Expected: Serializes to first (primary) normalized value
    """
    model = SimpleModel(
        number=Number([10.0, 15.0, 20.0]),  # Multiple alternatives
        currency=Currency(["$50", "$100"]),
        string=NormalizedString(["success", "ok", "completed"]),
        boolean=Boolean("true"),
    )

    json_str = model.model_dump_json()
    data = json.loads(json_str)

    # Should serialize to first alternative (primary normalized value)
    assert data["number"] == 10.0
    assert data["currency"] == "50.0"
    assert data["string"] == "success"
    assert data["boolean"] is True


# Nested Dict Tests
def test_nested_dict_with_normalized_types_serializes():
    """Test that NormalizedTypes nested in dicts serialize correctly.

    Scenario: Create model with dict containing NormalizedType values
    Expected: Dict values serialize to normalized values
    """
    model = NestedDictModel(
        data={
            "price": Currency("$99.99"),
            "quantity": Number(5),
            "status": NormalizedString("Active"),
            "available": Boolean("yes"),
        }
    )

    json_str = model.model_dump_json()
    data = json.loads(json_str)

    assert data["data"]["price"] == "99.99"
    assert data["data"]["quantity"] == 5.0
    assert data["data"]["status"] == "active"
    assert data["data"]["available"] is True


def test_mappingproxytype_with_normalized_types_serializes():
    """Test that NormalizedTypes in MappingProxyType serialize correctly.

    Scenario: Create model with MappingProxyType containing NormalizedType values
    Expected: MappingProxyType converts to dict with normalized values
    """
    proxy_data = MappingProxyType(
        {
            "url": URL("https://example.com/path?query=value"),
            "count": Number(100),
            "label": NormalizedString("Test Label"),
        }
    )

    model = NestedDictModel(data=dict(proxy_data))

    json_str = model.model_dump_json()
    data = json.loads(json_str)

    # URL normalizes to a dict with base_url and query_params
    assert data["data"]["url"]["base_url"] == "https://example.com/path"
    assert data["data"]["url"]["query_params"] == {"query": ["value"]}
    assert data["data"]["count"] == 100.0
    assert data["data"]["label"] == "test label"


# Nested List Tests
def test_nested_list_with_normalized_types_serializes():
    """Test that NormalizedTypes nested in lists serialize correctly.

    Scenario: Create model with list containing NormalizedType instances
    Expected: List items serialize to normalized values
    """
    model = NestedListModel(
        items=[
            Number(10),
            Number(20.5),
            Currency("$50"),
            NormalizedString("Item 1"),
            Boolean("true"),
        ]
    )

    json_str = model.model_dump_json()
    data = json.loads(json_str)

    assert data["items"][0] == 10.0
    assert data["items"][1] == 20.5
    assert data["items"][2] == "50.0"
    assert data["items"][3] == "item 1"
    assert data["items"][4] is True


def test_list_of_dicts_with_normalized_types_serializes():
    """Test that NormalizedTypes in list of dicts serialize correctly.

    Scenario: Create model with list of dicts, each containing NormalizedTypes
    Expected: All nested NormalizedTypes serialize correctly
    """
    model = NestedListModel(
        items=[
            {"id": Number(1), "name": NormalizedString("First")},
            {"id": Number(2), "name": NormalizedString("Second")},
            {"id": Number(3), "name": NormalizedString("Third")},
        ]
    )

    json_str = model.model_dump_json()
    data = json.loads(json_str)

    assert len(data["items"]) == 3
    assert data["items"][0]["id"] == 1.0
    assert data["items"][0]["name"] == "first"
    assert data["items"][1]["id"] == 2.0
    assert data["items"][1]["name"] == "second"
    assert data["items"][2]["id"] == 3.0
    assert data["items"][2]["name"] == "third"


# Complex Nested Structure Tests
def test_deeply_nested_normalized_types_serialize():
    """Test that deeply nested NormalizedTypes serialize correctly.

    Scenario: Create model with complex nested structure containing NormalizedTypes
    Expected: All nested levels serialize correctly
    """
    model = ComplexNestedModel(
        data={
            "metadata": {
                "count": Number(100),
                "active": Boolean("yes"),
            },
            "items": [
                {
                    "id": Number(1),
                    "details": {
                        "price": Currency("$29.99"),
                        "url": URL("https://example.com/item/1"),
                        "tags": [
                            NormalizedString("Featured"),
                            NormalizedString("New"),
                        ],
                    },
                },
                {
                    "id": Number(2),
                    "details": {
                        "price": Currency("$49.99"),
                        "url": URL("https://example.com/item/2"),
                        "tags": [
                            NormalizedString("Sale"),
                        ],
                    },
                },
            ],
        }
    )

    json_str = model.model_dump_json()
    data = json.loads(json_str)

    # Check top level
    assert data["data"]["metadata"]["count"] == 100.0
    assert data["data"]["metadata"]["active"] is True

    # Check nested items
    assert len(data["data"]["items"]) == 2
    assert data["data"]["items"][0]["id"] == 1.0
    assert data["data"]["items"][0]["details"]["price"] == "29.99"
    # URL normalizes to dict with base_url and query_params
    assert data["data"]["items"][0]["details"]["url"]["base_url"] == "https://example.com/item/1"
    assert data["data"]["items"][0]["details"]["url"]["query_params"] == {}
    assert data["data"]["items"][0]["details"]["tags"] == ["featured", "new"]

    assert data["data"]["items"][1]["id"] == 2.0
    assert data["data"]["items"][1]["details"]["price"] == "49.99"
    # URL normalizes to dict with base_url and query_params
    assert data["data"]["items"][1]["details"]["url"]["base_url"] == "https://example.com/item/2"
    assert data["data"]["items"][1]["details"]["url"]["query_params"] == {}
    assert data["data"]["items"][1]["details"]["tags"] == ["sale"]


def test_tuple_with_normalized_types_serializes():
    """Test that NormalizedTypes in tuples serialize correctly.

    Scenario: Create model with tuple containing NormalizedType instances
    Expected: Tuple items serialize to normalized values (as list in JSON)
    """
    model = NestedListModel(
        items=[
            Number(1),
            Number(2),
            NormalizedString("Three"),
        ]
    )

    json_str = model.model_dump_json()
    data = json.loads(json_str)

    # Tuples serialize as lists in JSON
    assert isinstance(data["items"], list)
    assert data["items"][0] == 1.0
    assert data["items"][1] == 2.0
    assert data["items"][2] == "three"


# Real-World Use Case: EvaluatorResult
def test_evaluator_result_with_normalized_types_serializes():
    """Test that EvaluatorResult with NormalizedTypes serializes correctly.

    Scenario: Create EvaluatorResult with nested NormalizedTypes (real-world use case)
    Expected: model_dump_json() works without errors
    """
    # Create result similar to what AgentResponseEvaluator returns
    result = EvaluatorResult.create(
        evaluator_name="AgentResponseEvaluator",
        actual={"status": "SUCCESS", "data": ["item1", "item2"]},
        actual_normalized=MappingProxyType(
            {
                "status": NormalizedString("SUCCESS"),
                "data": (NormalizedString("item1"), NormalizedString("item2")),
            }
        ),
        expected=MappingProxyType(
            {
                "status": NormalizedString("success"),
                "data": (NormalizedString("item1"), NormalizedString("item2")),
            }
        ),
        assertions=[],
    )

    # This should not raise PydanticSerializationError
    json_str = result.model_dump_json()
    data = json.loads(json_str)

    assert data["evaluator_name"] == "AgentResponseEvaluator"
    assert data["status"] == "success"
    assert data["score"] == 1.0

    # Check normalized values
    assert data["actual_normalized"]["status"] == "success"
    assert data["actual_normalized"]["data"] == ["item1", "item2"]
    assert data["expected"]["status"] == "success"
    assert data["expected"]["data"] == ["item1", "item2"]


def test_evaluator_result_with_complex_nested_normalized_types():
    """Test EvaluatorResult with complex nested NormalizedTypes.

    Scenario: Create EvaluatorResult with deeply nested structures
    Expected: All nested NormalizedTypes serialize correctly
    """
    result = EvaluatorResult.create(
        evaluator_name="TestEvaluator",
        actual={
            "products": [
                {"id": 1, "price": "$100", "available": "yes"},
                {"id": 2, "price": "$200", "available": "no"},
            ]
        },
        actual_normalized=MappingProxyType(
            {
                "products": (
                    {
                        "id": Number(1),
                        "price": Currency("$100"),
                        "available": Boolean("yes"),
                    },
                    {
                        "id": Number(2),
                        "price": Currency("$200"),
                        "available": Boolean("no"),
                    },
                )
            }
        ),
        expected=MappingProxyType(
            {
                "products": (
                    {
                        "id": Number(1),
                        "price": Currency("$100"),
                        "available": Boolean("yes"),
                    },
                    {
                        "id": Number(2),
                        "price": Currency("$200"),
                        "available": Boolean("no"),
                    },
                )
            }
        ),
        assertions=[],
    )

    json_str = result.model_dump_json()
    data = json.loads(json_str)

    # Check nested products
    products = data["actual_normalized"]["products"]
    assert len(products) == 2
    assert products[0]["id"] == 1.0
    assert products[0]["price"] == "100.0"
    assert products[0]["available"] is True
    assert products[1]["id"] == 2.0
    assert products[1]["price"] == "200.0"
    assert products[1]["available"] is False

    # Check expected has same structure
    expected_products = data["expected"]["products"]
    assert expected_products == products


# Edge Cases
def test_none_values_serialize_correctly():
    """Test that None values mixed with NormalizedTypes serialize correctly.

    Scenario: Create model with mix of None and NormalizedType values
    Expected: None values remain None, NormalizedTypes serialize
    """
    model = NestedDictModel(
        data={
            "value1": Number(42),
            "value2": None,
            "value3": NormalizedString("test"),
            "value4": None,
        }
    )

    json_str = model.model_dump_json()
    data = json.loads(json_str)

    assert data["data"]["value1"] == 42.0
    assert data["data"]["value2"] is None
    assert data["data"]["value3"] == "test"
    assert data["data"]["value4"] is None


def test_empty_nested_structures_serialize():
    """Test that empty nested structures serialize correctly.

    Scenario: Create model with empty dicts and lists
    Expected: Serializes to empty structures
    """
    model = ComplexNestedModel(
        data={
            "empty_dict": {},
            "empty_list": [],
            "nested_empty": {"inner": {}},
        }
    )

    json_str = model.model_dump_json()
    data = json.loads(json_str)

    assert data["data"]["empty_dict"] == {}
    assert data["data"]["empty_list"] == []
    assert data["data"]["nested_empty"]["inner"] == {}


def test_mixed_types_in_list_serialize():
    """Test that lists with mixed types (including NormalizedTypes) serialize.

    Scenario: Create list with mix of primitives and NormalizedTypes
    Expected: All items serialize correctly
    """
    model = NestedListModel(
        items=[
            42,  # int
            3.14,  # float
            "string",  # str
            Number(100),  # NormalizedType
            None,  # None
            True,  # bool
            Currency("$50"),  # NormalizedType
            {"nested": NormalizedString("value")},  # dict with NormalizedType
        ]
    )

    json_str = model.model_dump_json()
    data = json.loads(json_str)

    assert data["items"][0] == 42
    assert data["items"][1] == 3.14
    assert data["items"][2] == "string"
    assert data["items"][3] == 100.0
    assert data["items"][4] is None
    assert data["items"][5] is True
    assert data["items"][6] == "50.0"
    assert data["items"][7]["nested"] == "value"
