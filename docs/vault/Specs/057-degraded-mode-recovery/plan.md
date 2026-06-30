# Implementation Plan: Degraded Mode Recovery

**Branch**: `opencode/silent-wizard` | **Date**: 2026-06-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `docs/vault/Specs/057-degraded-mode-recovery/spec.md`

## Summary

Refactor the `TrackingService` degraded mode in `anvil/services/tracking/tracking.py` to address 7 issues: add automatic recovery from transient MLflow outages (exponential backoff with jitter), strengthen user visibility of degraded state (health endpoint + UI indicators), narrow exception handling to known MLflow exceptions, decouple the empty-run_id guard from the degraded gate, differentiate failure modes via an enum, and add thread-safe state mutation via `asyncio.Lock`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: mlflow (existing), sqlalchemy (existing), FastAPI/Starlette (existing)  
**Storage**: SQLite (anvil-state.db) — no schema changes needed  
**Testing**: pytest (existing) + asyncio test patterns  
**Target Platform**: macOS (Apple Silicon), Linux (x86_64) — existing  
**Project Type**: Web service (FastAPI) + pip-installable Python package  
**Performance Goals**: No new hot paths; retry backoff protects MLflow from thundering herd. Status check is a fast boolean read.  
**Constraints**: Must not break existing training/tracking behavior when MLflow is healthy. Must not introduce new runtime dependencies.  
**Scale/Scope**: Single-user to small-team deployments. One `TrackingService` instance per process.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**:

- [x] **Simplest viable** (§11.1) — each issue has a straightforward fix: `asyncio.Lock` for thread safety, exponential backoff for retry, targeted exception classes, enum for failure differentiation. No architecture changes.
- [x] **Boring over novel** (§11.2) — uses only existing patterns already in the codebase (`asyncio.Lock`, `StrEnum`, Pydantic `BaseModel`). No new dependencies.
- [x] **YAGNI** (§11.3) — no speculative features. Every change maps 1:1 to a concrete issue (Issues 1-7).
- [x] **Reuse first** (§11.4) — reuses existing `asyncio.Lock` pattern (already in `health_ops.py`), existing MLflow exception hierarchy, existing Jinja2 template system for UI indicators.
- [x] **Testable** (§11.6) — each fix is unit-testable via mocked MLflow client and integration-testable by toggling MLflow server reachability.

> No deviations from simplest viable — Complexity Tracking table is empty.

**Other constitution articles**:

- **Article V (Async-First)**: All new code MUST be async. Lock is `asyncio.Lock`, not `threading.Lock`. ✅
- **Article VII (Layered Architecture)**: Changes are confined to `TrackingService` (service layer) and the health endpoint route — no violation. ✅
- **Article IX (Pit of Success)**: Degraded mode IS the Pit of Success — tracking gracefully degrades rather than breaking training. Enhanced with recovery. ✅
- **Article IV (TDD Mandatory)**: Tests MUST be written before implementation per spec FR-007 through FR-012. ✅

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/057-degraded-mode-recovery/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 (created by /speckit.tasks)
```

### Source Code (repository root)

```text
# Single project — existing structure, no new files needed
anvil/services/tracking/
├── tracking.py                # TrackingService — primary change target
├── tracking_status.py         # NEW: DegradedState, DegradedReason, TrackingStatus entities
├── mlflow_capabilities.py     # Existing — no change
└── mlflow_inputs.py           # Existing — no change

anvil/api/v1/
├── health_ops.py              # Add tracking block to /v1/health/detailed response
├── training.py                # Update POST /v1/training response (keep "tracking":"degraded")
├── datasets.py                # No change needed (already gates on is_degraded)
└── corpora.py                 # No change needed (already gates on is_degraded)

anvil/api/templates/
├── archetypes/training.html   # UI degraded indicator on training page
├── experiments.html           # UI degraded indicator on experiments page
├── models.html                # UI degraded indicator on model registry page
└── operations.html            # UI degraded indicator on operations page

anvil/api/static/js/
└── widgets/experiment-tracking.js  # Already has degraded mode simulation widget

tests/
├── unit/services/
│   └── test_tracking_degraded.py  # NEW: comprehensive degraded mode tests
└── e2e/
    └── test_tracking_degraded.py  # NEW: end-to-end degraded mode tests
```

**Structure Decision**: Single project — all changes are within existing files or add new files to existing packages. No new package directories needed.
