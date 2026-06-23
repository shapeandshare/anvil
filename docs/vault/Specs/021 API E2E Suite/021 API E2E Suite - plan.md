---
title: 021 API E2E Suite - plan
type: plan
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/021 API E2E Suite/
related:
  - '[[021 API E2E Suite]]'
created: ~
updated: ~
---
# Implementation Plan: Whole-API E2E Test Suite

**Branch**: `021-api-e2e-suite` | **Date**: 2026-06-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `docs/vault/Specs/021 API E2E Suite/spec.md`

## Summary

Build a comprehensive end-to-end API test suite covering all 14 routers mounted in the `/v1` API — training, experiments, datasets, corpora, registry, eval, eval-datasets, inference, compute, governance, health-ops, pages (HTML), learning, and content — plus a cross-router lifecycle integration test. The `learning` router's data routes are exercised within the inference module and its HTML lesson routes within the pages module (13 per-router test files cover all 14 routers). Tests run in-process via the existing async `httpx` ASGI transport `client` fixture (no live server, no network). Uses `local-stdlib` backend with tiny model config for training-involved tests. Experiment tracking is treated as potentially degraded (sidecar not started in tests) — experiment assertions read from local run state. No new dependencies.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pytest 7+, pytest-asyncio, httpx (all existing — no new deps)
**Storage**: N/A (tests are stateless; each test self-seeds via factory fixtures)
**Testing**: pytest + pytest-asyncio (existing `asyncio_mode = "auto"`, existing `tests/conftest.py` client/session fixtures)
**Target Platform**: Linux/macOS CI runners (same as project's existing CI `test` job)
**Project Type**: Web service — test suite addition (15 new test modules in `tests/e2e/api/`)
**Performance Goals**: Full suite < ~90s on CPU; lifecycle test initial 90s target, to be validated against a measured baseline during implementation and adjusted to measured-time-plus-headroom
**Constraints**: No new runtime/dev dependencies; in-process ASGI transport only (no uvicorn subprocess); tiny model (`n_embd=16, n_layer=1, n_head=4`) for training tests; coverage gate (`fail_under = 23`) must not regress; `tests/` exempt from docstring/lint strictness
**Scale/Scope**: 14 mounted routers × ~140 endpoints → 14 test modules (13 per-router files covering all 14 routers, since `learning` is folded into inference + pages; + 1 lifecycle), shared `tests/e2e/api/conftest.py` with ~7 factory fixtures

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Relevance | Status |
|---------|-----------|--------|
| **I** — Zero-Dependency Core | Not relevant (tests are outside `anvil/core/`) | ✅ N/A |
| **II** — Educational Clarity | Not relevant (tests are not educational walkthroughs) | ✅ N/A |
| **III** — Seeded Reproducibility | FR-009 requires deterministic runs (3x identical pass/fail). Tests self-seed with explicit fixtures. | ✅ Compliant |
| **IV** — TDD Mandatory | We are writing tests, not production code. TDD applies to *features being tested*, not the test suite itself. | ✅ N/A (etition) |
| **V** — Async-First | Tests use async fixtures (`async def`, `await client.get(…)`, `httpx.AsyncClient`). | ✅ Compliant |
| **VI** — `__init__.py` Policy | `tests/` is not part of the `anvil` package — no `__init__.py` needed at `tests/e2e/api/`. | ✅ Compliant |
| **VII** — Layered Architecture | Tests call the God Class through the API layer (the `client` fixture hits routes, not services directly). | ✅ Compliant |
| **VIII** — iOS-Grade Polish | Not relevant (test suite, not UI). | ✅ N/A |
| **IX** — Pit of Success | Training tests use `local-stdlib` (no GPU required). Tests run without external services. | ✅ Compliant |
| **X** — Domain-Driven Decomposition | Not relevant (test organization follows router boundaries, not service domains). | ✅ N/A |
| **Additional** — No type-error suppression | `tests/` is exempt from mypy/mypy strict via existing ruff per-file ignores. Standard `# type: ignore` rule is expected for test code. | ✅ Compliant |
| **Additional** — Lean dependencies | FR-014 explicitly forbids new dependencies. | ✅ Compliant |
| **Additional** — Pydantic over dataclass | Not relevant (test code uses standard python fixtures). | ✅ N/A |
| **Additional** — One class per file | Not relevant (test functions, not classes). | ✅ N/A |
| **Additional** — Alembic migrations | Not relevant (no schema changes). | ✅ N/A |
| **Additional** — ADRs + Vault | Session log required under AGENTS.md. Discovery notes for any real bug found. | ⚠️ Required post-implementation |

**Gate Result**: ✅ PASS — no violations. No complexity justification needed.

## Project Structure

### Documentation (this feature)

```
docs/vault/Specs/021 API E2E Suite/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research findings
├── data-model.md        # Phase 1 test data/entity model
├── quickstart.md        # Phase 1 developer quickstart
├── contracts/           # Phase 1 fixture/helper contracts
├── tasks.md             # Phase 2 task breakdown (created by /speckit.tasks)
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```
tests/e2e/api/
├── conftest.py                  # Shared seeding factories + helpers
├── test_health_ops.py          # health, services mgmt, demo bootstrap
├── test_datasets.py            # full dataset CRUD + upload + curate + import + export + samples
├── test_corpora.py             # corpus CRUD + ingest + fork + files + path resolve/analyze
├── test_training_router.py            # start/status/stream(SSE)/stop/configs + forward-pass graph
├── test_experiments.py         # list/compare/detail/metrics/mlflow/artifacts/download/delete
├── test_registry_api.py           # register/list/detail/versions/delete
├── test_inference_api.py          # tokenize/embeddings/attention/sampling/graphs/params
├── test_eval.py               # perplexity + eval-datasets CRUD
├── test_compute.py            # compute backends listing
├── test_governance.py         # audit/verify/report/licenses + takedown
├── test_content.py            # content-repo: corpora/sources/sessions/versions/locks/imports/streams
├── test_pages.py              # every HTML page route renders 200 + key landmark
└── test_lifecycle_journey.py  # cross-router money-path integration test
```

**Structure Decision**: Per-router domain modules under `tests/e2e/api/` mirroring the router files in `anvil/api/v1/`. The `learning` router (data routes `GET /inference/models`, `POST /inference/sample`; HTML lesson routes `/learn/*`) does not get its own file — its data routes are covered in `test_inference_api.py` and its HTML routes in `test_pages.py`, so 13 per-router files cover all 14 mounted routers. Shared factories + helpers in `conftest.py` at the same level. This is consistent with the existing `tests/e2e/test_endpoints.py` pattern and pytest's conftest discovery.

## Complexity Tracking

No constitution violations — complexity table omitted.

## Phase 0: Research

**Timing**: Runs during initial exploration. Background agents explore the codebase for exact enum values, response shapes, and infrastructure patterns.

**Research artifacts**: Consolidated in `research.md`.

## Phase 1: Design & Contracts

### 1. Data Model (`data-model.md`)

Documents the test entity model: factory fixture contracts, seed data shapes, lifecycle state machines, and shared helpers.

### 2. Interface Contracts (`contracts/`)

Documents the test interface contracts:
- Factory fixture signatures (parameters, return shapes, side effects)
- Helper function contracts (poll_until_terminal, read_sse_events)
- Expected error response shapes (404, 422, 409)
- Fixed seed data values

### 3. Quickstart (`quickstart.md`)

Developer onboarding guide: how to run, add tests, interpret failures, and extend coverage.

### 4. Agent Context Update

Update `.specify/agent-context-opencode.md` with this plan's technology choices.

## Phase 2: Tasks

Delegated to `/speckit.tasks` — produces `tasks.md` with ordered work breakdown.

## Sequencing

```
          ┌─ conftest.py ─────────────────┐
          │  (shared factories + helpers)  │
          └──────────┬────────────────────┘
                     │ (unblocks all modules)
     ┌───────────────┼───────────────┐
     ▼               ▼               ▼
  14 per-router   14 per-router   14 per-router
  modules (par)   modules (par)   modules (par)
     │               │               │
     └───────────────┼───────────────┘
                     ▼
          test_lifecycle_journey.py
          (depends on factories stable)
```

**Key**: `conftest.py` is the critical path — must be built first. All 14 per-router modules are mutually independent and can be parallelized. The lifecycle test goes last.