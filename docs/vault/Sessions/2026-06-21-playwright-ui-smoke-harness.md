---
title: "Session: 2026-06-21 — Playwright UI Smoke Harness Spec Kit"
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/tooling
source: agent
created: 2026-06-21
updated: 2026-06-21
aliases:
  - "Session: 2026-06-21 — Playwright UI Smoke Harness"
status: status/draft
---

# Session: 2026-06-21 — Playwright UI Smoke Harness Spec Kit

**Branch**: `017-playwright-ui-smoke`
**ADR**: [ADR-034](../Decisions/ADR-034-playwright-ui-smoke-harness.md)

## Summary

Completed the full spec-kit workflow (`specify → plan → tasks → analyze → implement`) for the Playwright UI Smoke Harness feature — a thin browser-based smoke test suite (≈5–6 tests) that verifies the application's polished frontend UI is wired to the working backend.

## Key Decisions

1. **Playwright over Selenium/Cypress** — Python-native via `pytest-playwright`, async/SSE handling, auto-waiting API. Documented in ADR-034.

2. **Non-blocking CI for v1** — The CI job runs with `continue-on-error: true`, NOT added to `gate-status` needs. This mirrors the existing `tests/system` precedent (intentionally kept out of the blocking CI path). Promotion criteria: ≥10 consecutive zero-flake runs. This was a revision from the original plan (finding C1 in critical review).

3. **Numeric loss assertion** — The `#metric-loss` element defaults to the `—` placeholder. The SSE test asserts against `/\d+\.\d{4}/` in a JS `wait_for_function` expression, not "is visible" (which would pass on the placeholder). Enabled by the SSE signal survey that confirmed `#metric-loss`/`#metric-step` are textual DOM nodes (not canvas-only).

4. **MLflow readiness** — The experiment listing test accounts for the MLflow sidecar starting independently of the web server. Both web health and MLflow API readiness are checked before tests begin.

5. **Model seeding requires inference-capable models** — The `model_seed` fixture trains a tiny real model, not just a metadata registration. Documented as a future optimization point.

## File Layout

```
tests/browser/
├── conftest.py                          # Readiness, page fixtures, console error checker, seed helpers
├── test_navigation_smoke.py             # 8 routes, nav bar, nav links (T006)
├── test_dataset_upload_wiring.py        # Upload .txt via UI → appears in listing (T007)
├── test_training_sse_wiring.py          # Start training → numeric #metric-loss → done state (T008)
├── test_experiment_listing_wiring.py    # Completed run → experiment listing with loss (T009)
└── test_inference_wiring.py             # Select model → prompt → non-empty output (T010)
```

## Ground Truth Verification

During the critical review, three agents verified key claims against the actual codebase:

| Claim | Result |
|-------|--------|
| 8 primary routes exist | ✅ All confirmed |
| `#metric-loss`/`#metric-step` are assertable text nodes | ✅ Confirmed — updated every SSE metrics event |
| `tests/system/` infra patterns (compose lifecycle, pytest config, CI structure) | ✅ All confirmed verbatim |
| SSE completion signal | ✅ `#connection-state="done"` + `#loss-display` "FINAL loss:" banner |

## Remaining

- **T013** (manual): Run `make test-browser` 3 consecutive times to validate zero-flake stability
- **T015**: Edge case verification (empty datasets page) — implicitly covered by navigation smoke, but a dedicated test could verify the empty-state rendering

## References

- [Spec](../../docs/vault/Specs/022 Playwright UI Smoke/spec.md)
- [Plan](../../docs/vault/Specs/022 Playwright UI Smoke/plan.md)
- [Tasks](../../docs/vault/Specs/022 Playwright UI Smoke/tasks.md)
- [ADR-034](../Decisions/ADR-034-playwright-ui-smoke-harness.md)

## Related

- [[Specs/022 Playwright UI Smoke/022 Playwright UI Smoke|022 Playwright UI Smoke]] — feature specification
- [[Decisions/ADR-034-playwright-ui-smoke-harness|ADR-034: Playwright UI Smoke Harness]] — architecture decision record
- [[Specs/021 API E2E Suite/021 API E2E Suite|021 API E2E Suite]] — related testing specification