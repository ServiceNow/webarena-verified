# Network Event-Based Evaluation

WebArena-Verified evaluates web agents by analyzing network events extracted from HTTP Archive (HAR) format traces captured during task execution. This approach validates agent behavior at the network level—examining navigation URLs, HTTP Referer headers, and status codes—rather than relying on fragile DOM-based assertions. By focusing on the actual HTTP interactions that occur when agents browse the web, WebArena-Verified provides stable, maintainable evaluation that is resilient to UI changes.

## What are HAR Files?

HAR (HTTP Archive) is a JSON-based format that logs all HTTP requests and responses made by a web browser during a session. HAR files capture:

- Request URLs and HTTP methods (GET, POST, etc.)
- Request and response headers (including HTTP Referer headers and content types)
- HTTP status codes (200 OK, 404 Not Found, etc.)
- Response bodies and timing information
- Network redirects and navigation events

In WebArena-Verified, we extract network traces from browser automation tools (like Playwright) and convert them to a structured format for validation.

## Comparison of Evaluation Methods

WebArena-Verified uses network trace validation instead of traditional DOM-based approaches. This shift provides significant advantages in stability and maintainability.

### Previous Method: DOM-Based Evaluation

Traditional web agent evaluation relied on DOM interaction through browser automation:

- Using CSS or XPath selectors to find HTML elements
- Verifying agent actions by checking element properties and visibility
- Monitoring DOM changes to confirm user interactions

**Issues with the DOM-Based Approach:**

- **Fragility**: Tests break when page layout or element attributes change
- **High Maintenance**: Requires frequent selector updates as UIs evolve
- **Limited Scope**: Focuses on rendered DOM rather than actual network interactions
- **Tool Lock-in**: Tightly coupled to specific automation frameworks

### Current Method: Network Trace Validation

WebArena-Verified validates agent behavior by analyzing network traces captured during task execution. The system:

- Extracts navigation events from browser network logs
- Validates URLs, referers, and HTTP status codes
- Compares actual navigation patterns against expected outcomes
- Supports flexible URL matching with query parameter normalization

**Benefits of Network Trace Validation:**

- **Stability**: Resilient to UI changes since validation occurs at the network level
- **Reduced Maintenance**: No selector updates needed when UI changes
- **Framework Flexibility**: Works with any tool that exports network traces (Playwright, Puppeteer, etc.)
- **Offline Evaluation**: Previously captured traces can be re-evaluated without browser replay
- **Better Signal**: Validates the actual HTTP interactions rather than rendered appearance

## What Gets Validated

Network trace validation is powered by the `NetworkEventEvaluator`, the only evaluator included with
the open-source build for inspecting traces. It normalizes captured events and asserts that the agent
triggered the right HTTP traffic.

### 1. Navigation Requests

You can ensure the agent reached a specific page by checking the final navigation event:

```json
{
  "evaluator": "NetworkEventEvaluator",
  "last_event_only": true,
  "expected": {
    "url": "__SHOPPING__/products/123",
    "response_status": 200
  }
}
```

### 2. Query Parameters and POST Data

The evaluator can assert normalized query strings or form bodies. Use `ignored_query_params` to drop
volatile keys, and the optional schema helpers for type-aware comparisons:

```json
{
  "evaluator": "NetworkEventEvaluator",
  "ignored_query_params": ["session_id", "timestamp"],
  "query_params_schema": {
    "type": "object",
    "properties": {
      "from": {"type": "string", "format": "date"},
      "to": {"type": "string", "format": "date"}
    }
  },
  "expected": {
    "url": "__SHOPPING__/reports/sales",
    "query_params": {
      "from": ["02/01/2023"],
      "to": ["02/28/2023"]
    }
  }
}
```

### 3. Headers and Referers

Because HAR captures request headers, the evaluator can confirm a navigation originated from the
right page:

```json
{
  "evaluator": "NetworkEventEvaluator",
  "expected": {
    "url": "__SHOPPING__/checkout",
    "headers": {
      "referer": "__SHOPPING__/cart"
    }
  }
}
```

### 4. Event Types and Sequencing

Set `event_type` to `"navigation"` to focus on page loads, or to `"modification"` for form
submissions. The `last_event_only` flag instructs the evaluator to match the most recent event;
disabling it means "any matching event is sufficient".

## Network Trace Structure

Network traces contain structured navigation events extracted from HAR-format logs:

```python
class NetworkEvent:
    url: str                  # Request URL
    referer: str | None       # Referer header value
    http_method: str          # GET, POST, etc.
    request_status: int       # HTTP status code (200, 404, etc.)
    is_document_event: bool   # True for document navigations
    event_type: NetworkEventType  # NAVIGATION, MUTATION, or OTHER

class NetworkTrace:
    events: tuple[NetworkEvent, ...]
    navigation_events: tuple[NetworkEvent, ...]  # Filtered navigation events only
```

Navigation events are identified by request headers:

- `sec-fetch-dest: document`
- `sec-fetch-mode: navigate`
- HTTP method: GET (navigations) or POST/PUT/DELETE/PATCH (mutations)

## Example: Navigation Validation

Here's a complete example showing how validation works:

**Task:** Agent should navigate to the product detail page for item 123

**Captured navigation events:**

```python
[
    NetworkEvent(url="http://shop.test/home", http_method="GET", request_status=200),
    NetworkEvent(url="http://shop.test/search?q=item", http_method="GET", request_status=200),
    NetworkEvent(url="http://shop.test/products/123", http_method="GET", request_status=200)
]
```

**Evaluation config:**

```json
{
  "evaluator": "NetworkEventEvaluator",
  "last_event_only": true,
  "expected": {
    "url": "http://shop.test/products/123",
    "response_status": 200,
    "headers": {
      "referer": "http://shop.test/search"
    }
  }
}
```

**Result:** PASS – The last navigation event matches the expected URL and referer with status 200

## Limitations

While network trace validation provides significant advantages, it has some constraints:

### What Network Traces Cannot Validate

1. **Visual UI State**: Cannot verify rendered appearance, colors, fonts, or layout
2. **DOM Content**: Cannot check if specific text appears on the page
3. **JavaScript State**: Cannot inspect client-side application state
4. **Dynamic Content**: Cannot verify content loaded after initial page render
5. **User Experience**: Cannot validate animations, transitions, or interactivity

### When to Use Additional Evaluators

For comprehensive validation, pair network trace validation with:

- **AgentResponseEvaluator**: Ensures the agent returns the expected structured response payload.

### Technical Constraints

- **Requires structured traces**: The system expects navigation events in a specific format, not raw HAR JSON
- **Capture required**: Initial task execution requires a live browser to capture network traces
- **Tool integration**: While HAR is standard, extracting navigation events requires integration with browser automation tools
