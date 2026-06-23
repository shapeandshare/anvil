---
title: 004 Frontend Refactor - data-model
type: data-model
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/004 Frontend Refactor/
related:
  - '[[004 Frontend Refactor]]'
created: ~
updated: ~
---
# Data Model: Systemic Frontend Refactor

## Entity-Relationship Map

```
AppShell (1) ──contains──> Page (1..*)
Page ──is one of──> Archetype {ConceptPage, LiveTraining, RunHistory, Playground}

ConceptPage (1) ──composes──> ScrollScene (1)
ScrollScene (1) ──has──> Step (1..*)
ScrollScene (1) ──drives──> PinnedVisual (1)

LiveTraining (1) ──manages──> SSESession (1)
SSESession (1) ──has state──> ConnectionState {idle, connecting, streaming, done, errored, reconnecting}
LiveTraining (1) ──renders──> LossChart (1)
LossChart (1) ──contains──> DataPoint (0..N) [throttled, downsampled for display]

RunHistory (1) ──lists──> TrainingRun (0..N)
TrainingRun (1) ──has──> RunMetrics (1)
RunMetrics ──replays via──> LossChart (1) [same component, replay mode]

ConceptWidget (1) ──embedded in──> ScrollScene.Step (0..1)

LearningArc (1) ──orders──> ConceptPage (7)
```

## Entities

### AppShell

| Field | Type | Description |
|-------|------|-------------|
| navItems | NavItem[] | Learning arc order + auxiliary page links |
| activeRoute | string | Current page route, highlights nav |
| theme | "dark" | "light" | "os" | Current theme mode; "os" follows system preference |
| pageFrame | Element | Content area container; all archetypes render here |
| clientStore | Store | Cross-page state boundary (URL params + sessionStorage) |

**Relationships**: 1 AppShell → N Pages (all routes)

### Archetype (enum)

| Value | Page Type | Routes |
|-------|-----------|--------|
| concept | Concept / explainer (ScrollScene) | Tokenization, Embeddings, Attention, Forward Pass, Sampling, Training Loop, Payoff |
| liveTraining | Live training dashboard (SSE) | `/v1/training-page`, `/v1/` |
| runHistory | Experiment list + detail | `/v1/experiments-page`, runs detail |
| playground | Sandbox / widget composition | `/v1/inference-page` (mapped) |

### ScrollScene

| Field | Type | Description |
|-------|------|-------------|
| pinnedVisual | HTMLElement | Sticky pane holding visualization state |
| steps | Step[] | Ordered narrative steps (1..*) |
| activeStep | string | Currently active step key (from IntersectionObserver) |

**Behavior**: IntersectionObserver watches each Step. On viewport entry, sets `activeStep`. PinnedVisual re-renders based on `activeStep`.

### Step

| Field | Type | Description |
|-------|------|-------------|
| key | string | Unique identifier for this step |
| narrative | string | Prose/markdown content for the narrative column |
| widget | ConceptWidget | Optional interactive widget embedded in this step |
| onActivate | (key) => void | Called when step enters viewport; drives pinnedVisual state |

### ConnectionState (state machine)

```
idle ──> connecting ──> streaming ──> done
                      ──> errored
streaming ──> errored ──> reconnecting ──> streaming (retry loop)
                                          ──> errored (after 5 retries)
```

| State | Visual Treatment | Description |
|-------|-----------------|-------------|
| idle | Dim/inactive | No training run active — "Start Training" available |
| connecting | --accent pulse | EventSource being established |
| streaming | --accent (live green) | Active data flow — chart ticking, metrics updating |
| done | Muted success | Training completed — final metrics displayed |
| errored | --accent-error | Connection failed — manual "Retry" button shown |
| reconnecting | --accent-warn (amber) | Connection lost, backing off: 1s → 2s → 4s → 8s → 16s |

**Transitions**:
- `idle → connecting`: User clicks "Start Training", backend starts, EventSource opens
- `connecting → streaming`: EventSource `open` event fires
- `streaming → done`: Backend emits `complete` event
- `streaming → errored`: Backend emits `error` event, or EventSource `error` after retry exhaustion
- `streaming → reconnecting`: EventSource `error` with retry available (< 5 attempts)
- `reconnecting → streaming`: Successfully reconnected, next `metrics` event received
- `reconnecting → errored`: 5th retry failed

### TrainingRun

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| id | number | Backend API | Unique run identifier |
| hyperparameters | {n_embd, n_layer, n_head, num_steps, lr, temp} | Backend API | Model configuration |
| status | "running" | "completed" | "failed" | Backend API | Current run status |
| metrics | DataPoint[] | SSE stream + store | Time-series loss data points |
| finalLoss | number | null | SSE `complete` event | Final loss value on completion |
| samplesSeen | number | null | SSE `complete` event | Total samples processed |
| duration | number | null | SSE `complete` event | Wall-clock training time (seconds) |
| createdAt | timestamp | Backend API | When training started |

**URL encoding**: `?run_id=42&temp=0.8&n_embd=64` — all params restore on direct load.

### DataPoint

| Field | Type | Description |
|-------|------|-------------|
| step | number | Training step (iteration) |
| loss | number | Loss value at this step |
| throughput | number | null | Steps/second (calculated client-side from time delta) |

**Rendering constraints**:
- Append-only: new points added to end, never modified
- Throttled: rendered at rAF or 50ms fixed interval (not per-SSE-event)
- Downsampled: past `MAX_VISIBLE_POINTS` (e.g., 2000), use Largest Triangle Three Bucket (LTTB) or simple interval sampling
- Full data retained in `metrics[]` array; only rendered series is bounded

### DesignToken

| Category | Tokens | Description |
|----------|--------|-------------|
| Color | `--bg`, `--surface`, `--text`, `--text-muted`, `--border`, `--accent`, `--accent-warn`, `--accent-error` | Semantic color tokens, dual-mode (dark/light) |
| Type | `--font-display`, `--font-body`, `--font-mono` | Typeface tokens |
| Spacing | `--space-1` through `--space-12` | Modular spacing scale |
| Motion | `--ease`, `--dur-fast`, `--dur-slow` | Transition timing tokens |
| Radius | `--radius` | Border radius (retain existing) |
| Border | `--border-width` | Border thickness |

**Mode switching**: Values defined in `:root` (dark by default), `[data-theme="light"]` (light override), `@media (prefers-color-scheme: dark)` (OS-follow default).

### LearningArc

| Position | Page | Route |
|----------|------|-------|
| 1 | Hook / hero | `/learn/intro` |
| 2 | Tokenization | `/learn/tokenization` |
| 3 | Embeddings | `/learn/embeddings` |
| 4 | Attention (centerpiece) | `/learn/attention` |
| 5 | Forward pass | `/learn/forward-pass` |
| 6 | Sampling | `/learn/sampling` |
| 7 | Training loop | `/learn/training-loop` |
| 8 | Payoff | `/learn/payoff` |

**Auxiliary pages** (outside learning arc but in navigation):
- Live Training: `/v1/training-page`
- Experiment History: `/v1/experiments-page`

### ConceptWidget (type union)

| Widget Type | Input | Output | Keyboard Support |
|-------------|-------|--------|------------------|
| Tokenization | Text input | Token/ID split display | Tab → input, type → live split |
| Embedding | Projection control | 2D/3D projection with hover | Arrow keys to rotate |
| Attention | Heatmap interactions | Highlighted attention patterns | Tab through tokens, Enter to select |
| Sampling | Temperature/top-k sliders | Re-rolled probability distribution | Arrow keys on sliders |
| TrainingLoop | Step scrubber | Animated weight nudges | Left/right arrow on scrubber |

## State Transitions (Cross-Page)

### Navigation Flow
```
User opens URL → AppShell reads URLSearchParams
  → Restores theme from localStorage
  → Restores run_id / config from URL params
  → Renders archetype for route
  → User scrolls/interacts → ephemeral UI state → sessionStorage
  → User changes config → URLSearchParams updated (shareable)
  → User navigates → AppShell preserves store, clears sessionStorage for new page
```

### Data Flow (Live Training)
```
User clicks "Start Training"
  → POST /v1/training/start {hyperparams}
  → Response: {run_id: 42}
  → new EventSource('/v1/training/stream/42')
  → State: idle → connecting
  → Event: open → State: connecting → streaming
  → Event: metrics {step, loss}
    → Append DataPoint to metrics[]
    → Throttle: if lastPaint > 50ms ago, paint LossChart
  → Event: complete {final_loss, samples, duration}
    → State: streaming → done
    → Store final metrics
    → eventSource.close()
  → Error: EventSource error
    → If retries < 5: State: streaming → reconnecting
      → setTimeout(reconnect, backoff[retryCount])
    → Else: State: reconnecting → errored
      → Show manual "Retry" button
```