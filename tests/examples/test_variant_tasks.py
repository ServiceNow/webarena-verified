"""Offline semantic and evaluator checks for the optional variant task compiler."""

import copy
import json
from pathlib import Path

import pytest
from jinja2 import Template
from pydantic import ValidationError

from examples.evaluation.variant_tasks.build import Market, build_tasks, write_dataset
from examples.evaluation.variant_tasks.evaluate import evaluate_response
from webarena_verified.types.eval import EvalStatus

FIXTURE = Path(__file__).parents[2] / "examples/evaluation/variant_tasks/fixture.json"


@pytest.fixture
def market_data():
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def dataset(tmp_path):
    output = tmp_path / "variant-tasks"
    write_dataset(FIXTURE, output)
    return output


def answer(data, status="SUCCESS"):
    return {"task_type": "retrieve", "status": status, "retrieved_data": data}


def test_keys_distinguish_card_price_sold_out_and_absent(market_data):
    tasks = build_tasks(Market.model_validate(market_data))
    assert tasks[0].expected_agent_response.retrieved_data == [{"seller": "Cedar", "price": "$14.00"}]
    assert tasks[1].expected_agent_response.retrieved_data == [2]
    assert tasks[2].expected_agent_response.retrieved_data == [
        {"seller": "Alder", "listed": True, "buyable": True},
        {"seller": "Birch", "listed": True, "buyable": False},
        {"seller": "Cedar", "listed": True, "buyable": True},
        {"seller": "Dune", "listed": False, "buyable": False},
    ]
    for task in tasks:
        assert Template(task.intent_template).render(**task.instantiation_dict) == task.intent


@pytest.mark.parametrize(
    ("task_id", "data", "expected"),
    [
        (900_000, [{"seller": "Cedar", "price": "$14.00"}], EvalStatus.SUCCESS),
        (900_000, [{"seller": "Cedar", "price": "14 USD"}], EvalStatus.SUCCESS),
        (900_000, [{"seller": "Alder", "price": "$8.00"}], EvalStatus.FAILURE),
        (900_000, [{"seller": "Birch", "price": "$12.00"}], EvalStatus.FAILURE),
        (900_000, [{"seller": "Cedar", "price": "$11.00"}], EvalStatus.FAILURE),
        (900_001, [2], EvalStatus.SUCCESS),
        (900_001, [3], EvalStatus.FAILURE),
    ],
)
def test_standard_evaluator_rejects_plausible_wrong_answers(dataset, task_id, data, expected):
    result = evaluate_response(dataset, task_id, answer(data))
    assert result.status == expected


def test_extra_winner_is_rejected(dataset):
    response = answer([{"seller": "Cedar", "price": "$14.00"}, {"seller": "Alder", "price": "$20.00"}])
    assert evaluate_response(dataset, 900_000, response).status == EvalStatus.FAILURE


def test_sold_out_and_absent_are_not_interchangeable(dataset, market_data):
    data = build_tasks(Market.model_validate(market_data))[2].expected_agent_response.model_dump()["retrieved_data"]
    assert evaluate_response(dataset, 900_002, answer(list(reversed(data)))).status == EvalStatus.SUCCESS
    wrong = copy.deepcopy(data)
    wrong[1]["listed"] = False
    assert evaluate_response(dataset, 900_002, answer(wrong)).status == EvalStatus.FAILURE


def test_ties_require_every_winner(market_data, tmp_path):
    market_data["listings"][0]["variants"][1]["price_cents"] = 1400
    fixture = tmp_path / "tie.json"
    fixture.write_text(json.dumps(market_data))
    output = tmp_path / "tasks"
    write_dataset(fixture, output)
    both = [{"seller": "Alder", "price": "$14.00"}, {"seller": "Cedar", "price": "$14.00"}]
    assert evaluate_response(output, 900_000, answer(both)).status == EvalStatus.SUCCESS
    assert evaluate_response(output, 900_000, answer(both[:1])).status == EvalStatus.FAILURE


def test_no_available_variant_has_explicit_not_found_result(tmp_path):
    output = tmp_path / "tasks"
    write_dataset(FIXTURE, output, size="XXL")
    assert evaluate_response(output, 900_000, answer(None, "NOT_FOUND_ERROR")).status == EvalStatus.SUCCESS
    assert evaluate_response(output, 900_001, answer([0])).status == EvalStatus.SUCCESS
    assert evaluate_response(output, 900_000, answer([], "SUCCESS")).status == EvalStatus.FAILURE


@pytest.mark.parametrize("field", ["sku", "seller"])
def test_duplicate_identifiers_are_rejected(market_data, field):
    market_data["listings"][1][field] = market_data["listings"][0][field]
    with pytest.raises(ValidationError, match=f"duplicate {field}"):
        Market.model_validate(market_data)


@pytest.mark.parametrize(
    "mutation", ["duplicate-size", "negative-price", "fractional-cents", "string-stock", "bad-bound"]
)
def test_invalid_fixture_cannot_produce_keys(market_data, mutation):
    listing = market_data["listings"][0]
    if mutation == "duplicate-size":
        listing["variants"][1]["size"] = "s"
    elif mutation == "negative-price":
        listing["variants"][0]["price_cents"] = -1
    elif mutation == "fractional-cents":
        listing["variants"][0]["price_cents"] = 1.5
    elif mutation == "string-stock":
        listing["variants"][0]["in_stock"] = "false"
    else:
        listing["advertised_price_cents"] = 9999
    with pytest.raises(ValidationError):
        Market.model_validate(market_data)


def test_output_is_reproducible_and_agent_input_has_no_keys(dataset, tmp_path):
    other = tmp_path / "again"
    write_dataset(FIXTURE, other)
    for path in dataset.iterdir():
        assert path.read_bytes() == (other / path.name).read_bytes()
    inputs = json.loads((dataset / "agent_inputs.json").read_text())
    assert all(set(task) == {"task_id", "intent", "start_urls"} for task in inputs)
    assert "Cedar" not in (dataset / "agent_inputs.json").read_text()
    assert not json.loads((dataset / "provenance.json").read_text())["live_environment_validated"]


def test_existing_output_is_not_overwritten(dataset):
    before = (dataset / "tasks.json").read_bytes()
    with pytest.raises(FileExistsError):
        write_dataset(FIXTURE, dataset)
    assert (dataset / "tasks.json").read_bytes() == before


def test_missing_dataset_does_not_fall_back_to_official_tasks(tmp_path):
    with pytest.raises(FileNotFoundError):
        evaluate_response(tmp_path, 0, answer([]))


def test_unknown_task_id_fails_explicitly(dataset):
    with pytest.raises(ValueError, match="not found"):
        evaluate_response(dataset, 0, answer([]))
