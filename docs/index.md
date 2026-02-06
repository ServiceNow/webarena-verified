# Welcome to WebArena-Verified

WebArena-Verified is the reproducible release of the WebArena benchmark: the original containerized sites remain intact, but every task, reference answer, and evaluator has been re-audited to eliminate brittle string matching and ambiguous success criteria. Deterministic, JSON-based scoring and network events-based checks let you measure web agents offline.

**Key Contributions:**

- **Fully audited benchmark**: Every task, reference answer, and evaluator has been manually reviewed and corrected
- **Offline evaluation**: Evaluate agent runs without requiring live web environments using network trace replay
- **Deterministic scoring**: Removed LLM-as-a-judge evaluation and substring matching in favor of type-aware normalization and structural comparison
- **[WebArena-Verified Hard subset](getting_started/hard_subset.md)**: A difficulty-prioritized 258-task subset for cost-effective evaluation

The following quick start demonstrates these capabilities in practice. You'll bring the toolkit up, validate a single task end-to-end, and then branch into batch evaluation or custom integrations when you're ready.


This quick start is divided into two parts:

- **Part 1** (~5 minutes): Understand evaluation by evaluating a pre-run agent log
- **Part 2** (~10 minutes): Run an agent and evaluate it

---

## Setup

Clone the repository and install dependencies:

=== "uvx"

    **Prerequisites:** [uv](https://docs.astral.sh/uv/getting-started/installation/)

    !!! info "What is uvx?"
        `uvx` runs Python CLI tools in isolated, ephemeral environments without installation. It doesn't pollute your environment and automatically handles dependencies and cleanup.

    ```bash
    git clone https://github.com/ServiceNow/webarena-verified.git
    cd webarena-verified
    ```

    Verify the CLI is working:

    ```bash
    uvx webarena-verified --help
    ```

=== "Docker"

    **Prerequisites:** Docker

    ```bash
    git clone https://github.com/ServiceNow/webarena-verified.git
    cd webarena-verified
    docker pull ghcr.io/servicenow/webarena-verified:latest
    ```

    Verify the CLI is working:

    ```bash
    docker run --rm ghcr.io/servicenow/webarena-verified:latest --help
    ```

=== "uv"

    **Prerequisites:** Python 3.11+

    ```bash
    git clone https://github.com/ServiceNow/webarena-verified.git
    cd webarena-verified
    uv venv
    source .venv/bin/activate
    uv pip install "webarena-verified[examples]"
    ```

    Verify the CLI is working:

    ```bash
    webarena-verified --help
    ```

=== "pip"

    **Prerequisites:** Python 3.11+

    ```bash
    git clone https://github.com/ServiceNow/webarena-verified.git
    cd webarena-verified
    python -m venv .venv
    source .venv/bin/activate
    pip install "webarena-verified[examples]"
    ```

    Verify the CLI is working:

    ```bash
    webarena-verified --help
    ```

!!! note "Why clone the repository?"
    This tutorial uses example files (pre-run agent logs, configs, and the human agent) from the `examples/` directory. If you're evaluating your own agents, you can simply `pip install webarena-verified` or use the Docker image which contains the self-contained evaluator - see the [Usage Guide](getting_started/usage.md).


---

## Part 1: Evaluate a Pre-Run Task

Before running an agent, let's evaluate an existing agent log to understand how WebArena-Verified works. We'll use the following task that already has output in `examples/agent_logs/demo/108/`:

```json
{
  "task_id": 108,
  "intent": "Get the monthly count of successful orders 01/2023-05/2023",
  "sites": ["shopping_admin"]
  ...
}
```

!!! tip "New in WebArena-Verified: **Offline Evaluation**."

    **Why This Matters:**

    - Evaluate agent runs without live web environments
    - Reevaluate past runs at any time
    - Compare different agents transparently with reproducible benchmarking

### 1. What's in a Task Log?

The task log contains two key artifacts:

```
examples/agent_logs/demo/108/
├── agent_response.json
└── network.har
```

#### Agent Response

Agents are required to return a valid JSON like the following:

```json
--8<-- "examples/agent_logs/demo/108/agent_response.json"
```

??? info "Field Descriptions"
    - **`task_type`** (required): Type of work performed - `RETRIEVE`, `MUTATE`, or `NAVIGATE`
    - **`status`** (required): Task outcome - `SUCCESS` or error codes (`NOT_FOUND_ERROR`, `PERMISSION_DENIED_ERROR`, `DATA_VALIDATION_ERROR`, etc.)
    - **`retrieved_data`**: Array of items for `RETRIEVE` operations (otherwise null)
    - **`error_details`**: Null for `SUCCESS`, otherwise explains what failed and why

!!! tip "New in WebArena-Verified: **Structured Agent Response**"
    **Why This Matters:**

    - **Robust Evaluation**: Modern LLMs rarely struggle with generating valid JSON, enabling more reliable evaluation with explicit fields:
        - **`task_type`**: Requires agents to explicitly state what operation they performed, revealing whether they truly understood the task
        - **`status`**: Allows various error status codes instead of catch-all "N/A" responses for unachievable tasks
        - **`retrieved_data`**: Structured format reduces false negatives due to parsing issues
    - **Reduces False Positives**: By validating both the operation type and the outcome, we ensure agents actually completed the intended task.

        !!! example "Example: Navigation vs. Retrieval"
            For a task that requires retrieving data, the agent misunderstands and only navigates. The agent can reach the correct page but never retrieve the data.

            - **Original WebArena**: Pass ✓ (only checked if agent reached the correct page)
            - **WebArena-Verified**: Fail ✗ (verifies page navigation *and* `task_type` matches `RETRIEVE`)

            *(Or picture asking a coding agent to "review this code" and watching it start rewriting everything while you frantically mash Ctrl+C! 😱)*

#### Network Trace

Captures all network activity between the browser frontend and the backend in [HAR (HTTP Archive)](https://en.wikipedia.org/wiki/HAR_(file_format)) format - a standard format widely used for debugging and analyzing web traffic. This records what the agent actually did - including page navigations, data retrievals, and modifications. Each network event includes the URL, HTTP method, and response status used by the evaluator:

```json
{
  "request": {
    "method": "GET",
    "url": "http://192.168.1.35:7780/admin/customer/index/",
    ...
  },
  "response": {
    "status": 200,
    ...
  },
  ...
}
```

!!! tip "New in WebArena-Verified: **Network Event Based Evaluation**"
    **Why This Matters:**

    - **Enables Offline Evaluation**: Network traces can be evaluated without live web environments - this is the critical piece that makes reevaluation possible
    - **Avoids Brittle Locators**: No reliance on DOM selectors or page structure - allows for easy website updates
    - **Single Evaluation Method**: Works uniformly across all websites (GitLab, e-commerce, forums, etc.)

    See [Network Event Based Evaluation](evaluation/network_event_based_evaluation.md) for details.

### 2. Run the evaluator

=== "uvx"

    ```bash
    uvx webarena-verified eval-tasks \
      --task-ids 108 \
      --output-dir examples/agent_logs/demo \
      --config examples/configs/config.demo.json
    ```

=== "Docker"

    ```bash
    docker run --rm \
      -v ./examples:/examples \
      ghcr.io/servicenow/webarena-verified:latest \
      eval-tasks \
        --task-ids 108 \
        --output-dir /examples/agent_logs/demo \
        --config /examples/configs/config.demo.json
    ```

=== "CLI"

    ```bash
    webarena-verified eval-tasks \
      --task-ids 108 \
      --output-dir examples/agent_logs/demo \
      --config examples/configs/config.demo.json
    ```

??? tip "Troubleshooting"
    - If the `webarena-verified` command is not available, make sure you have activated the virtual environment correctly. See the [Setup](#setup) section.

This creates an `eval_result.json` file in the task directory (`examples/agent_logs/demo/108/`).

### 3. Examine the evaluation result

The evaluation result is a structured JSON document that shows:

- **The overall task status and score** - Did the agent pass or fail?
- **Individual evaluator results** - Each evaluator (e.g., AgentResponseEvaluator) reports its findings
- **Raw and normalized values** - We show both `actual` (raw agent output) and `actual_normalized` (after type-aware normalization) to help you catch normalization issues and understand how values are being compared
- **Reproducibility checksums** - We track evaluation code and task dataset checksums to ensure consistent, reproducible evaluations across different runs and environments

The annotated JSON below explains each field. Click the + markers to expand explanations:

``` json
--8<-- "docs/assets/task_108_annotated_results.json"
```


1. Task revision number - incremented when task definition changes
2. Overall evaluation status - `success` when all evaluators pass
3. Overall score - 1.0 = complete success, 0.0 = failure
4. Results from each evaluator that ran on this task
5. Name of the evaluator - `AgentResponseEvaluator` validates structured agent responses
6. Raw agent response before normalization - note mixed month formats ("Jan", "Feb", "March")
7. Agent response after type-aware normalization - all months converted to lowercase ("january", "february", "march"). Notice how `actual_normalized` matches `expected` even though raw formats were mixed.
8. Expected values from task definition - what the agent should return after normalization
9. List of assertion failures - `null` means all checks passed
10. Error message when the evaluation system itself encounters an error (not agent failures). When `error_msg` is not null, `status` is `ERROR`.
11. WebArena-Verified version used for this evaluation
12. Checksum of evaluator code - ensures evaluation logic hasn't changed
13. Checksum of task dataset - ensures task definitions are consistent

!!! tip "New in WebArena-Verified: **Type-Aware Normalization**"
    **Why This Matters:**

    - **Handles Common Data Types**: Automatically normalizes dates, currency, URLs, coordinates, and more without requiring LLM-based evaluation
    - **Format-Agnostic Comparison**: In this example, month names are normalized regardless of format ("Jan" vs "January" vs "january"), ensuring reliable comparison
    - **Deterministic & Cost-Effective**: Eliminates the unpredictability and cost of LLM evaluators

---

## Part 2: Run and Evaluate an Agent

Now that you understand evaluation, let's run an agent and evaluate it. We'll complete the following task:

```json
{
  "task_id": 44,
  "intent": "Open my todos page",
  "sites": ["gitlab"]
  ...
}
```

We'll use a special "human agent" that opens a browser and hands control to you to complete this simple navigation task (requires clicking on a single menu item).

!!! info "Why not use a real AI agent implementation?"
    The goal of this exercise is to walk through how to use the benchmark in a straightforward way, without additional complexity. By stepping through the process manually, you'll understand exactly what agents need to produce and how evaluation works.

### 0. Install Playwright

The example agents use Playwright for browser automation. Install the Chromium browser:

=== "uvx"

    !!! note "Playwright runs locally"
        `uvx` is used for evaluation only. To run the human agent example, you need Playwright installed locally.

    ```bash
    uv venv
    source .venv/bin/activate
    uv pip install "webarena-verified[examples]"
    playwright install chromium
    ```

=== "Docker"

    !!! note "Playwright runs locally"
        The Docker image is used for evaluation only. To run the human agent example, you need Playwright installed locally.

    ```bash
    uv venv
    source .venv/bin/activate
    uv pip install "webarena-verified[examples]"
    playwright install chromium
    ```

=== "uv / pip"

    ```bash
    playwright install chromium
    ```

### 1. Setup GitLab Environment

First, you need a GitLab instance to work with. Choose one option:

=== "Demo GitLab"

    ??? info "What is the Demo GitLab?"
        This is a lightweight, bare-bones GitLab Docker image instead of the full 100 GB+ GitLab instance from the original WebArena. For simple navigation tasks like "Check out my todos", this smaller image is perfectly sufficient and much faster to download and run on your laptop! However, this task is not part of our hard subset since it only requires basic navigation.

    Start the demo GitLab instance using Docker:

    ```bash
    uv run invoke -r examples demo-gitlab-start
    ```

    !!! info "The GitLab instance takes 2-3 minutes to fully boot up. Wait until the command completes and shows the container status as 'running' before proceeding."

    !!! info "Change the default port (8012)"
        To use a different port, add the `--port` flag:
        ```bash
        uv run invoke -r examples demo-gitlab-start --port=8080
        ```
        Then update `examples/configs/config.demo.json` to match your port.

    We'll use `examples/configs/config.demo.json`
    
    ``` json
    --8<-- "examples/configs/config.demo.json"
    ```


=== "Bring Your Own"

    If you have your own GitLab instance running (from the original webarena setup), update `examples/configs/config.demo.json` with your GitLab URL and credentials:

    ```json
    {
      "environments": {
        "__GITLAB__": {
          "urls": ["http://your-gitlab-url[:port]"],
          "credentials": {
            "username": "your-username",
            "password": "your-password"
          }
        }
      }
    }
    ```

### 2. Export Task Data

Export the task information that the agent needs:

=== "uvx"

    ```bash
    uvx webarena-verified agent-input-get \
      --task-ids 44 \
      --config examples/configs/config.demo.json \
      --output output/tasks.demo.json
    ```

=== "Docker"

    ```bash
    docker run --rm \
      -v ./examples:/examples \
      -v ./output:/output \
      ghcr.io/servicenow/webarena-verified:latest \
      agent-input-get \
        --task-ids 44 \
        --config /examples/configs/config.demo.json \
        --output /output/tasks.demo.json
    ```

=== "CLI"

    ```bash
    webarena-verified agent-input-get \
      --task-ids 44 \
      --config examples/configs/config.demo.json \
      --output output/tasks.demo.json
    ```

This exports only the fields that the agent needs to perform the task (`intent`, `start_urls`) and the IDs (`task_id`, `intent_template_id`, and `sites`). Since the `--config` argument is provided, URL templates like `__GITLAB__` are rendered to actual URLs (e.g., `http://localhost:8012`).

!!! tip "New in WebArena-Verified: **Agent runner does not depend on benchmark dependencies**"
    **Why This Matters:**

    - **Language & Framework Freedom**: Your agent implementation can use any programming language (Python, JavaScript, Go, etc.) or framework - no dependency on the benchmark's libraries
    - **Independent Versioning**: Use any version of Playwright, Selenium, or other browser automation tools without conflicts with the benchmark
    - **Lightweight Integration**: Agents only need to read JSON task files and produce standard output formats (JSON response + HAR trace)
    - **Alternative Approach**: While we use `agent-input-get` CLI here to export tasks, you can also call WebArena-Verified's Python API directly within your agent code if you prefer programmatic access

### 3. Your Turn: Complete the Task

Now let's run the human agent for Task ID 44 (from `output/tasks.demo.json` we generated earlier)

```json
{
  "sites": ["gitlab"],
  "task_id": 44,
  "intent_template_id": 303,
  "start_urls": ["http://localhost:8012"],
  "intent": "Open my todos page"
}
```

```bash
uv run python examples/agents/human/agent.py \
  --tasks-file output/tasks.demo.json \
  --task_id 44 \
  --task_output_dir output/demo-run/44 \
  --config examples/configs/config.demo.json
```

**What happens next:**

1. The agent script opens a browser window and navigates to GitLab (login is handled automatically)
2. **Now it's your turn!** Navigate to the todos page by clicking "To-Do List" in the left sidebar, then close the browser window
3. The agent will prompt you in the **terminal** to generate the agent response saved to `agent_response.json`
4. The agent writes its response and network event logs to `output/demo-run/44/agent_response.json` and `output/demo-run/44/network.har`

??? example "Example: Agent Response Questionnaire Output"
    ```
    ==============================================================
    Browser closed. Generating the agent response questionnaire...
    ==============================================================

    ------------------------------------------------------------
    Select the performed operation:

    1. RETRIEVE
    2. MUTATE
    3. NAVIGATE

    Enter choice number > 3

    ------------------------------------------------------------
    Select the task status:

    1. SUCCESS
    2. ACTION_NOT_ALLOWED_ERROR
    3. PERMISSION_DENIED_ERROR
    4. NOT_FOUND_ERROR
    5. DATA_VALIDATION_ERROR
    6. UNKNOWN_ERROR

    Enter choice number > 1


    ------------------------------------------------------------
    Proposed agent response:
    {
      "task_type": "NAVIGATE",
      "status": "SUCCESS",
      "retrieved_data": null,
      "error_details": null
    }
    ------------------------------------------------------------
    Confirm and save this response?
      1. Yes
      2. No
    > 1
    ```

### 4. Evaluate Your Run

Now let's evaluate your performance:

=== "uvx"

    ```bash
    uvx webarena-verified eval-tasks \
      --config examples/configs/config.demo.json \
      --task-ids 44 \
      --output-dir output/demo-run
    ```

=== "Docker"

    ```bash
    docker run --rm \
      -v ./examples:/examples \
      -v ./output:/output \
      ghcr.io/servicenow/webarena-verified:latest \
      eval-tasks \
        --config /examples/configs/config.demo.json \
        --task-ids 44 \
        --output-dir /output/demo-run
    ```

=== "CLI"

    ```bash
    webarena-verified eval-tasks \
      --config examples/configs/config.demo.json \
      --task-ids 44 \
      --output-dir output/demo-run
    ```

This creates `output/demo-run/44/eval_result.json` with your evaluation results.

### 5. Review the Results

Check `output/demo-run/44/eval_result.json` - it will have the same structure as Part 1.

**What got evaluated:**

- **AgentResponseEvaluator**: Validated your response structure (`task_type`, `status`, etc.)
- **NetworkEventEvaluator**: Checked that you navigated to the correct URL (`/dashboard/todos`)

If you successfully navigated to the todos page and reported `task_type: "NAVIGATE"` with `status: "SUCCESS"`, you should see:

```json
{
  "status": "success",
  "score": 1.0,
  "evaluators_results": [
    {
      "evaluator_name": "AgentResponseEvaluator",
      "status": "success",
      "score": 1.0,
      ...
    },
    {
      "evaluator_name": "NetworkEventEvaluator",
      "status": "success",
      "score": 1.0,
      ...
    }
  ],
  ...
}
```

If you used the demo GitLab instance, you can now stop it:

```bash
uv run invoke -r examples demo-gitlab-stop
```

---

## Where to Next?

- **[Usage Guide](getting_started/usage.md)** - Agent workflow, batch evaluation, CLI filters, programmatic APIs
- **[Configuration Reference](getting_started/configuration.md)** - All config options
- **[Evaluation Guide](evaluation/index.md)** - Deep dive into evaluators and scoring
- **[API Reference](api_reference/index.md)** - Type models and classes

Happy benchmarking!
