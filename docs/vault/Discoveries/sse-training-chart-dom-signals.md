---
title: "SSE Training Chart — Assertable DOM Text Signals"
type: discovery
tags:
  - type/discovery
  - domain/testing
  - domain/frontend
created: 2026-06-21
updated: 2026-06-21
aliases:
  - "SSE Training Chart — Assertable DOM Text Signals"
status: status/draft
---

# SSE Training Chart — Assertable DOM Text Signals

## Context

During the Playwright browser smoke test implementation, I needed to assert that the live SSE training chart receives data points. The concern was whether this was only rendered to a `<canvas>` (unassertable by Playwright) or exposed as DOM text nodes.

## Finding

The training page (`anvil/api/templates/archetypes/training.html`) exposes live step and loss values as **plain text DOM nodes** with stable IDs, updated on every SSE `metrics` event:

| Signal | Selector | Format |
|--------|----------|--------|
| Current step | `#metric-step` | Integer (e.g. `"42"`) |
| Current loss | `#metric-loss` | Float, 4 decimals (e.g. `"2.3456"`) |
| Throughput | `#metric-Throughput` | `"N.N st/s"` |
| SSE status | `#connection-state` | `streaming` / `done` / `errored` |
| Output log | `#loss-display` | Plain text, appends per-step |

### Key Details

- **Update function** (`training.html` lines 312–321): `updateMetrics(d)` reads every SSE metrics event and writes to these elements via `textContent`.
- **Completion signal** (`#connection-state` becomes `"done"`, `#loss-display` shows `"FINAL loss: X.XXXX"`).
- **No canvas dependency**: The `<canvas id="loss-chart">` exists for the visual chart, but assertions should target `#metric-loss` / `#metric-step` text nodes.

### Assertion Strategy (Playwright)

```javascript
// Wait for a numeric loss value (poll, not placeholder)
await page.waitForFunction(
  "() => { const el = document.querySelector('#metric-loss'); " +
  "return el && /\\d+\\.\\d{4}/.test(el.textContent); }",
  { timeout: 30000 }
);

// Wait for completion
await page.waitForFunction(
  "() => { const s = document.querySelector('#connection-state'); " +
  "return s && s.textContent.trim() === 'done'; }",
  { timeout: 60000 }
);
```

## Implications

- The highest-value test (SSE wiring) is fully feasible without canvas hacks.
- `#metric-loss` defaults to `—` (placeholder); always assert a **numeric pattern**, not "non-empty".
- Canvas content (`chart.js`) is secondary — the authoritative source is `#metric-step`/`#metric-loss`.

## References

- [ADR-034](../Decisions/ADR-034-playwright-ui-smoke-harness.md)
- [Session: 2026-06-21 Playwright UI Smoke Harness](../Sessions/2026-06-21-playwright-ui-smoke-harness.md)
- `anvil/api/templates/archetypes/training.html`
- `anvil/api/static/js/chart.js`
- `anvil/api/static/js/sse.js`