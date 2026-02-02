# Hard Subset

## Overview

**WebArena-Verified Hard** is a carefully curated subset of 258 challenging tasks selected from the full 812-task benchmark. This subset focuses on genuinely difficult tasks while maintaining broad site coverage and category diversity.

**Why use the hard subset?**

- **Cost-effective evaluation**: Evaluate on 258 tasks instead of 812 while preserving discriminative power
- **Difficulty-prioritized**: 48.1% of tasks have predicted success rate ≤ 0.20
- **Representative coverage**: Maintains balanced distribution across sites and task categories

## Task Selection

The subset contains:

| Site | Tasks | Multi-site | Total |
|:-----|------:|:----------:|------:|
| Shopping Admin | 55 | - | 55 |
| GitLab | 57 | - | 57 |
| Reddit | 42 | - | 42 |
| Shopping | 56 | - | 56 |
| Multi-site | - | 48 | 48 |
| **Overall** | **210** | **48** | **258** |

!!! note "Why no single-site Map tasks?"
    Single-site Map tasks are excluded from the hard subset due to contamination issues identified during benchmark diagnosis. All 48 multi-site tasks (including 19 that involve Map) are included.

## How It Was Created

The subset was constructed using a principled difficulty modeling approach:

1. **Difficulty Quantification**: Estimated task hardness from multi-agent trajectories (8 agents) using a survival-style GLMM that models success probability as a function of steps taken
2. **Task Ranking**: Ranked tasks by difficulty coefficient (β_t), where larger values indicate harder tasks
3. **Category Balancing**: Within each per-site category, selected up to κ tasks based on hardness probability:
    - Default cap: κ_default = 3 tasks per category
    - Easy category cap: κ_easy = 2 tasks (for categories with median success ≥ 0.85)
4. **Site Coverage**: Single-site Map excluded due to contamination; all 48 multi-site tasks included

**Selection criteria:**

- τ_hard = 0.20 (threshold for "hard" classification)
- τ_easy = 0.85 (threshold for "easy" category identification)
- 16.7% of tasks have ≥ 0.90 probability of being hard

The hardest categories involve multi-step state-changing interactions (forms, data updates), while easiest are browse/read-only tasks.

## Usage

Export the hard subset tasks to a JSON file:

=== "uvx"

    ```bash
    uvx webarena-verified subset-export \
      --name webarena-verified-hard \
      --output webarena-verified-hard.json
    ```

=== "Docker"

    ```bash
    docker run --rm \
      -v ./:/output \
      am1n3e/webarena-verified:latest \
      subset-export \
        --name webarena-verified-hard \
        --output /output/webarena-verified-hard.json
    ```

=== "CLI"

    ```bash
    webarena-verified subset-export \
      --name webarena-verified-hard \
      --output webarena-verified-hard.json
    ```

The exported file contains the full task definitions for all 258 tasks in the subset.

For more subset management commands, see the [Subset Manager](subset_manager.md) guide.

## Reference

For detailed methodology and analysis, see Section 4.5 "WebArena Verified Hard: A Representative Subset" in the [WebArena Verified paper](https://arxiv.org/abs/XXXX.XXXXX).
