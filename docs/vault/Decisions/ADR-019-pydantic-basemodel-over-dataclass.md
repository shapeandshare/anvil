---
title: 'ADR-019: Pydantic BaseModel Over dataclasses.dataclass'
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/architecture
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - 'ADR-019: Pydantic BaseModel Over dataclasses.dataclass'
  - ADR-019
  - BaseModel Preference
source: agent
code-refs:
  - anvil/gpu.py
  - anvil/services/compute/result.py
  - anvil/services/demo_bootstrap.py
  - anvil/services/memory_estimator.py
  - anvil/services/mlflow_capabilities.py
  - anvil/_resources/migrations/scripts/migrate_to_mlflow_primary.py
  - constitution.md
  - shared/python.mk
---
# ADR-019: Pydantic BaseModel Over dataclasses.dataclass

## Status

Accepted

## Context

The anvil codebase used a mix of `dataclasses.dataclass` and Pydantic `BaseModel` for structured data / value-object classes:

- `BaseModel` was used in 2 files: `storage/interface.py` (FileInfo) and `api/v1/datasets.py` (8 request/response bodies).
- `@dataclass` was used in 6 files: `gpu.py`, `services/compute/result.py`, `services/demo_bootstrap.py`, `services/memory_estimator.py`, `services/mlflow_capabilities.py`, and `_resources/migrations/scripts/migrate_to_mlflow_primary.py`.

Pydantic was already a hard dependency of the project (pinned at `>=2.0,<3` in `pyproject.toml`) — required by FastAPI and already used in the API routes layer.

Using `@dataclass` alongside `BaseModel` created inconsistency:
- `BaseModel` provides serialization (`model_dump()`, `model_dump_json()`) and validation out of the box; `@dataclass` requires manual `to_dict()` methods (e.g., `MemoryEstimate.to_dict()`).
- API layer already uses `BaseModel` for request/response bodies — service-layer dataclasses that flow into those bodies need manual conversion.
- New contributors face an unnecessary "which one do I use?" choice.

## Decision

1. **Constitution amendment**: Added a new Additional Constraint: "Pydantic `BaseModel` MUST be used for all structured data/value-object classes over `dataclasses.dataclass`."
2. **Migration**: All 6 existing `@dataclass` classes were converted to Pydantic `BaseModel`:
   - `GpuInfo` — GPU detection result value object
   - `TrackingCapabilities` — MLflow capability flags
   - `MemoryEstimate` — Memory computation result with properties + `to_dict()`
   - `BootstrapResult` — Demo bootstrap outcome
   - `ComputeResult` — Unified compute backend result value object
   - `MigrationReport` — One-shot migration script report
3. **Enforcement**: Added a grep-based check to `make lint` that rejects any `@dataclass` decorator usage in `anvil/`, with a clear error message directing developers to the constitution.

Key conversion patterns:
- `from dataclasses import dataclass, field` → `from pydantic import BaseModel, Field`
- `@dataclass` → `class X(BaseModel):`
- `field(default_factory=list)` → `Field(default_factory=list)`
- `field(default_factory=dict)` → `Field(default_factory=dict)`

## Consequences

**Easier**:
- Consistent data class pattern across the entire codebase.
- No manual `to_dict()` / serialization needed — `model_dump()` works automatically.
- `ComputeResult` flows directly into API responses without conversion.
- New contributors have a single choice: "use `BaseModel`."
- `model_dump_json()`, `model_copy()`, and validators available everywhere.

**Harder**:
- Core engine (`anvil/core/`) remains stdlib-only; `@dataclass` is still the right choice there (zero dependencies). This is not affected — core had no `@dataclass` usage anyway.
- One-off scripts that don't import from the project (unlikely) might prefer `@dataclass` for zero-dependency. The grep check only covers `anvil/`.

## Compliance

Verified by:
1. `make lint` — the `@dataclass` grep check exits non-zero if any `@dataclass` decorator appears in `anvil/`.
2. All 6 migrated files pass `black --check`, `isort --check`, and have zero new `ruff` errors.
3. Code review: new PRs must use `BaseModel` for structured data.
