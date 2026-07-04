---
aliases:
  - large-scale-coverage-burst-2026-07-03
created: '2026-07-03'
session: 2026-07-03-large-scale-coverage-burst
source: agent
status: draft
tags:
  - type/session-log
  - domain/tooling
  - domain/test-coverage
  - status/draft
title: 'Session: Large-Scale Coverage Burst — 80+ New Test Files, +8.76 pts'
type: session-log
updated: '2026-07-03'
---
# Session: Large-Scale Coverage Burst — 80+ New Test Files, +8.76 pts

**Date**: 2026-07-03
**Trigger**: Increase test coverage "about 15% over boot" — fan out to subagents for speed.

## Summary

Used Sisyphus orchestration to deploy 4 parallel `deep` sub-agents executing Phase 1 of a multi-phase coverage attack plan. Each agent owned a domain: client package commands, API v1 routes, GPU/tokenizer/CLI modules, and service-layer test expansion. All agents ran simultaneously with exhaustive "MUST DO / MUST NOT DO" prompts.

## Coverage Delta

| Metric | Before | After | Δ |
|--------|--------|-------|---|
| **Total coverage** | 36.87% | **45.63%** | **+8.76 pts** |
| **Total tests** | 288 | **1,146** | **+858** |
| **New test files** | — | **~80** | — |
| **Source files modified** | — | **0** | No source changes |

## Per-Agent Results

### Agent 1a: Client Package (0% → 90%+)
Created **53 test files** covering all 52 command classes and 1 new DTO in `anvil/client/`. Each command tests HTTP method, URL path, optional parameter inclusion/exclusion, and return value passthrough using `AsyncMock(return_value=...)`. DTO tests cover minimal/full construction, defaults, validation, and serialization round-trips.

| Domain | Files | Coverage |
|--------|-------|----------|
| compute, content, corpora | 13 commands | 100% |
| datasets, eval | 10 commands | 100% |
| experiments, governance | 8 commands | 100% |
| health, inference, models | 7 commands | 100% |
| registry, services, training | 11 commands + 1 DTO | 100% |

### Agent 1b: API v1 Routes (7-30% → 70-100%)
Created/expanded 6 test files. Used the existing `client` fixture (httpx AsyncClient with ASGITransport, in-memory SQLite) and `app.dependency_overrides` pattern for workbench mocking.

| Route Module | Before | After |
|-------------|--------|-------|
| `eval.py` | 26% | **100%** |
| `teach.py` | 29% | **100%** |
| `models.py` | 30% | **96%** |
| `health_ops.py` | 24% | **92%** |
| `inference.py` | 21% | **88%** |
| `experiments.py` | 12% | **88%** |
| `registry.py` | 7% | **73%** |
| `fine_tune_datasets.py` | 24% | **70%** |

### Agent 1c: GPU + Tokenizer + CLI + Hub (0-94% → 93-100%)
Expanded/created tests for 5 modules. Discovered that `hub_client.py` and `gpu.py` already had comprehensive tests (97% and 100%) — they just weren't in the `make test` batch.

| Module | Before | After |
|--------|--------|-------|
| `gpu.py` | 21% | **100%** |
| `backup/cli.py` | 0% | **100%** |
| `instances/cli.py` | 94% | **100%** |
| `_sentencepiece_tokenizer.py` | 0% | **93%** |
| `hub_client.py` | 0% | **97%** (existed) |

### Agent 1d: Service Expansion (11-19% → 59-97%)
Expanded 5 service test files. Used targeted coverage reports to identify exact missing lines before writing test cases.

| Module | Before | After |
|--------|--------|-------|
| `backup_service.py` | 18% | **97%** |
| `dataset_import.py` | 11% | **93%** |
| `merge_service.py` | 15% | **79%** |
| `hf_source.py` | 15% | **60%** |
| `evaluation_service.py` | 19% | **59%** |

## Key Decisions

- **All 4 agents in parallel**: Used `task(category="deep", run_in_background=true, ...)` to deploy all agents simultaneously, maximizing throughput.
- **Exhaustive prompt structure**: Each prompt included TASK, EXPECTED OUTCOME, REQUIRED TOOLS, MUST DO, MUST NOT DO, and CONTEXT sections. This prevented tool sprawl and scope creep.
- **No source code modified**: Every test file was either new or appended to existing test files. Zero production code touched.
- **Client testing strategy**: All 52 command classes use the same `AbstractCommand` pattern. Tests use `AsyncMock` on `transport.request()` to verify HTTP method, URL path, parameter handling, and return value passthrough — no real HTTP calls.
- **API route testing**: Used the existing `client` fixture (ASGITransport + in-memory SQLite) for integration-style tests with mocked workbench dependencies via `app.dependency_overrides`.
- **`hub_client.py` discovery**: Marked as 0% coverage but actually had a 668-line test file achieving 97% coverage — the test file wasn't in the `make test` batch list.

## Remaining High-Value Targets (Phase 2)

| Module | Coverage | Missing | Notes |
|--------|----------|---------|-------|
| `tracking/tracking.py` | 12% | ~468 stmts | Complex MLflow orchestration |
| `training_run_service.py` | 10% | ~325 stmts | Complex state machine |
| `tracking/mlflow_inputs.py` | 21% | ~43 stmts | Needs MLflow mock |
| `api/v1/datasets.py` | 57% | ~109 stmts | Large route file |
| `api/v1/learning.py` | 52% | ~100 stmts | Educational content routes |
| `workbench.py` | 68% | ~131 stmts | God class, many delegations |
| `instance_lifecycle_service.py` | 17% | ~150 stmts | Complex lifecycle |

## Files Changed

New test files (~80 total, all under `tests/`):
- `tests/unit/client/**/test_*.py` — 53 command tests + 1 DTO test
- `tests/unit/api/v1/test_registry.py`, `test_fine_tune_datasets.py`, `test_teach.py` — 3 new API route test files
- `tests/unit/services/test_evaluation_service.py` — new evaluation service test file
- `tests/unit/services/test_sentencepiece_tokenizer.py` — new tokenizer test file

Modified test files (appended to):
- `tests/unit/api/v1/test_eval.py`, `test_inference.py`, `test_models.py`
- `tests/unit/services/backup/test_backup_service.py`, `test_cli.py`
- `tests/unit/services/test_hf_source.py`, `test_instances_cli.py`
- `tests/unit/services/test_merge_service.py`
- `tests/unit/test_dataset_import.py`

## Verification

- **`make test` (batch)**: 305 passed, 76 warnings (same as baseline)
- **All new tests**: 1,146 total passed (batch + 841 new)
- **`make format`**: 30 files reformatted, clean
- **`make lint`**: Clean (16 UP017 auto-fixes applied)
- **Pre-existing failures**: `test_serve_starts_uvicorn` (KeyError: 'host') — unchanged from baseline
