# Codebase Remediation — Research & Context

**Branch**: `066-codebase-remediation` (master overview) / individual feature branches per spec  
**Created**: 2026-07-18  
**Status**: Draft  
**Input**: Codebase review of anvil for anti-patterns and best-practice gaps in Python, FastAPI, Pydantic, and solution structure

## Source of Findings

This remediation spec suite was produced from a comprehensive codebase review across 5 dimensions:

1. **FastAPI Route Design** — DI patterns, response models, error handling, business logic placement
2. **Service Layer Architecture** — SOLID principles, async usage, dependency flow, god classes
3. **DB/Repository Layer** — SQLAlchemy 2.0 patterns, FK indexes, N+1 risks, session management
4. **Pydantic/Config/Exceptions** — pydantic-settings adoption, validation, exception hierarchy
5. **Testing Patterns** — coverage thresholds, isolation, mocking, parametrization

## Current State Summary

| Layer | Assessment | Key Metrics |
|-------|-----------|-------------|
| FastAPI Routes | ⚠️ Needs work | 23 route files, 0 with `response_model=` |
| Service Layer | ⚠️ Needs work | 14 domain sub-packages, services up to 1474 lines |
| DB/Repository | ✅ Good | 31 models, 30 repos, SQLAlchemy 2.0 Mapped[] |
| Pydantic/Config | ❌ Critical gap | `pydantic-settings` dep unused, `dict[str, Any]` config |
| Testing | ⚠️ Needs work | `fail_under=23`, 300+ test files |

## Key Architecture Constraints (from Constitution)

- **Article IV**: TDD Mandatory — Red-Green-Refactor, ratcheting coverage
- **Article V**: Async-First — web, DB, service layers must be async
- **Article VII**: Layered Architecture — Repository → Service → AnvilWorkbench → Routes/CLI
- **Article XI**: Simplicity First — boring over novel, YAGNI
- **Principle 2**: TDD Always — test before implementation
- **Principle 11**: Enums over magic strings
- **Principle 13**: Simplicity First (boring technology)
- **Principle 14**: No lazy imports (top-of-file only)

## File Inventory (Key Files Affected)

### Routes
- `anvil/api/v1/training.py` — module-level singletons, `_tasks` mutable state, `asyncio.run()`
- `anvil/api/v1/experiments.py` — 9 `TrackingService()` instantiations, `LlamaModel` in handler
- `anvil/api/v1/inference.py` — module-level `_svc` singleton
- `anvil/api/v1/datasets.py` — file reading in handlers
- `anvil/api/v1/corpora.py` — business logic in handlers
- `anvil/api/v1/eval_datasets.py` — module-level `_tracking_svc`
- `anvil/api/v1/fine_tune_datasets.py` — `_tasks` mutable state, `workbench._session` access
- `anvil/api/v1/content.py` — `_injection_queue` module-level mutable state
- `anvil/api/v1/schemas_dataset.py` — missing `extra="forbid"`, missing `from __future__ import annotations`
- `anvil/api/v1/schemas_content.py` — missing `extra="forbid"` (12 models)
- `anvil/api/v1/inference_schemas.py` — missing `from __future__ import annotations`
- `anvil/api/v1/schemas_eval.py` — missing `from __future__ import annotations`
- `anvil/api/deps.py` — DI module (reference for proper pattern)

### Services
- `anvil/services/training/training.py` — `asyncio.run(_load())` in `_load_docs()`
- `anvil/services/training/training_run_service.py` — creates `InferenceService()` directly
- `anvil/services/inference/inference.py` — 1400+ lines, creates `TrackingService()` directly
- `anvil/services/tracking/tracking.py` — 1474+ lines
- `anvil/services/datasets/datasets.py` — accesses `_repo._session` directly
- `anvil/services/compute/registry.py` — reference for plugin pattern

### DB Layer
- `anvil/db/session.py` — `cast()` calls, `assert` statements, module-level globals
- `anvil/db/base.py` — DeclarativeBase
- `anvil/db/models/external_model.py` — deprecated legacy model
- `anvil/db/repositories/` — 30 repos, no `selectinload()` usage
- FK columns lacking indexes: `FineTuneDataset.dataset_id`, `FineTuneDataset.chat_template_id`, `LoRAAdapter.external_model_id`, license FKs

### Config
- `anvil/config.py` — `dict[str, Any]` config, global `_resolved_mlflow_uri`, `lru_cache`
- `pyproject.toml:23` — `pydantic-settings>=2.14.2` unused
- `anvil/client/_shared/server_config.py` — reference for proper BaseSettings pattern

### Exceptions
- `anvil/client/_shared/api_error.py` — reference for proper hierarchy
- `anvil/services/_shared/encryption_errors.py` — reference for cohesive group
- `anvil/services/_shared/import_types.py` — `ModelSourceError` structured exception
- `anvil/services/catalog/catalog_unavailable_error.py` — standalone RuntimeError
- `anvil/services/training/divergence_error.py` — standalone Exception
- `anvil/db/migration_error.py` — standalone RuntimeError

### Testing
- `tests/conftest.py` — root fixtures
- `tests/unit/conftest.py` — `in_memory_session` fixture
- `tests/e2e/api/conftest.py` — factory helpers
- `tests/unit/services/test_tracking_service.py` — global state manipulation
- `tests/unit/api/test_training_validation.py` — monkeypatch of module-level singletons

## Findings Index

| # | Priority | Title | Directory |
|---|----------|-------|-----------|
| 083 | P0 | Migrate config to pydantic-settings | `083-config-pydantic-settings/` |
| 067 | P0 | Add response_model to all routes | `067-api-response-models/` |
| 068 | P0 | Remove asyncio.run() blocking call | `068-training-service-async-fix/` |
| 069 | P0 | Replace module-level service singletons | `069-route-di-cleanup/` |
| 070 | P1 | Extract business logic from experiments.py | `070-experiments-service-extraction/` |
| 071 | P1 | Inject cross-service dependencies | `071-service-di-injection/` |
| 072 | P1 | Standardize API error response format | `072-error-response-standardization/` |
| 073 | P1 | Add extra="forbid" to schema files | `073-pydantic-schema-validation/` |
| 074 | P1 | Remove module-level mutable state | `074-module-state-removal/` |
| 075 | P1 | Raise coverage threshold | `075-coverage-threshold-ratchet/` |
| 076 | P2 | Split InferenceService | `076-inference-service-decomposition/` |
| 077 | P2 | Clean up session.py (cast/assert/module globals) | `077-session-py-cleanup/` |
| 078 | P2 | Annotations consistency (PEP 563) | `078-annotations-consistency/` |
| 079 | P2 | Exception hierarchy unification | `079-exception-hierarchy-unification/` |
| 080 | P2 | FK indexes and N+1 prevention | `080-db-indexes-eager-loading/` |

## Technology Stack

- **Python 3.11+** — PEP 604 unions, `StrEnum`, `from __future__ import annotations`
- **FastAPI** — route handling, DI, middleware, SSE streaming
- **Pydantic v2** — `BaseModel`, `field_validator`, `ConfigDict`, `pydantic-settings`
- **SQLAlchemy 2.0** — async, `Mapped[]`, `mapped_column()`, Alembic
- **pytest** — `pytest-asyncio`, `httpx.AsyncClient` (ASGI transport)
- **mypy --strict** — type checking enforced

## Design Decisions

- All specs follow the spec-template.md format from `.specify/templates/`
- Priority assignments: P0 (blocker/critical), P1 (important), P2 (improvement)
- Changes stay on `opencode/witty-forest` branch for a single PR merge
- Each spec is independently implementable and testable
