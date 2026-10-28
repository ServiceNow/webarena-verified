"""Evaluate one typed response against the optional fixture, without running an agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from webarena_verified.api import WebArenaVerifiedDataReader, WebArenaVerifiedEvaluator
from webarena_verified.types.config import EnvironmentConfig, WebArenaVerifiedConfig
from webarena_verified.types.data import TaskSubset
from webarena_verified.types.task import WebArenaSite
from webarena_verified.types.tracing import NetworkTrace

if TYPE_CHECKING:
    from webarena_verified.types.eval import TaskEvalResult


def evaluate_response(dataset: Path, task_id: int, response: Any) -> TaskEvalResult:
    """Use the standard evaluator and an explicit subset for this nonstandard dataset."""
    tasks = dataset / "tasks.json"
    if not tasks.is_file():
        # Config normally falls back to the official dataset on a missing path.
        # That would silently evaluate the wrong task set in this example.
        raise FileNotFoundError(tasks)
    config = WebArenaVerifiedConfig(
        test_data_file=tasks,
        environments={WebArenaSite.SHOPPING: EnvironmentConfig(urls=["http://variant-example.invalid"])},
    )
    reader = WebArenaVerifiedDataReader(config, subset=TaskSubset.from_file(dataset / "subset.json"))
    reader.get_task_by_id(task_id)  # Fail explicitly for an ID outside this example.
    evaluator = WebArenaVerifiedEvaluator(config=config, reader=reader)
    # These are response-only tasks. Empty traces are not evidence that a browser
    # selected a variant, and this helper deliberately does not claim otherwise.
    trace = NetworkTrace(is_playwright=False, src_file=Path("<response-only>"), events=())
    return evaluator.evaluate_task(task_id=task_id, agent_response=response, network_trace=trace)


def main() -> None:
    """Score a saved response locally; no environment or model is contacted."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--task-id", type=int, required=True)
    parser.add_argument("--response", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_response(args.dataset, args.task_id, json.loads(args.response.read_text(encoding="utf-8")))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
