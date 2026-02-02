# Utilities

WebArena-Verified provides several utility commands for managing and optimizing benchmark data.

## Trimming Network Logs

Network log files (HAR format) can become large due to static resources like CSS, JavaScript, images, and fonts. Since these resources are not evaluated (only HTML pages, API requests, and form submissions matter), you can significantly reduce file sizes by removing them.

The `trim-network-logs` command removes entries for skipped resource types while preserving all evaluation-relevant events:

=== "uvx"

    ```bash
    uvx webarena-verified trim-network-logs \
      --input logs/task_123.har \
      --output logs/task_123_trimmed.har
    ```

=== "Docker"

    ```bash
    docker run --rm \
      -v ./logs:/logs \
      am1n3e/webarena-verified:latest \
      trim-network-logs \
        --input /logs/task_123.har \
        --output /logs/task_123_trimmed.har
    ```

=== "CLI"

    ```bash
    webarena-verified trim-network-logs \
      --input logs/task_123.har \
      --output logs/task_123_trimmed.har
    ```

### What Gets Removed

The utility uses the same logic as `NetworkEvent.is_evaluation_event` to identify static resources:

- CSS files (`.css`)
- JavaScript files (`.js`)
- Images (`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`, `.ico`)
- Fonts (`.woff`, `.woff2`, `.ttf`, `.eot`)

### What Gets Kept

All evaluation-relevant network events are preserved:

- HTML pages
- API endpoints
- Form submissions
- All other navigation and data requests

### Benefits

- **76-90% file size reduction** on typical logs
- **Evaluation results unchanged** - trimmed files produce identical scores
- **Faster processing** - smaller files load and parse more quickly
- **Reduced storage costs** - especially important for large-scale evaluations

!!! example "Example Size Reduction"
    ```bash
    # Original HAR file: 786 KB with 359 entries
    # Trimmed HAR file: 184 KB with 50 entries (76.6% reduction)
    ```

### Batch Trimming

You can trim multiple files in a loop:

=== "uvx"

    ```bash
    for task_dir in output/*/; do
      task_id=$(basename "$task_dir")
      uvx webarena-verified trim-network-logs \
        --input "$task_dir/network.har" \
        --output "$task_dir/network_trimmed.har"
    done
    ```

=== "Docker"

    ```bash
    for task_dir in output/*/; do
      task_id=$(basename "$task_dir")
      docker run --rm \
        -v ./"$task_dir":/data \
        am1n3e/webarena-verified:latest \
        trim-network-logs \
          --input /data/network.har \
          --output /data/network_trimmed.har
    done
    ```

=== "CLI"

    ```bash
    for task_dir in output/*/; do
      task_id=$(basename "$task_dir")
      webarena-verified trim-network-logs \
        --input "$task_dir/network.har" \
        --output "$task_dir/network_trimmed.har"
    done
    ```

### Technical Details

The trimming utility:

1. Loads the HAR file and converts entries to `NetworkEvent` objects
2. Uses `NetworkEvent.is_evaluation_event` to identify evaluation-relevant events
3. Filters out static resources while preserving evaluation events
4. Writes the trimmed HAR file with the same structure

This ensures consistency with the evaluation logic and guarantees that trimmed logs produce identical evaluation results.
