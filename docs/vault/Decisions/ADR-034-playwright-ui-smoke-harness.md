---
title: "ADR-034: Playwright UI Smoke Harness"
type: decision
tags:
  - type/decision
  - domain/testing
  - domain/ci
created: 2026-06-21
updated: 2026-06-21
aliases:
  - "ADR-034: Playwright UI Smoke Harness"
  - ADR-034
status: status/draft
source: agent
code-refs:
  - specs/017-playwright-ui-smoke/spec.md
  - specs/017-playwright-ui-smoke/plan.md
  - specs/017-playwright-ui-smoke/tasks.md
---

# ADR-034: Playwright UI Smoke Harness

- **Status**: draft
- **Date**: 2026-06-21
- **Author**: Sisyphus (AI agent)

## Context

The anvil application has a polished modern UI with Jinja2-rendered pages, vanilla ES6 module JavaScript, and a FastAPI backend. The existing system test suite (`tests/system/`) uses httpx to verify backend API correctness — it has no browser and cannot verify that the UI is actually wired to the backend.

What a browser uniquely verifies: forms submit to the right endpoints, the SSE training chart receives live points, runs appear in tables, buttons enable/disable, and primary navigation works.

## Decision

Add a thin Playwright-based browser smoke test harness (≈5–6 tests) in `tests/browser/` that runs as a non-blocking Linux-only CI job (v1), promotable to blocking after a proven zero-flake record.

### Tool Choice: Playwright over Selenium/Cypress

| Factor | Playwright | Selenium | Cypress |
|--------|-----------|----------|---------|
| Python-native integration | ✅ `pytest-playwright` | ✅ `selenium` package | ❌ Requires Node.js |
| Auto-waiting API | ✅ Built-in | ❌ Manual waits needed | ✅ Built-in |
| Native SSE/async handling | ✅ `page.on('console')`, event-based | ⚠️ Limited | ⚠️ HTTP-level only |
| pytest integration | ✅ Native plugin | ⚠️ Third-party | ❌ Different runner |
| Headless Chromium | ✅ | ✅ | ⚠️ Electron-based |
| Cross-browser matrix | ✅ (Chromium/Firefox/WebKit) | ✅ (Any WebDriver) | ⚠️ Limited |

### Scope Boundary

**In scope**: UI-to-backend wiring smoke tests (navigation, dataset upload, training SSE, experiment listing, inference). ≈5–6 tests covering the primary user-facing workflows.

**Out of scope**: Functional/backend correctness (owned by httpx e2e suite), visual pixel regression, cross-browser matrix, auth/SaaS flows, accessibility audits.

### CI Isolation

- **v1: NON-blocking** (`continue-on-error: true`) — the existing analogous heavy suite (`tests/system/`) is deliberately kept out of the blocking CI path. A flaky heavy job must not stall all merges.
- **v1**: NOT added to `gate-status` job's `needs:` list or gate loop.
- **Promotion criteria**: Flip to `continue-on-error: false` and wire into `gate-status` after ≥10 consecutive zero-flake CI runs on `main`.
- Gated behind the same `bump-scope-guard` scope guard (`if: needs.bump-scope-guard.outputs.scope != 'version-only'`).

### Chromium-Only for v1

The initial suite targets Chromium only. Firefox and WebKit are available via Playwright's cross-browser API but introduce ordering complexity and maintenance cost that aren't justified for a smoke suite. Cross-browser testing may be added to a future iteration.

### Coverage Exclusion

`tests/browser/*` is omitted from `[tool.coverage.run].omit` so the coverage gate (`fail_under = 23`) is unaffected. Browser tests run with `--no-cov`.

## Consequences

**Positive**:
- The highest-value UI-backend interaction (SSE training chart) is verifiable end-to-end using assertable DOM text nodes (`#metric-loss`, `#metric-step`)
- Zero new runtime dependencies — `pytest-playwright` is dev-only
- Reuses the existing compose lifecycle pattern from `tests/system/`
- Non-blocking CI protects merge velocity from flaky infrastructure

**Negative**:
- Requires `playwright install chromium` (one-time setup) — adds friction to local dev setup
- Heavy CI job (Docker compose build + Playwright browser install + real training) — longer total CI time
- Not a full UI regression suite — visual and cross-browser coverage are deferred

**Risks**:
- Flaky blocking gate if promoted prematurely — mitigated by ≥10-run zero-flake promotion criteria
- MLflow sidecar readiness for experiment listing tests — mitigated by service-readiness probes in conftest
- Placeholder glyph (`—`) in `#metric-loss` before first data point — mitigated by numeric-pattern assertion

## Alternatives Considered

| Alternative | Rejected because |
|-------------|-----------------|
| Selenium | Slower, no native SSE/async support, heavier dependencies |
| Cypress | Requires Node.js toolchain, not Python-native, no pytest integration |
| API-only testing (httpx) | Cannot verify UI wiring — that's the whole point of this suite |
| Visual regression (Percy/Chromatic) | High maintenance; 27 themes would require frequent snapshot updates |

## References

- [Spec](specs/017-playwright-ui-smoke/spec.md)
- [Plan](specs/017-playwright-ui-smoke/plan.md)
- [Tasks](specs/017-playwright-ui-smoke/tasks.md)