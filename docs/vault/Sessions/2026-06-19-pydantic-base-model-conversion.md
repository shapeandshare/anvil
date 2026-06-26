---
title: 'Session: Pydantic BaseModel Conversion'
type: session-log
tags:
  - type/session-log
  - domain/governance
  - domain/architecture
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - 'Session: Pydantic BaseModel Conversion'
  - BaseModel Preference Session
source: agent
code-refs:
  - constitution.md
  - shared/python.mk
  - anvil/gpu.py
  - anvil/services/compute/result.py
  - anvil/services/demo_bootstrap.py
  - anvil/services/memory_estimator.py
  - anvil/services/mlflow_capabilities.py
  - anvil/_resources/migrations/scripts/migrate_to_mlflow_primary.py
  - Decisions/ADR-019-pydantic-basemodel-over-dataclass.md
---
# Session: Pydantic BaseModel Conversion

**Date**: 2026-06-19
**Trigger**: User request: "Add Pydantic BaseModel preference over dataclasses.dataclass"

## Problem

The codebase had a split personality — `BaseModel` used in API routes, `@dataclass` used in 6 service/utility files, with no clear rule about which to use for new code. The rule existed only informally in `AGENTS.md` (line 86) with no enforcement or constitutional backing.

## Decision

Three layers of action:

1. **Constitution**: Added "Pydantic `BaseModel` MUST be used for all structured data/value-object classes over `dataclasses.dataclass`" as an Additional Constraint.
2. **Migration**: Converted all 6 `@dataclass` classes to Pydantic `BaseModel`:
   - `anvil/gpu.py:GpuInfo`
   - `anvil/services/compute/result.py:ComputeResult`
   - `anvil/services/demo_bootstrap.py:BootstrapResult`
   - `anvil/services/memory_estimator.py:MemoryEstimate`
   - `anvil/services/mlflow_capabilities.py:TrackingCapabilities`
   - `anvil/_resources/migrations/scripts/migrate_to_mlflow_primary.py:MigrationReport`
3. **Enforcement**: Added a grep-based `@dataclass` detection check to `make lint` in `shared/python.mk`.

Key conversion pattern: `dataclasses.dataclass` + `field(default_factory=...)` → `pydantic.BaseModel` + `Field(default_factory=...)`.

## ADR

- **ADR-019**: Pydantic BaseModel Over dataclasses.dataclass — records the context, decision, and compliance mechanism.

## Validation

- `lsp_diagnostics` on all 6 changed files: zero new errors (all pre-existing optional-dependency warnings)
- `black --check` + `isort --check`: all 6 files pass
- `ruff check` on changed files: zero new violations (all errors pre-existing)
- `make lint` dataclass grep check: zero `@dataclass` usages found

## Related

- [[Decisions/ADR-019-pydantic-basemodel-over-dataclass|ADR-019: Pydantic BaseModel Over dataclasses.dataclass]] — architecture decision record
- [[Code/Code|Code]] — code architecture conventions and patterns
- [[Governance/Constitution|Constitution]] — project governance and conventions

## Tags
- type/session-log
- domain/governance
- domain/architecture
- status/reviewed
