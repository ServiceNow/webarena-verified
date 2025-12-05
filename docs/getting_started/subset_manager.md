# Subset Manager

WebArena-Verified provides commands to manage task subsets - curated collections of tasks for focused evaluation.

## List Available Subsets

View all predefined subsets in the repository:

```bash
webarena-verified subsets-ls
```

This lists all subset files in `assets/dataset/subsets/`, including:

- `webarena-verified-hard` - Difficulty-prioritized 258-task subset (see [Hard Subset](hard_subset.md))

## Export a Subset

Export task definitions from a subset to a standalone JSON file:

=== "By name"

    ```bash
    webarena-verified subset-export \
      --name webarena-verified-hard \
      --output webarena-verified-hard.json
    ```

=== "By path"

    ```bash
    webarena-verified subset-export \
      --path assets/dataset/subsets/custom-subset.json \
      --output custom-tasks.json
    ```

The exported file contains complete task definitions for all tasks in the subset, which you can use for evaluation or analysis.

## Create a Custom Subset

Create a new subset from a custom task list:

```bash
webarena-verified subsets-create \
  --src custom_tasks.json \
  --name my-subset \
  --desc "My custom task selection"
```

This creates a new subset file in `assets/dataset/subsets/` with:

- Task IDs extracted from the source file
- Optional description
- Computed checksum for integrity verification
