# Local Development

Quick guide for working with this repository.

## Setup

!!! info "For Contributors"
    This guide is for contributors who want to develop and modify WebArena-Verified. If you're just using the package to evaluate agents, install from PyPI instead:

    ```bash
    pip install webarena-verified
    ```

    See the [Usage Guide](../getting_started/usage.md) for more information.

Install the package with development dependencies:

```bash
uv sync --dev
```

## Repository Structure

```
.
├── assets/dataset/           # Dataset files
│   ├── webarena-verified.json  # Working dataset
│   └── test.raw.json           # Original reference (read-only)
├── contributing/data/        # Dev tools for dataset management
│   ├── transforms/             # Transform scripts for bulk modifications
│   └── validators/             # Validation scripts for data integrity
├── docs/                     # Documentation source (MkDocs)
├── src/webarena_verified/    # Python package source code
│   └── types/                  # Type definitions and models
└── tasks.py                  # Invoke tasks for development
```

## Working with Documentation

This documentation is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material).


### Serve Docs Locally

To start the development server with live reload:

```bash
uv run invoke -r contributing docs-serve # (1)
```

1. The command will print the URL to access the docs
