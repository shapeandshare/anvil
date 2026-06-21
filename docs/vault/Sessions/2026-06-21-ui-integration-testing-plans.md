---
created: '2026-06-21T00:00:00.000Z'
source: agent
tags:
  - type/session-log
  - domain/tooling
  - domain/ui
title: 'Session: UI Integration Testing Strategy — API E2E + Playwright Plans'
type: session-log
updated: '2026-06-21T00:00:00.000Z'
aliases:
  - 'Session: UI Integration Testing Plans'
  - UI Integration Testing Plans
---
# Session: UI Integration Testing Strategy — API E2E + Playwright Plans

**Date**: 2026-06-21
**Status**: Completed (planning only — no test code written this session)

## Summary

Investigated whether the UI can be integration-tested with Playwright, then reframed the effort
around the user's clarification that the theme engine is chrome and the priority is verifying the
application's core functions. Concluded the highest-ROI coverage is a **server-side whole-API e2e
suite** (the existing `tests/e2e/test_endpoints.py` is only 3 trivial smoke tests against a
~140-endpoint API), with a **thin Playwright browser layer** reserved for what only a real browser
can verify — UI-to-backend wiring (form submits, the live SSE training chart, runs appearing in
tables). Produced two handoff-ready implementation plans, split cleanly at the **API layer** and
**browser layer**.

## Findings

- **Test infrastructure**: `tests/conftest.py` exposes an async `client` fixture
  (`httpx.AsyncClient` + `ASGITransport(app=app)`) that creates+drops all tables per test. pytest
  runs with `asyncio_mode = "auto"` and `--ignore=tests/system`. Coverage gate is
  `fail_under = 23` (AGENTS.md's "100%" is aspirational, not enforced).
- **Existing e2e is a stub**: `tests/e2e/test_endpoints.py` covers only `/v1/health`,
  `/v1/datasets`, `/v1/experiments` list — no lifecycle, no per-router coverage.
- **System tests already boot the real app**: `tests/system/` brings up the container on `:8080`
  via `make test-system` (docker compose) and asserts with httpx + `--no-cov`. Playwright reuses
  this exact lifecycle pattern.
- **Frontend is vanilla ES6 + Jinja2, no build step** — `sse.js` (EventSource), `chart.js` (live
  loss chart). The SSE training stream is `GET /v1/training/stream/{run_id}`. This dynamic,
  browser-only behavior is what justifies a (thin) Playwright layer.
- **API surface**: 14 routers, ~140 endpoints (verified via grep of `@router.*` decorators in
  `anvil/api/v1/`). The whole-API plan enumerates them per-router.

## Artifacts Produced

- `docs/functional-api-e2e-suite.md` — **API layer**. Whole-`/v1`-API e2e coverage: one test
  module per router (14) + a cross-router lifecycle backbone (upload → dataset → train → metrics →
  experiment → register → export → infer). httpx/ASGI, no new deps, runs in `make test`.
- `docs/playwright-ui-smoke-harness.md` — **browser layer**. ≈4–6 Playwright smoke tests for
  UI wiring (nav, upload form, live SSE chart, experiment listing, inference output). Adds
  `pytest-playwright` (dev extra only), a `make test-browser` target, and a **blocking**
  Linux-only CI job. Requires an ADR before implementation (per AGENTS.md Principle 4).

## Decisions

- **Split at API vs browser layer** (user directive). API plan covers correctness of the entire
  API; browser plan covers only that the UI is wired to it — no duplication of functional asserts.
- **Browser CI job is a required, blocking gate** (user directive) — wired into `gate-status`
  `needs:`, no `continue-on-error`; consequently the browser suite must be engineered zero-flake.
- **Lead with the API e2e suite** — cheapest, most deterministic, protects the most.
- Plans authored to `docs/` (user directive) rather than `.sisyphus/plans/`.

## References

- `tests/conftest.py` — async `client` / `session` fixtures
- `tests/e2e/test_endpoints.py` — the 3-test stub being expanded
- `tests/system/conftest.py`, `Makefile` `test-system` target — reused compose lifecycle
- `anvil/api/v1/` — 14 routers enumerated in the API plan
- `anvil/api/static/js/sse.js`, `chart.js` — SSE + live chart (browser-plan targets)
