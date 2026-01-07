# WebArena-Verified

<p align="center">
  <a href="https://pypi.org/project/webarena-verified/"><img src="https://img.shields.io/pypi/v/webarena-verified.svg" alt="PyPI version"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.11+-3776AB.svg" alt="Python 3.11+"></a>
  <a href="tests"><img src="https://img.shields.io/badge/Tests-Pytest-6B2F8.svg" alt="Tests: Pytest"></a>
  <a href="https://servicenow.github.io/webarena-verified/"><img src="https://img.shields.io/badge/Docs-MkDocs-0288D1.svg" alt="Docs: MkDocs"></a>
</p>

WebArena-Verified is the verified release of the WebArena benchmark. It distributes a curated, version-controlled dataset of web tasks together with deterministic evaluators that operate on agent responses and captured network traces. The project is designed for reproducible benchmarking of web agents and provides tooling for both single-task debugging and batch evaluation.

<p align="center">
  <a href="https://servicenow.github.io/webarena-verified/">📖 Documentation</a>
</p>

## 📢 Announcements

- **January 7, 2026**: WebArena-Verified is now available on PyPI! Install it easily with `pip install webarena-verified`.
- **December 2, 2025**: We are presenting WebArena-Verified at the [Scaling Environments for Agents (SEA) Workshop](https://sea-workshop.github.io/) at NeurIPS 2025 on December 7th in San Diego. Come see us!
- **November 12, 2024**: Started initial release with collaborators to gather early feedback, catch any issues, and clarify the documentation. **Public release scheduled for December 4th, 2025.**

## 🎯 Highlights

- **Fully audited benchmark**: Every task, reference answer, and evaluator has been manually reviewed and corrected
- **Offline evaluation**: Evaluate agent runs without requiring live web environments using network trace replay
- **Deterministic scoring**: Removed LLM-as-a-judge evaluation and substring matching in favor of type-aware normalization and structural comparison
- **WebArena-Verified Hard subset**: A difficulty-prioritized 258-task subset for cost-effective evaluation

## 🚀 Quick Start

### Installation

Install from PyPI:

```bash
pip install webarena-verified
```

Or for development, clone and install from source:

```bash
git clone https://github.com/ServiceNow/webarena-verified.git
cd webarena-verified
uv sync
```

Verify the CLI is working:

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
  --config examples/configs/config.example.json
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

**With Inline Response:**
```python
# Evaluate a task with inline response
result = wa.evaluate_task(
    task_id=44,
    agent_response={
        "task_type": "NAVIGATE",
        "status": "SUCCESS",
        "retrieved_data": None
    },
    network_trace=Path("output/44/network_44.har")
)

print(f"Score: {result.score}, Status: {result.status}")
```

See the [Quick Start Guide](https://servicenow.github.io/webarena-verified/) for a complete walkthrough using example task logs.

## 📊 Dataset

- WebArena Verified dataset is in `assets/dataset/webarena-verified.json`
- The original WebArena dataset is in `assets/dataset/test.raw.json` (kept for reference)
- The WebArena Verified Hard subset task IDs are in `assets/dataset/subsets/webarena-verified-hard.json`

To export the hard subset's task data:

```bash
webarena-verified subset-export --name webarena-verified-hard --output webarena-verified-hard.json
```

See the [documentation](https://servicenow.github.io/webarena-verified/) for more info.

## 🤝 Contributing

We welcome improvements to both the dataset and the evaluation tooling. See the [Contributing Guide](https://servicenow.github.io/webarena-verified/contributing/) for guidelines, local development tips, and dataset update workflows.

## 📄 Citation

If you use WebArena-Verified in your research, please cite our paper:

```bibtex
@inproceedings{
hattami2025webarena,
title={WebArena Verified: Reliable Evaluation for Web Agents},
author={Amine El hattami and Megh Thakkar and Nicolas Chapados and Christopher Pal},
booktitle={Workshop on Scaling Environments for Agents},
year={2025},
url={https://openreview.net/forum?id=94tlGxmqkN}
}
```

## 🙏 Acknowledgements

We thank [Prof. Shuyan Zhou](https://scholars.duke.edu/person/shuyan.zhou) and [Prof. Graham Neubig](https://miis.cs.cmu.edu/people/222215657/graham-neubig) for their valuable guidance and feedback.
