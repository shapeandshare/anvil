# Feature Specification: Replace Module-Level Service Singletons with Proper DI

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P0  
**Input**: Codebase review finding #069 — Multiple route modules instantiate services at module load time (`training.py:126-127`, `inference.py:33`, `eval_datasets.py:21`, `experiments.py` at 9 locations) instead of using FastAPI `Depends()` injection.

## User Scenarios & Testing

### User Story 1 - Services injected via Depends (Priority: P1)

Route handlers receive service instances through FastAPI dependency injection rather than importing module-level singletons.

**Why this priority**: Module-level singletons create tight coupling, prevent request-scoped lifecycle, and require monkeypatching in tests. Proper DI enables cleaner testing, lifecycle management, and service isolation.

**Independent Test**: A route handler can be tested by replacing its injected service with a mock via `app.dependency_overrides[]` instead of `monkeypatch.setattr(module, "svc", mock)`.

**Acceptance Scenarios**:

1. **Given** a route module with `router = APIRouter()`, **When** the module is imported, **Then** no service is instantiated at module level (no `svc = ServiceClass()` at the top of the file).
2. **Given** a route handler function, **When** it needs a service, **Then** the service is injected via `Depends(get_service)` parameter.
3. **Given** a test needs to mock a service, **When** it uses `app.dependency_overrides[get_training_service] = lambda: mock`, **Then** the mock is used instead of the real service.

---

### User Story 2 - Injectable tracking service (Priority: P1)

`TrackingService` instances are created through DI rather than 9+ separate `TrackingService()` instantiations inside `experiments.py` route handlers.

**Why this priority**: Each `TrackingService()` call creates a new MLflow client connection. In degraded state, each instantiation retries connection. Centralizing to one injectable instance avoids redundant connections and retries.

**Independent Test**: A test creates a `TrackingService` mock once, overrides it, and verifies that all experiment routes use the same mock instance.

**Acceptance Scenarios**:

1. **Given** `experiments.py` routes, **When** they need tracking, **Then** they receive the tracking service via `Depends()` rather than creating `TrackingService()` inline.
2. **Given** a single request processes multiple experiment routes, **When** each route accesses tracking, **Then** they share the same tracking service instance (scoped to the workbench or request).

### Edge Cases

- What about the `_call_or_400` helper in `inference.py` that wraps service calls? Needs to receive the service as a parameter, not use the module-level `_svc`.
- What about route helpers that are plain functions, not route handlers? They should receive services as parameters from the calling route handler.

## Requirements

### Functional Requirements

- **FR-001**: All module-level service instantiations in route files MUST be removed (no `svc = ServiceClass()` at module top level).
- **FR-002**: Each service type that routes consume MUST have a corresponding `Depends()`-compatible dependency function (e.g., `get_training_service()`, `get_tracking_service()`).
- **FR-003**: Dependency functions MUST be defined in `anvil/api/deps.py` (or domain-specific deps modules) and registered with `app.dependency_overrides` for testability.
- **FR-004**: The `inference.py` `_svc` singleton and all `TrackingService()` inline instantiations in `experiments.py` MUST be replaced with injected dependencies.
- **FR-005**: Tests currently using `monkeypatch.setattr(module, "svc", mock)` MUST be updated to use `app.dependency_overrides` instead.
- **FR-006**: The workbench (`AnvilWorkbench`) remains the primary DI entry point; individual service dependencies are provided as convenience shortcuts for routes that only need one service.

### Key Entities

- **get_training_service**: New dependency function in `deps.py`
- **get_tracking_service**: New dependency function in `deps.py`
- **get_inference_service**: New dependency function in `deps.py`
- **AnvilWorkbench**: Existing god class (may be used to obtain these services)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero module-level service instantiations in any `anvil/api/v1/` route file.
- **SC-002**: All tests use `app.dependency_overrides` instead of `monkeypatch` for service mocking in route tests.
- **SC-003**: `make test` passes with zero changes to service-layer tests.
- **SC-004**: No new mypy --strict errors.

## Assumptions

- Service dependency functions will be thin wrappers that delegate to `AnvilWorkbench` properties.
- The request-scoped lifecycle through `AnvilWorkbench` (which is already request-scoped via `get_workbench`) is sufficient.
- Stateless services like `TrainingService` can be created once per workbench instance (not per-request if pure stateless).
