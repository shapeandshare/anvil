# Feature Specification: Inject Cross-Service Dependencies via Constructors

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P1  
**Input**: Codebase review finding #071 — Multiple services create other services directly inside methods instead of receiving them via constructor injection: `TrainingService` creates `DatasetService`/`CorpusService`/`DemoBootstrapService` inline; `InferenceService` creates `TrackingService()` directly; `TrainingRunService` creates `InferenceService()` directly.

## User Scenarios & Testing

### User Story 1 - Services declare all dependencies in constructor (Priority: P1)

Every service's `__init__` signature lists all its service-level dependencies. No service creates another service internally.

**Why this priority**: Hidden dependency creation makes the dependency graph invisible. It's impossible to know what a service needs without reading every line of its code. Constructor injection makes dependencies explicit, testable, and mockable.

**Independent Test**: A test can create a service by passing mock dependencies in the constructor and verify each dependency is used.

**Acceptance Scenarios**:

1. **Given** `TrainingService.__init__`, **When** inspected, **Then** it accepts `DatasetService`, `CorpusService`, and `DemoBootstrapService` as optional keyword arguments (defaulting to creating them if not provided, or requiring them).
2. **Given** `InferenceService.__init__`, **When** inspected, **Then** it accepts `TrackingService` as an optional parameter.
3. **Given** `TrainingRunService.__init__`, **When** inspected, **Then** it accepts `InferenceService` as an optional parameter.
4. **Given** a service is created with explicit dependencies, **When** a method uses that dependency, **Then** it uses the injected instance, not a freshly created one.

---

### User Story 2 - AnvilWorkbench wires all dependencies (Priority: P2)

The `AnvilWorkbench` god class is the single place where service dependency graphs are constructed.

**Why this priority**: Centralized wiring prevents scattered dependency creation logic and makes the service graph visible in one place.

**Independent Test**: Creating an `AnvilWorkbench` creates all services with their transitive dependencies wired automatically.

**Acceptance Scenarios**:

1. **Given** `AnvilWorkbench.training`, **When** first accessed, **Then** it creates `TrainingService` with all injected dependencies (including `DatasetService`, `CorpusService`, etc.).
2. **Given** `AnvilWorkbench.inference`, **When** first accessed, **Then** it creates `InferenceService` with `TrackingService` injected.

### Edge Cases

- What about `InferenceService` having no constructor parameters currently? Adding optional params with defaults preserves backward compatibility.
- What about cyclic dependencies? The layered architecture (Article VII) should prevent cycles — if one emerges, it indicates a design problem.

## Requirements

### Functional Requirements

- **FR-001**: `TrainingService.__init__` MUST accept `DatasetService | None`, `CorpusService | None`, and `DemoBootstrapService | None` as keyword arguments with `None` defaults that create instances lazily.
- **FR-002**: `InferenceService.__init__` MUST accept `TrackingService | None` as a keyword argument.
- **FR-003**: `TrainingRunService.__init__` MUST accept `InferenceService | None` as a keyword argument.
- **FR-004**: All inline creation of services inside methods (`_load_docs`, `_validate_warm_start`, `_load_trained`, `load_model`) MUST be replaced with usage of the injected instance.
- **FR-005**: `AnvilWorkbench` property accessors MUST pass all known service dependencies when creating services.
- **FR-006**: Backward compatibility MUST be preserved — callers that do not pass the new params should get working defaults (current behavior).
- **FR-007**: Tests MUST be able to inject mock services via constructor parameters.

### Key Entities

- **TrainingService**: Receives DatasetService, CorpusService, DemoBootstrapService
- **InferenceService**: Receives TrackingService
- **TrainingRunService**: Receives InferenceService
- **AnvilWorkbench**: Wires all dependencies centrally

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero instances of services creating other services internally (search for `ServiceClass(` inside service modules).
- **SC-002**: All service constructors explicitly declare their service dependencies.
- **SC-003**: `AnvilWorkbench` is the single source of truth for the service dependency graph.
- **SC-004**: `make test` and `make typecheck` pass with zero new errors.

## Assumptions

- Backward-compatible defaults (the `None`-creates-internal pattern) allow incremental migration without breaking existing callers.
- No circular dependencies exist that would prevent constructor injection (the layered architecture should prevent this).
