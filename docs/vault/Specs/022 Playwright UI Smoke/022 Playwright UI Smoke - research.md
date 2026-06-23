---
title: 022 Playwright UI Smoke - research
type: research
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/022 Playwright UI Smoke/
related:
  - '[[022 Playwright UI Smoke]]'
created: ~
updated: ~
---
# Research: Playwright UI Smoke Harness

**Phase**: 0 — Technology & Approach Research  
**Date**: 2026-06-21  
**Status**: Resolved (no NEEDS CLARIFICATION — all decisions documented from project context)

---

## Decision 1: Browser Automation Tool

**Decision**: Playwright (via `pytest-playwright`)
**Rationale**: Playwright provides async/SSE-native handling, auto-waiting API, Python-native integration via `pytest-playwright`, and no separate JS test toolchain — ideal for a Python-first repo. Chromium-only for v1.

**Alternatives considered**:
| Tool | Rejected because |
|------|-----------------|
| Selenium | Slower, no native async/SSE support, heavier dependencies |
| Cypress | Requires Node.js toolchain, no Python-native driver |
| Puppeteer | JS-only, no pytest integration |

**Source**: Original implementation plan document (`docs/playwright-ui-smoke-harness.md`)

---

## Decision 2: SSE Chart Assertion Strategy

**Decision**: Assert via observable DOM signal in the training UI
**Rationale**: The training page renders SSE-emitted data points in a visible DOM element (e.g., a metrics readout with step/loss text, a rendered point count, or a "step N / loss X" display). Instead of reverse-engineering the chart canvas, assert on a human-readable DOM signal.

**Approach**:
1. Identify the exact selector by reading `anvil/api/templates/archetypes/training.html` + `chart.js` + `sse.js` during implementation
2. Use Playwright's `expect(locator).to_have_text()` with a timeout for auto-waiting
3. Assert: the display contains at least one step/loss pair

**Alternatives considered**:
| Approach | Rejected because |
|----------|-----------------|
| Canvas pixel sampling | Fragile, dependent on rendering implementation |
| Network-level SSE interception | Over-engineered for a smoke test |
| Fixed sleep + check | Violates MUST NOT DO — no fixed sleeps |

**Source**: Implementation plan STEP 4 and Acceptance Criteria

---

## Decision 3: Test Data Seeding

**Decision**: Seed via API (httpx against `:8080`) where speed matters, create via UI where the form is the subject under test
**Rationale**: The training-SSE test and inference test need pre-existing data/models. Creating them via API is faster and more reliable than filling UI forms. The dataset upload test is the one that actually exercises the upload form through the browser.

**Approach**:
- `test_training_sse_wiring.py`: Create dataset via API → test UI training flow
- `test_inference_wiring.py`: Seed model via API → test UI inference flow
- `test_dataset_upload_wiring.py`: Upload via browser UI (this is the subject under test)
- `test_experiment_listing_wiring.py`: Reuse training run from SSE test or seed via API

**Source**: Implementation plan STEP 4 (precondition note) and STEP 6 (precondition note)

---

## Decision 4: Compose Lifecycle Ownership

**Decision**: `make test-browser` manages compose lifecycle (reset → up → tests → teardown)
**Rationale**: Mirrors the existing `test-system` target. The test conftest may provide a readiness wait but does NOT bring the stack up or down.

**Approach**:
- Makefile target: `docker compose down -v; up -d --build --wait; pytest tests/browser --no-cov; down -v`
- conftest.py: session-scoped fixture that waits for `GET /v1/health` to respond 200
- Chromium headless, 15s default timeout

**Source**: Implementation plan STEP 1 + Dependency/config changes #4

---

## Decision 5: CI Job Design

**Decision**: New Linux-only CI job; **NON-blocking for v1** (`continue-on-error: true`), promotable to blocking after a proven zero-flake record
**Rationale**: This suite is heavy (builds a Docker image, installs Chromium + system deps, runs real training) and therefore inherently flake-prone. The existing analogous heavy suite (`tests/system`) is **deliberately kept out of the blocking CI path** (local-only). Making a brand-new heavy browser suite a blocking gate from day one risks stalling all merges on flakes. Starting non-blocking preserves the deployment *signal* while protecting merge velocity; it can be promoted to blocking once stable.

**Approach**:
- Job steps: checkout → setup uv → `make setup` → `uv run playwright install --with-deps chromium` → `make test-browser`
- `continue-on-error: true` for v1; NOT added to `gate-status` `needs:`/gate loop yet
- Gated behind the same `bump-scope-guard` scope guard as other heavy gates
- Zero-flake priority: auto-waiting, generous CI-tolerant timeouts, tiny model config, service-readiness checks (web + MLflow sidecar)
- **Promotion criteria** (recorded in ADR): flip to `continue-on-error: false` and wire into `gate-status` after ≥10 consecutive zero-flake CI runs

**Revision note**: The original implementation plan proposed a blocking gate. This was revised during critical review (finding C1) to reconcile with the `tests/system` precedent and avoid a flaky blocking gate.

**Source**: Implementation plan Acceptance Criteria (CI job section), revised per critical-review finding C1

---

## Decision 6: ADR Prerequisite

**Decision**: ADR before any test code
**Rationale**: AGENTS.md Principle 4 requires ADRs for significant architecture decisions. Adding a browser-test toolchain qualifies. The ADR captures: Playwright choice rationale, scope boundary (smoke/wiring only), coverage gate exclusion, CI isolation, Chromium-only v1.

**Source**: Implementation plan "Decision required: ADR before coding" section