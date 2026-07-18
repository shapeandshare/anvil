# Feature Specification: Extract Business Logic from experiments.py

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P1  
**Input**: Codebase review finding #070 — `experiments.py` contains extensive business logic in route handlers and helper functions: `_enrich_experiments()` (DB lookups), `_resolve_experiment_name()`, `_resolve_name_from_ds()`, `_resolve_name_from_corpus()`, `_set_artifact_flag()` (filesystem checks), `_hyperparams_from_mlflow()`, and direct `LlamaModel` instantiation inside `get_experiment()` handler.

## User Scenarios & Testing

### User Story 1 - Route handlers are thin (Priority: P1)

Route handlers in `experiments.py` only extract params from the request, call a service method, and format the response. No business logic, no DB access, no model instantiation.

**Why this priority**: The current `get_experiment` handler (lines 277-400+) instantiates `LlamaModel`, reads JSON files, queries MLflow directly, calculates durations, and estimates memory. This violates layer discipline (Article VII) and makes the route untestable without monkeypatching multiple modules.

**Independent Test**: A route handler test needs only to mock the service layer, not DB, filesystem, MLflow, and core engine simultaneously.

**Acceptance Scenarios**:

1. **Given** `GET /v1/experiments/{id}` is called, **When** the handler executes, **Then** it calls at most one service method (e.g., `tracking.get_experiment_detail(id)`) and returns the result.
2. **Given** `GET /v1/experiments` is called, **When** the handler executes, **Then** it calls a service method for enrichment rather than doing DB lookups inline.
3. **Given** a test for `get_experiment`, **When** it overrides the experiment service dependency, **Then** it does not need to mock `LlamaModel`, `MlflowClient`, `json.loads`, or `Path.read_text`.

---

### User Story 2 - Experiment service owns business logic (Priority: P1)

All business logic for experiment operations (enrichment, artifact discovery, model architecture extraction, memory estimation) lives in the service layer.

**Why this priority**: Service layer is testable, injectable, and follows the project architecture. Putting logic there makes it reusable across routes, CLI, and future consumers.

**Independent Test**: The experiment service methods can be unit-tested without HTTP transport.

**Acceptance Scenarios**:

1. **Given** the experiment tracking service, **When** `get_experiment_detail(id)` is called, **Then** it returns a fully enriched response dict (or Pydantic model) with all fields currently computed in the route handler.
2. **Given** the experiment service, **When** `enrich_experiments(experiments)` is called, **Then** it performs DB lookups and sets artifact flags — all internally.

### Edge Cases

- `_get_mlflow_experiment_id()` catches `MlflowException` — this error handling must be preserved in the service layer.
- Memory estimation via `estimate_training_memory()` must remain callable from the service.
- The `_build_mlflow_url` helper builds browser-facing links from the request — this can remain in the route layer (HTTP context).

## Requirements

### Functional Requirements

- **FR-001**: A new service method `TrackingService.get_experiment_detail(id) -> ExperimentDetail` (or similar) MUST encapsulate all business logic currently in the `get_experiment` handler.
- **FR-002**: All enrichment helpers (`_enrich_experiments`, `_resolve_experiment_name`, `_resolve_name_from_ds`, `_resolve_name_from_corpus`, `_set_artifact_flag`) MUST be moved to a service class.
- **FR-003**: The `_hyperparams_from_mlflow` coercion logic MUST be moved to a service method.
- **FR-004**: `LlamaModel` instantiation for architecture extraction MUST be moved to the service layer.
- **FR-005**: MLBrowser URL construction (`_build_mlflow_url`) MAY remain in the route layer as it depends on the HTTP `Request` object.
- **FR-006**: All existing behavior MUST be preserved — the API response shape must not change.
- **FR-007**: Unit tests for the extracted service methods MUST be written following TDD (Red-Green-Refactor).

### Key Entities

- **ExperimentService** (new or extension of TrackingService): Encapsulates experiment business logic
- **ExperimentDetail** (Pydantic response model): Structured return type for experiment details

## Success Criteria

### Measurable Outcomes

- **SC-001**: `experiments.py` line count reduced by at least 50% (from ~864 lines to ~430).
- **SC-002**: Zero `LlamaModel` references in `anvil/api/v1/experiments.py`.
- **SC-003**: Zero `MlflowClient` references in `anvil/api/v1/experiments.py`.
- **SC-004**: All extraction helpers tested via unit tests on the service, not mocked via monkeypatch on module-level functions.
- **SC-005**: `make test` and `make typecheck` pass.

## Assumptions

- The new service methods will be added to an existing service class (TrackingService) or a new dedicated service, following the judgment of the implementer.
- Request-dependent logic (MLflow URL construction) stays in the route layer.
- The response format is unchanged — only the internal plumbing changes.
