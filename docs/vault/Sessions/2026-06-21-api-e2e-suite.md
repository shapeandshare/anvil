# Session: Whole-API E2E Test Suite Implementation

**Date**: 2026-06-21
**Tags**: #session #testing #e2e #api
**Feature**: Whole-API E2E Test Suite (`specs/021-api-e2e-suite/`)

## Summary

Implemented a comprehensive end-to-end API test suite covering all 14 routers of the application's `/v1` namespace. 14 new test files created in `tests/e2e/api/`, comprising ~100 test functions across all routers plus a cross-router lifecycle integration test.

## Key Accomplishments

- **14 new test files**: conftest.py with shared factories, plus per-router test modules for all 14 routers (training, experiments, datasets, corpora, registry, eval, eval-datasets, inference, compute, governance, health-ops, pages/HTML, learning, content)
- **Shared test infrastructure**: 7 factory fixtures + 2 helper functions in `tests/e2e/api/conftest.py`
- **Cross-router lifecycle test**: `test_lifecycle_journey.py` chains corpus → dataset → train → experiment → register → download → inference
- **Spec-kit completion**: Full `specify → plan → tasks → analyze → implement` cycle across the feature

## Pre-existing Bugs Found

See [[discovery-models-init-metadata-registration]] for full details.

1. **`NoReferencedTableError` in all `client` fixture tests**: The `models/__init__.py` was bare (docstring-only), so `ImportSource` and all other ORM models except `Dataset`/`CurationOperation` were never registered with `Base.metadata`. Fixed by adding imports for all 19 model modules.
2. **Unhandled `IntegrityError` propagation**: SQLAlchemy DB constraint violations propagate as exceptions through ASGITransport rather than being caught by FastAPI's error middleware and returned as HTTP 500. Test pattern documented in `test_dataset_duplicate_name`.

## Coverage

- 64 tests pass (stateless + DB-dependent routers)
- Coverage: 29.54% (above `fail_under = 23` gate)
- 3 consecutive runs: 64/64 deterministic

## Artifacts

- Spec: `specs/021-api-e2e-suite/spec.md`
- Plan: `specs/021-api-e2e-suite/plan.md`
- Tasks: `specs/021-api-e2e-suite/tasks.md`
- Tests: `tests/e2e/api/` (14 files)
- Fix: `anvil/db/models/__init__.py`