# Optional variant-retrieval tasks

This example compiles a small shopping fixture into typed retrieval tasks and
checks responses with WebArena-Verified's existing evaluator. It is the
**evaluation layer of a proposed environment extension**, related to
[issue #60](https://github.com/ServiceNow/webarena-verified/issues/60).

It does not install Magento products, change a Docker image, or add tasks to the
812-task benchmark. The fixture's products do not exist in the standard shopping
image. Live environment integration is still required before these tasks can be
used for browser-agent benchmarking.

## What the fixture distinguishes

A listing's lowest advertised price need not be the price of the requested size.
A size can also be listed but sold out, or absent from the listing entirely. The
four synthetic sellers below separate these cases without misleading labels.

| Seller | Advertised price | Size M | Size M price |
|---|---:|---|---:|
| Alder | $8.00 | In stock | $20.00 |
| Birch | $9.00 | Listed, sold out | $12.00 |
| Cedar | $11.00 | In stock | $14.00 |
| Dune | $10.00 | Absent | Not applicable |

The compiler derives three tasks directly from `fixture.json`:

1. Return every seller tied for the cheapest in-stock target size and its price.
2. Count sellers with that size in stock, not units of inventory.
3. Report separately whether each seller lists the size and whether it is in stock.

Prices use integer cents in the fixture. All cheapest-price ties are retained;
if no seller can supply the size, the first task expects `NOT_FOUND_ERROR` and
the count expects zero. The fixture validator rejects duplicate sellers, SKUs
and size labels, non-integer or non-positive prices, non-boolean stock values,
and advertised prices above a variant's price. USD is the only supported currency.

## Reproduce the offline example

From the repository root, with Python 3.11+ and `uv`:

```bash
uv sync --frozen --group dev
uv run --no-sync pytest tests/examples/test_variant_tasks.py

variant_demo_dir=$(mktemp -d)
uv run --no-sync python examples/evaluation/variant_tasks/build.py \
  --output "$variant_demo_dir/tasks"

cat > "$variant_demo_dir/response.json" <<'JSON'
{
  "task_type": "retrieve",
  "status": "SUCCESS",
  "retrieved_data": [{"seller": "Cedar", "price": "$14.00"}]
}
JSON

uv run --no-sync python examples/evaluation/variant_tasks/evaluate.py \
  --dataset "$variant_demo_dir/tasks" \
  --task-id 900000 \
  --response "$variant_demo_dir/response.json"
```

The final command should report `"status": "success"`. This is a manually
constructed response testing the evaluator, not a recorded agent result.
Changing the seller to `Birch` and price to `$12.00` must fail because its M size
is sold out. Changing the price to Cedar's advertised `$11.00` must also fail.
These checks make no model, browser or network calls after dependencies are installed.

`--fixture`, `--size` and `--first-id` allow another validated fixture and target.
The default IDs 900000-900002 are provisional and local to this example, not
allocated benchmark IDs. Use a fresh output directory on each run; the compiler
refuses to overwrite an existing one.

| Output | Intended recipient |
|---|---|
| `agent_inputs.json` | Agent: task ID, question and starting URL only |
| `tasks.json` | Evaluator: complete task definitions, schemas and expected answers |
| `subset.json` | Evaluator: explicit task IDs and their checksum |
| `provenance.json` | Researcher: source-fixture hash, target size and task IDs |

Keep `fixture.json` and `tasks.json` outside the agent's accessible workspace.
The expected answers must not be included in its prompt or browser page. A
dataset compiled twice from the same bytes and arguments is byte-identical.

The evaluator helper uses the explicit subset API because the default reader
correctly requires 812 tasks. It does not weaken that check or pad the example
with unrelated tasks. It rejects a missing dataset instead of silently falling
back to the official dataset.

## Contract for the environment adapter

The browser-facing adapter is intentionally outside this first slice. Before
calling this an interaction-gated benchmark, an implementation must establish:

- **Isolation:** use a dedicated shopping instance. Namespace created products
  with the fixture's query prefix, record product IDs and configuration changes,
  and provide idempotent setup and scoped teardown. Do not modify a standard
  benchmark instance in place.
- **Catalogue agreement:** install exactly the fixture's sellers and sizes.
  The search query must find exactly those listings. Cards must display the
  specified advertised prices; selection must reveal the selected variant's
  price and stock. A sold-out size must remain distinguishable from an absent one.
- **Observation model:** declare whether agents may inspect page source,
  JavaScript state or arbitrary network endpoints. Hiding rendered text alone
  does not hide data embedded in the page. An unrestricted agent may retrieve
  such data without using the size selector.
- **Validation:** pin the shopping image digest and adapter version. On a fresh
  instance, check every rendered listing and variant against the fixture,
  verify reset/teardown, and run existing shopping smoke tests. Include a
  negative control that detects target-price leakage before selection.
- **Evaluation scope:** these tasks score the committed answer only. They do
  not prove that the agent performed a particular interaction, measure answer
  readability, or establish resistance to prompt injection. Trace-based evidence
  checks would be a separate, explicitly specified addition.

The [research prototype referenced in issue #60](https://github.com/kr7001/fyp-shopping-agent)
provides one possible adapter starting point. Its current theme sends an encoded
price table to the browser, so it supports a rendered-observation condition, not
the stronger claim that prices are inaccessible through page inspection. Its
Magento-derived template is not copied into this example; adapting it requires
preserving the applicable licence notices.

## Remaining work before benchmark inclusion

- Agree with maintainers on extension location and official task IDs.
- Package and test the opt-in adapter on a fresh pinned shopping image.
- Add live browser tests for selected prices, absent/sold-out sizes and reset.
- Have the task wording and keys independently reviewed.

No browser-agent performance or live gating result is claimed here. The tests
cover fixture validation, answer derivation, price/stock confusions, ties,
empty availability, evaluator normalisation, and separation of agent inputs
from evaluator keys.

This new example and fixture were prepared by Kayleen Lee Kai Rong with AI
coding assistance and are contributed under the repository's Apache-2.0 licence.
