# Updating WebArena-Verified Data

This guide shows you how to update the WebArena-Verified dataset.

## Overview

The dataset uses git for version control to track all changes through standard git commits.

**Dataset Location:**

- Working dataset: `assets/dataset/webarena-verified.json`
- Original dataset: `assets/dataset/test.raw.json` (reference only, not used)

## Prerequisites

Install the dev dependencies:

```bash
uv sync --dev
```

## How to Update the Dataset

1. **Update the data** - Edit the dataset directly
2. **Create a pull request** - Submit your changes for review

### Step 1: Edit the Dataset

Edit the dataset file directly. For example, to fix a typo in task ID 94:

**Before:**

```json
{
  "task_id": 94,
  "intent_template": "Telll me the grand total of invoice {{id}}.",
  ...
}
```

**After:**

```json
{
  "task_id": 94,
  "intent_template": "Tell me the grand total of invoice {{id}}.",
  ...
}
```

### Step 2: Submit a Pull Request

Once you've validated your changes, open a new pull request to merge the changes.
