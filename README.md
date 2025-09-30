# WebArena-Verified

<p align="center">
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.11+-3776AB.svg" alt="Python 3.11+"></a>
  <a href="tests"><img src="https://img.shields.io/badge/Tests-Pytest-6B2F8.svg" alt="Tests: Pytest"></a>
</p>

WebArena-Verified is the verified release of the WebArena benchmark. It distributes a curated, version-controlled dataset of web tasks together with deterministic evaluators that operate on agent responses and captured network traces. The project is designed for reproducible benchmarking of web agents and provides tooling for both single-task debugging and batch evaluation.


## 📢 Announcements

- **December 2, 2025**: We are presenting WebArena-Verified at the [Scaling Environments for Agents (SEA) Workshop](https://sea-workshop.github.io/) at NeurIPS 2025 on December 7th in San Diego. Come see us!
- **November 12, 2024**: Started initial release with collaborators to gather early feedback, catch any issues, and clarify the documentation. **Public release scheduled for December 4th, 2025.**

## 🎯 Highlights

- **Fully audited benchmark**: Every task, reference answer, and evaluator has been manually reviewed and corrected
- **Offline evaluation**: Evaluate agent runs without requiring live web environments using network trace replay
- **Deterministic scoring**: Removed LLM-as-a-judge evaluation and substring matching in favor of type-aware normalization and structural comparison
- **WebArena-Verified Hard subset**: A difficulty-prioritized 258-task subset for cost-effective evaluation

## 🚀 Quick Start

### 1. Set up an environment

```bash
git clone https://github.com/ServiceNow/platform-labs-webarena-verified.git
cd platform-labs-webarena-verified
uv venv  # or: python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
# Install core package
uv sync
```

### 3. Verify the CLI

```bash
webarena-verified --help
```

## 🧪 Evaluate A Task

Evaluate a task using the CLI or programmatically:

**CLI:**
```bash
webarena-verified eval-tasks \
  --task-ids 108 \
  --output-dir examples/agent_logs/demo \
  --config examples/config.json
```

**Library:**

Start by creating a `WebArenaVerified` instance with your environment configuration:

```python
from pathlib import Path
from webarena_verified.api import WebArenaVerified
from webarena_verified.types.config import WebArenaVerifiedConfig

# Initialize with configuration
config = WebArenaVerifiedConfig(
    environments={
        "__GITLAB__": {
            "urls": ["http://localhost:8012"],
            "credentials": {"username": "root", "password": "demopass"}
        }
    }
)
wa = WebArenaVerified(config=config)

# Get a single task
task = wa.get_task(44)
print(f"Task intent: {task.intent}")
```

Once you have your agent's output, evaluate it against the task definition:

**With Files:**
```python
# Evaluate a task with file paths
result = wa.evaluate_task(
    task_id=44,
    agent_response=Path("output/44/agent_response_44.json"),
    network_trace=Path("output/44/network_44.har")
)

print(f"Score: {result.score}, Status: {result.status}")
```

**With Content:**
```python
import json

# Evaluate a task with direct content
result = wa.evaluate_task(
    task_id=44,
    agent_response={
        "task_type": "NAVIGATE",
        "status": "SUCCESS",
        "retrieved_data": None
    },
    network_trace=json.loads(Path("output/44/network_44.har").read_text())
)

print(f"Score: {result.score}, Status: {result.status}")
```


## 📊 Dataset

Coming soon (December 4th, 2025)

## 🤝 Contributing

We welcome improvements to both the dataset and the evaluation tooling.

## 📚 Citation

Coming soon (December 4th, 2025)
