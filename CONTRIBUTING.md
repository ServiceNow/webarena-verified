# Contributing to WebArena-Verified

Thank you for your interest in contributing to WebArena-Verified!

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker (for environment testing)

### Setup

```bash
# Clone the repository
git clone https://github.com/ServiceNow/webarena-verified.git
cd webarena-verified

# Install dependencies and pre-commit hooks
uv sync --all-groups --all-extras
uv run pre-commit install
```

## Repository Structure

```
.
├── assets/dataset/           # Dataset files
│   ├── webarena-verified.json  # Working dataset
│   └── test.raw.json           # Original reference (read-only)
├── dev/                      # Dev tools and invoke tasks
│   ├── data/transforms/        # Transform scripts for bulk modifications
│   └── data/validators/        # Validation scripts for data integrity
├── docs/                     # Documentation source (MkDocs)
├── src/webarena_verified/    # Python package source code
└── tests/                    # Test suite
```

## Development Commands

All development tasks use [Invoke](https://www.pyinvoke.org/):

```bash
# Format and check code (ruff + ty)
inv -r dev code-format-and-check

# Run tests
uv run pytest

# Serve documentation locally
inv -r dev docs-serve

# Build documentation
inv -r dev docs-build
```

## Code Style

This project uses automated tools for consistent code style:

- **[Ruff](https://github.com/astral-sh/ruff)** - Linting and formatting (line length: 120)
- **[ty](https://github.com/astral-sh/ty)** - Type checking

Pre-commit hooks run automatically. To run manually:

```bash
pre-commit run --all-files
```

## How to Contribute

### Reporting Issues

- Search [existing issues](https://github.com/ServiceNow/webarena-verified/issues) before creating a new one
- Include clear steps to reproduce bugs
- Provide environment details (OS, Python version)

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run checks: `inv -r dev code-format-and-check`
5. Run tests: `uv run pytest`
6. Commit with a clear message
7. Push and open a pull request

## Updating the Dataset

The dataset uses git for version control.

**Dataset Location:** `assets/dataset/webarena-verified.json`

**Example:** Fix a typo in task ID 94:

```json
// Before
{
  "task_id": 94,
  "intent_template": "Telll me the grand total of invoice {{id}}."
}

// After
{
  "task_id": 94,
  "intent_template": "Tell me the grand total of invoice {{id}}."
}
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/webarena_verified --cov-report=html

# Run specific tests
uv run pytest tests/path/to/test.py -v
```

## Documentation

Documentation is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/):

```bash
# Serve locally with live reload
inv -r dev docs-serve

# Build static site
inv -r dev docs-build
```

Documentation is automatically deployed to GitHub Pages by CI when changes are merged to main.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
