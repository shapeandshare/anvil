---
title: 022 Playwright UI Smoke - plan
type: plan
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/022 Playwright UI Smoke/
related:
  - '[[022 Playwright UI Smoke]]'
created: ~
updated: ~
---
# Implementation Plan: Playwright UI Smoke Harness

**Branch**: `022-playwright-ui-smoke` | **Date**: 2026-06-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `docs/vault/Specs/022 Playwright UI Smoke/spec.md`

## Summary

Add a thin browser-based smoke test harness (≈4–6 tests) using Playwright to verify that the application's polished frontend UI is correctly wired to the working backend. Tests cover: page navigation without console errors, dataset upload through the UI, live training SSE chart updates, experiment listing after a completed run, and inference output rendering. The suite is independently invocable, Chromium-only (v1), and runs in a separate Linux-only CI job (**non-blocking for v1**, promotable to blocking after a proven zero-flake record) — never in the fast `make test` coverage loop.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `pytest-playwright>=0.5,<1` (dev-only, added to `[project.optional-dependencies].dev`)
**Storage**: N/A — tests are behavioral; seeded test data is ephemeral
**Testing**: pytest with `pytest-playwright` plugin, `--no-cov`, excluded via `--ignore=tests/browser`
**Target Platform**: Linux (CI: ubuntu-latest via GitHub Actions); macOS (local development)
**Project Type**: Browser smoke test suite (add-on to existing web application)
**Performance Goals**: ~5 min max for full suite (most time is tiny model training)
**Constraints**: Zero fixed `sleep()` calls — Playwright auto-waiting only; Chromium-only for v1; `tests/browser/` excluded from coverage gate (`fail_under` unaffected); ADR must be committed before test code; CI job is non-blocking for v1; readiness must cover the MLflow sidecar for run-history tests; live-loss assertions require a numeric (non-placeholder) value; inference test requires a generation-ready model
**Scale/Scope**: 4–6 smoke tests focused on UI-to-backend wiring; not a full UI regression suite

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Check | Rationale |
|---------|-------|-----------|
| **Article I — Zero-Dependency Core** | ✅ Pass | `pytest-playwright` is a dev-only dependency; `anvil/core/` remains stdlib-only, untouched |
| **Article IV — TDD Mandatory** | ✅ Pass | The tests themselves ARE the implementation; requirements are defined as testable GWT scenarios in the spec |
| **Article V — Async-First** | ✅ Pass | No architectural impact; Playwright test API is behavioral, tests don't introduce new sync/async concerns |
| **Article VI — `__init__.py` Ownership** | ✅ Pass | `tests/browser/` is a test directory, not a Python package — no `__init__.py` needed |
| **Article VII — Layered Architecture** | ✅ Pass | Tests go through the UI only; no DB or service layer access from test code |
| **Article IX — Pit of Success** | ✅ Pass | `playwright install chromium` is a one-time setup step documented in the target; `uv sync` installs the dep automatically |
| **Lean Dependencies** | ✅ Pass | One dev-only dep (`pytest-playwright`) for a new testing capability justified by the ADR |
| **ADR Requirement** | ✅ Pass | ADR gated before coding (Principle 4); documented in spec Assumptions |
| **Coverage Gate** | ✅ Pass | `tests/browser/*` added to `coverage.run.omit`; `fail_under` unchanged |
| **Type Safety / Lint** | ✅ Pass | `tests/**` is already excluded from docstring rules via per-file ignores; no new mypy concerns |

**No violations. All gates pass.**

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/022 Playwright UI Smoke/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # (/speckit.tasks command — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Single project — test-only additions to existing Python project
tests/
├── browser/                       # NEW: top-level test directory (peer of tests/system/)
│   ├── conftest.py                # compose lifecycle, page fixtures, helpers
│   ├── test_navigation_smoke.py   # all primary pages load without errors
│   ├── test_dataset_upload_wiring.py
│   ├── test_training_sse_wiring.py
│   ├── test_experiment_listing_wiring.py
│   └── test_inference_wiring.py
└── system/                        # existing (unchanged)

# Config changes — no new source code outside tests/
pyproject.toml          # Add pytest-playwright dep, --ignore=tests/browser, coverage omit
Makefile                # Add test-browser target
.github/workflows/ci.yml  # Add Linux-only browser test job
```

**Structure Decision**: New `tests/browser/` directory mirrors existing `tests/system/` pattern. All config changes are minimal additions to existing files — no new config files. This keeps the suite clean, separately invokable, and avoids colliding with the existing system conftest.

## Complexity Tracking

No constitution violations to justify.
