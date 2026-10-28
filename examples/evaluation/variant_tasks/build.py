"""Compile a small, separate variant-retrieval dataset. No browser or API calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Annotated, Any, Literal, Self
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from webarena_verified.types.data import TaskSubset
from webarena_verified.types.task import WebArenaVerifiedTask

PositiveCents = Annotated[int, Field(strict=True, gt=0)]
Label = Annotated[str, Field(min_length=1, pattern=r"^\S(?:.*\S)?$")]


class Variant(BaseModel):
    """A listed size; a missing size is represented by no variant, not false stock."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    size: Label
    price_cents: PositiveCents
    in_stock: StrictBool


class Listing(BaseModel):
    """One seller's product and the variants visible through its size selector."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    sku: Label
    seller: Label
    advertised_price_cents: PositiveCents
    variants: Annotated[tuple[Variant, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def check_variants(self) -> Self:
        """Reject ambiguous size labels and invalid advertised lower bounds."""
        sizes = [variant.size.casefold() for variant in self.variants]
        if len(set(sizes)) != len(sizes):
            raise ValueError("duplicate size within a listing")
        if self.advertised_price_cents > min(variant.price_cents for variant in self.variants):
            raise ValueError("advertised price exceeds a variant price")
        return self

    def variant(self, size: str) -> Variant | None:
        """Find a size without confusing an absent variant with a sold-out one."""
        return next((variant for variant in self.variants if variant.size.casefold() == size.casefold()), None)


class Market(BaseModel):
    """Evaluator-only fixture; never include this object in the agent prompt."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    name: Label
    query: Label
    currency: Literal["USD"]
    listings: Annotated[tuple[Listing, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def check_identifiers(self) -> Self:
        """Require unambiguous identifiers and a namespace for installation."""
        for field in ("sku", "seller"):
            values = [getattr(listing, field).casefold() for listing in self.listings]
            if len(set(values)) != len(values):
                raise ValueError(f"duplicate {field}")
        if any(not listing.sku.startswith(self.query + "-") for listing in self.listings):
            raise ValueError("each SKU must start with query followed by a hyphen")
        return self


def _task(
    market: Market,
    size: str,
    task_id: int,
    intent_template: str,
    item_schema: dict[str, Any],
    retrieved_data: list[Any] | None,
) -> WebArenaVerifiedTask:
    intent = intent_template.replace("{{query}}", market.query).replace("{{size}}", size)
    return WebArenaVerifiedTask.model_validate(
        {
            "sites": ["shopping"],
            "task_id": task_id,
            "intent_template_id": task_id,
            "start_urls": [f"__SHOPPING__/catalogsearch/result/?q={quote(market.query, safe='')}"],
            "intent": intent,
            "intent_template": intent_template,
            "instantiation_dict": {"query": market.query, "size": size},
            "revision": 1,
            "eval": [
                {
                    "evaluator": "AgentResponseEvaluator",
                    "ordered": False,
                    "results_schema": {"type": "array", "items": item_schema},
                    "expected": {
                        "task_type": "retrieve",
                        "status": "SUCCESS" if retrieved_data is not None else "NOT_FOUND_ERROR",
                        "retrieved_data": retrieved_data,
                    },
                }
            ],
        }
    )


def build_tasks(market: Market, size: str = "M", first_id: int = 900_000) -> list[WebArenaVerifiedTask]:
    """Derive three typed tasks from a fixture, retaining all cheapest-price ties."""
    if not size.strip() or size != size.strip():
        raise ValueError("size must be nonempty with no surrounding whitespace")
    if type(first_id) is not int or first_id < 0:
        raise ValueError("first_id must be a nonnegative integer")
    available = [
        (listing, variant)
        for listing in market.listings
        if (variant := listing.variant(size)) is not None and variant.in_stock
    ]
    lowest = min((variant.price_cents for _, variant in available), default=None)
    winners = [
        {"seller": listing.seller, "price": f"${variant.price_cents // 100}.{variant.price_cents % 100:02d}"}
        for listing, variant in available
        if variant.price_cents == lowest
    ]
    availability = [
        {
            "seller": listing.seller,
            "listed": (variant := listing.variant(size)) is not None,
            "buyable": variant is not None and variant.in_stock,
        }
        for listing in market.listings
    ]
    return [
        _task(
            market,
            size,
            first_id,
            "Among {{query}} listings, which sellers have the lowest price for size {{size}} that is in stock? "
            "Return every tied seller and that size's price, excluding shipping and tax.",
            {"type": "object", "properties": {"seller": {"type": "string"}, "price": {"format": "currency"}}},
            winners or None,
        ),
        _task(
            market,
            size,
            first_id + 1,
            "How many {{query}} sellers have size {{size}} in stock? Count sellers, not units of stock.",
            {"type": "number"},
            [len(available)],
        ),
        _task(
            market,
            size,
            first_id + 2,
            "For each {{query}} seller, report whether size {{size}} is listed and whether it is in stock. "
            "A listed but sold-out size is not in stock; an absent size is neither listed nor in stock.",
            {
                "type": "object",
                "properties": {
                    "seller": {"type": "string"},
                    "listed": {"type": "boolean"},
                    "buyable": {"type": "boolean"},
                },
            },
            availability,
        ),
    ]


def write_dataset(fixture: Path, output: Path, *, size: str = "M", first_id: int = 900_000) -> None:
    """Create a fresh output directory, keeping evaluator secrets out of agent inputs."""
    source = fixture.read_bytes()
    market = Market.model_validate_json(source)
    tasks = build_tasks(market, size, first_id)
    ids = [task.task_id for task in tasks]
    subset = TaskSubset(
        description="Optional variant example only; not part of the official benchmark",
        task_ids=ids,
        checksum=TaskSubset.compute_checksum(ids),
    )
    files = {
        "tasks.json": [task.model_dump(mode="json") for task in tasks],
        "agent_inputs.json": [
            {"task_id": task.task_id, "intent": task.intent, "start_urls": list(task.start_urls)} for task in tasks
        ],
        "subset.json": subset.model_dump(mode="json"),
        "provenance.json": {
            "fixture_sha256": hashlib.sha256(source).hexdigest(),
            "size": size,
            "task_ids": ids,
            "currency": market.currency,
            "live_environment_validated": False,
        },
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        (output / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    """Compile the supplied demonstration fixture or an explicitly selected one."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=Path(__file__).with_name("fixture.json"))
    parser.add_argument("--output", type=Path, required=True, help="New output directory; existing paths are refused")
    parser.add_argument("--size", default="M")
    parser.add_argument("--first-id", type=int, default=900_000)
    args = parser.parse_args()
    write_dataset(args.fixture, args.output, size=args.size, first_id=args.first_id)


if __name__ == "__main__":
    main()
