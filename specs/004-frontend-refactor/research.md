# Research: Systemic Frontend Refactor

**Phase 0 research output** — Technology decisions, architecture rationale, and alternatives considered.

---

## 1. CSS Architecture: Monolithic → Modular Design Tokens

- **Decision**: Split single `style.css` (1276 lines) into modular CSS files with a centralized design token file. The existing CSS custom property system (`:root` + `[data-theme="light"]`) is the right foundation — extend it with missing token categories (spacing, type, motion) rather than replacing it.
- **Rationale**: The spec requires "a systemic restyle must be a token edit" (SC-008). The existing `:root` token system already supports this pattern. Extending it with `--space-*`, `--font-*`, `--dur-*` tokens and splitting into logical files makes the system manageable.
- **Alternatives considered**:
  - Tailwind CSS — rejected (dependency-lean ethos, Principle 4)
  - CSS-in-JS — rejected (no build step, all-static ethos)
  - Keeping monolithic file — rejected (maintainability, violates SC-008)

## 2. Chart Rendering: ASCII Art → Canvas API

- **Decision**: Canvas 2D API for the live loss chart. Canvas is the best fit for append-only, high-frequency updates with downsampling.
- **Rationale**: The spec mandates "charts render via `<canvas>` or bounded SVG, not a heavyweight charting dependency" (Principle 4). Canvas excels at pixel-level rendering of dense time-series data without DOM overhead. Native Canvas API has zero dependencies.
- **Alternatives considered**:
  - SVG — viable but slower for >10k data points with frequent repaints; every point is a DOM node
  - Chart.js — rejected (dependency, violates Principle 4)
  - D3.js — rejected (dependency, overkill for a single loss curve)
  - Existing ASCII art (`█░` block chars in `<pre>`) — rejected (not a real chart, no interaction)

## 3. SSE Lifecycle: Native EventSource + Custom Manager

- **Decision**: Wrap native `EventSource` in a custom SSE connection manager (`sse.js`) that tracks the 6-state lifecycle (idle → connecting → streaming → done → errored → reconnecting) with capped exponential backoff (5 retries: 1s, 2s, 4s, 8s, 16s).
- **Rationale**: The existing training page already uses native EventSource successfully. No need for a library — the custom manager handles the state machine, reconnect, and cleanup that the current code lacks.
- **Alternatives considered**:
  - Fetch-based polling — rejected (SSE is more efficient for streaming, already in place)
  - WebSocket — rejected (overkill for unidirectional metrics stream, requires different backend)
  - `eventsource` polyfill npm package — rejected (no IE support needed, modern browsers only)

## 4. SSE Data Format (from existing backend)

Current SSE backend (`microgpt/api/v1/training.py`) emits:

```
event: metrics
data: {"step": 0, "loss": 4.2314, "throughput": "12.3 steps/s"}

event: complete
data: {"final_loss": 0.0423, "samples_seen": 10000, "duration": 120.5}

event: error
data: {"message": "Training failed: ..."}
```

Throughput calculation must happen client-side (step deltas / wall clock) or be added to backend metrics payload. The existing frontend only receives step + loss — throughput display needs either backend changes or client-side computation.

## 5. Scroll Scene: IntersectionObserver + Render-Prop Pattern

- **Decision**: Single `useActiveStep` mechanism built on `IntersectionObserver`. Steps emit a state key on viewport entry. The pinned visual re-renders based on the active state key. No scroll-offset math.
- **Rationale**: IntersectionObserver is the platform-native, performant way to detect element visibility. It avoids scroll-handler jank, is throttle-free by design, and automatically handles cleanup. The render-prop pattern keeps ScrollScene reusable across all concept pages.
- **Alternatives considered**:
  - Scroll event listener with offset math — rejected (jank, per-section coupling, violates FR-006)
  - `scrollama` library — rejected (dependency, overkill for this use case)

## 6. Theme System: CSS Custom Properties + `data-theme` Attribute

- **Decision**: Keep the existing `data-theme="dark|light"` mechanism with `localStorage` persistence. Extend it with:
  - `@media (prefers-color-scheme: dark)` default (existing code lacks OS detection)
  - New semantic tokens: `--bg`, `--surface`, `--text`, `--text-muted`, `--border`, `--accent`, `--accent-warn`, `--accent-error`
  - New type tokens: `--font-display`, `--font-body`, `--font-mono`
  - New spacing tokens: `--space-1` through `--space-12` modular scale
  - New motion tokens: `--ease`, `--dur-fast`, `--dur-slow`
  - Remove: `--accent-cyan`, `--accent-yellow`, `--accent-magenta`, `--accent-green`, `--accent-red` (ANSI legacy)
- **Rationale**: The existing `data-theme` + `localStorage` pattern is solid and already deployed. Extending it with new semantic tokens and OS detection achieves the spec's dual-mode design while preserving backward compatibility during migration.
- **Alternatives considered**:
  - Single `:root` with `prefers-color-scheme` only — rejected (no manual toggle)
  - Separate CSS files per theme — rejected (maintainability, violates SC-008)
  - CSS color-scheme property only — insufficient for custom semantic tokens

## 7. State Management: URL Params + sessionStorage + localStorage

- **Decision**: Three-tier state management:
  - **Shareable/durable** → `URLSearchParams` (run_id, model config params, learning arc position)
  - **Ephemeral UI** → `sessionStorage` (current scroll position, accordion state, widget settings)
  - **Persistent preference** → `localStorage` (theme choice)
- **Rationale**: This matches the spec's §5 contract exactly. URL params enable shareable links ("here's my run with temp=1.2"). sessionStorage survives in-page navigation but not cross-session, which is correct for ephemeral UI. localStorage is appropriate for user preferences.
- **Alternatives considered**:
  - Single global mutable store — rejected (violates FR-020)
  - localStorage for everything — rejected (too much noise in persistent storage)
  - Server-side state (DB-backed) — rejected (overkill, auth not in scope)

## 8. Computation Graph: Canvas DAG Rendering

- **Decision**: Canvas 2D API rendering of a directed acyclic graph. Node layout via a lightweight topological sort + simple layered layout algorithm (manual, not a library). Nodes show real op labels and tensor values in `--font-mono`.
- **Rationale**: The spec requires real engine data (FR-014) and supports "projection/level-of-detail" for large graphs. Canvas avoids DOM overhead for potentially hundreds of nodes. A hand-rolled layered layout is sufficient — the graph is a simple forward pass chain, not an arbitrary DAG.
- **Alternatives considered**:
  - dagre library — considered and may be justified if graph complexity grows, but deferred
  - SVG with manual layout — viable but DOM-heavy for large graphs
  - Static HTML pre-rendering — rejected (needs to be interactive/scrubbable)

## 9. JS Module Strategy: Inline IIFE → Static Files

- **Decision**: Extract all inline JS from 9 templates into separate `.js` files under `microgpt/api/static/js/`. Each file is wrapped in an IIFE (preserving the existing pattern) with explicit `window.` exports for Jinja2 `onclick` compatibility.
- **Rationale**: All JS is currently inline in `<script>` blocks with IIFE wrappers. Extracting to files improves maintainability, enables caching, and supports the modular architecture. Keeping the IIFE pattern avoids a breaking change for existing `onclick` handlers.
- **Alternatives considered**:
  - ES modules — rejected (requires `type="module"`, breaks existing inline onclick patterns)
  - Bundler (webpack/rollup) — rejected (dependency, violates Principle 4)
  - Keep all JS inline — rejected (maintainability, violates modularity goals)