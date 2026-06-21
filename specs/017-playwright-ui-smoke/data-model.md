# Data Model: Playwright UI Smoke Harness

**Phase**: 1 — Design & Contracts  
**Date**: 2026-06-21

> **Note**: This feature defines conceptual entities for organizing the smoke test suite. There is no persistent data model — all entities are ephemeral test artifacts.

---

## Entity: SmokeTest

A single automated browser session that performs a sequence of user-facing interactions and assertions.

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Unique test identifier (derived from test function name) |
| `workflow` | String | The user-facing workflow under test (e.g., "navigation", "dataset-upload") |
| `routes_covered` | String[] | Primary application routes exercised by this test |
| `pass_condition` | String | The assertion that determines pass/fail (from acceptance scenarios) |
| `timeout` | Integer (seconds) | Maximum wait time for the pass condition (30s for training, 10s for upload) |

**Validation rules**:
- Each test covers exactly one user workflow (not a composite scenario)
- Each test MUST be independently runnable (no hard dependencies on other tests)
- Timeout MUST be implemented via Playwright auto-waiting, not fixed sleep

---

## Entity: PrimaryRoute

One of the application's main page URLs that constitutes the core navigation surface.

| Field | Type | Description |
|-------|------|-------------|
| `path` | String | URL path (e.g., `/`, `/v1/training-page`) |
| `label` | String | Human-readable name (e.g., "Dashboard", "Training") |
| `landmark_selector` | String | CSS selector for a unique page-identifying element (final selectors derived at implementation time by reading the actual templates; training page confirmed to expose `#metric-step`/`#metric-loss`/`#connection-state`) |

**Complete list of primary routes**:
| Path | Label | Assertion |
|------|-------|-----------|
| `/` | Dashboard | Visible hero/dashboard component |
| `/v1/datasets-page` | Datasets | Page-specific heading or control |
| `/v1/training-page` | Training | Training form or config section |
| `/v1/experiments-page` | Experiments | Experiment list or empty state |
| `/v1/models-page` | Models | Model registry or empty state |
| `/v1/inference-page` | Inference | Model selector or prompt input |
| `/v1/operations-page` | Operations | Service health or log viewer |
| `/v1/learn` | Learn | Lesson listing or content area |

**Validation rules**:
- Every route MUST produce a 200-level HTTP status (no error page)
- Every route MUST render a unique landmark element
- Every route MUST have zero console errors on load

---

## Entity: ConsoleError

A JavaScript runtime error, unhandled promise rejection, or network-level error logged to the browser console during page load or interaction.

| Field | Type | Description |
|-------|------|-------------|
| `type` | Enum | `js_error`, `unhandled_rejection`, `network_error`, `warning` |
| `message` | String | Error message text from the console |
| `source` | String | Source URL or resource that triggered the error |
| `timestamp` | Integer | Milliseconds since page load when error occurred |

**Validation rules**:
- `js_error` and `unhandled_rejection` types are ALWAYS test failures
- `network_error` for missing assets (404s, 502s) are ALWAYS test failures
- `warning` types are captured but do not fail the test (logged for investigation)
- Console listener MUST be attached before or immediately after `page.goto()`

---

## Entity: LiveDataPoint

A single unit of real-time progress information emitted by the backend and rendered in the frontend training display during an active training run.

| Field | Type | Description |
|-------|------|-------------|
| `step` | Integer | Training step number (rendered at `#metric-step`) |
| `loss` | Float | Loss value at this step (rendered at `#metric-loss`, 4 decimals) |
| `display_element` | String | CSS selector for the DOM element showing this data (`#metric-loss`) |

**Validation rules**:
- At least one data point MUST be observed to pass the SSE wiring test
- The data point MUST be rendered in a visible DOM element (`#metric-loss` / `#metric-step` text nodes — confirmed to exist in `training.html`)
- The loss assertion MUST match a **numeric pattern** (e.g., `/\d+\.\d{4}/`), NOT merely "non-empty" — the element defaults to the `—` placeholder until the first real point arrives
- The test MUST NOT interpret the loss *magnitude* — only verify a real number is rendered
- The test MUST use Playwright auto-waiting/polling to observe the data point

---

## State Transitions

The training run lifecycle under test:

```
[Start] → [Configuring] → [Running] → [Live Data Points] → [Completed]
                              ↕
                        SSE Stream Active
```

Test assertions at each state:
| State | Assertion |
|-------|-----------|
| Configuring | Form fields are editable, Start button is enabled |
| Running | UI shows "training in progress" indicator |
| Live Data Points | At least one step/loss pair is rendered |
| Completed | UI displays terminal/completed state |