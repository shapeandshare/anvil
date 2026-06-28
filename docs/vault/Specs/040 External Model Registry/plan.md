# Implementation Plan: 040 External Model Registry & Import Paradigm

**Branch**: `040-external-model-registry` | **Date**: 2026-06-28 | **Spec**: [[040 External Model Registry - spec]]
**Input**: Feature specification from `docs/vault/Specs/040 External Model Registry/`

## Summary

A source-agnostic `ModelSource` abstraction (HF Hub first, local-file second) that lets learners
import external models into anvil as tracked metadata entries — created before any weight download.
Import is async job-based, surfaced via CLI (`anvil import`), REST API (`POST /v1/models/import`),
and Python SDK (`client.import_model(...)`). Registry entries are distinguishable by origin alongside
anvil's native models, with typed error codes and idempotent same-revision re-import.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `huggingface_hub` (behind `[finetune]` extra for HF source); existing
  FastAPI, async SQLAlchemy + aiosqlite, Pydantic, httpx (stdlib for CLI)
**Storage**: SQLite (anvil-state.db, WAL mode) via async SQLAlchemy + existing Alembic migrations;
  external model entries co-located in the same registry schema (extending spec 003)
**Testing**: pytest + pytest-asyncio (existing convention); unit tests per domain sub-package,
  e2e HTTP tests via `httpx.AsyncClient`
**Target Platform**: Linux / macOS POSIX server
**Project Type**: CLI + REST API + Python SDK (web service package with CLI frontend)
**Performance Goals**: HF Hub metadata resolution completes in <5s for typical model cards;
  local-file import near-instant. Registry queries <100ms
**Constraints**: NMRG — base (`pip install anvil`) MUST NOT import `huggingface_hub`;
  `[finetune]` extra required for HF source; existing from-scratch training path unchanged;
  all new modules — no existing paths modified
**Scale/Scope**: Tens to hundreds of external model metadata entries per instance;
  each entry is ~1 KB of structured metadata

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Applicable articles and constraints**:

- **Article I (Zero-Dependency Core)** — Core engine (`anvil/core/`) must remain stdlib only.
  Compliance: `huggingface_hub` is behind `[finetune]` extra, never imported from core path.
- **Article IV (TDD Mandatory)** — Tests before implementation; coverage ratcheting.
  Compliance: Unit and e2e tests required for all new modules.
- **Article V (Async-First)** — Web, DB, service layers async.
  Compliance: Import service and repository use async SQLAlchemy; import job is async.
- **Article VI (init.py Ownership)** — Bare `__init__.py` for new authoritative packages.
  Compliance: If a new domain sub-package is created (e.g., `anvil/services/import/`), it needs a
  docstring-only `__init__.py`.
- **Article VII (Layered Architecture)** — Repository → Service → God Class → Routes/CLI.
  Compliance: `ExternalModelRepository` → `ImportService` → `AnvilWorkbench` → CLI/API/SDK.
- **Article X (Domain-Driven Decomposition)** — Domain boundaries, max 2 nesting levels.
  Compliance: Evaluate whether an `import/` domain sub-package under `anvil/services/` is warranted
  vs extending an existing service. Models co-locate with the service or in `_shared/` if cross-domain.
- **Article XI (Simplicity First / Boring Technology)** — Hard MUST gate.
  See checklist below.
- **Additional Constraints**:
  - No type-error suppression (`mypy --strict`)
  - Pydantic `BaseModel` over `dataclasses.dataclass`
  - One class per file
  - Lean dependencies — only `huggingface_hub` as new dependency (behind extra)
  - Alembic migration for schema changes
  - UI compliance (`docs/ux-rules.md`) — not applicable (no UI in this spec)
  - ADR for significant decisions

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors
the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — the chosen approach is the simplest that
      satisfies the requirement; any added complexity has a concrete, present
      justification (not a hypothetical future one).
- [x] **Boring over novel** (§11.2) — no novel/experimental dependency,
      framework, or pattern is introduced where a simpler proven alternative
      exists; any such choice is recorded in Complexity Tracking below.
- [x] **YAGNI** (§11.3) — no speculative generality, premature abstraction, or
      config knobs without a present consumer.
- [x] **Reuse first** (§11.4) — existing libraries/patterns/abstractions are
      reused before introducing new ones.
- [x] **Testable** (§11.6) — the approach is demonstrably testable; untested or
      untestable paths are not treated as complete (pairs with Article IV TDD).

> Any deviation from the simplest viable solution MUST be recorded in the
> Complexity Tracking table below (§11.5), or this gate fails.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# New files
anvil/db/models/external_model.py          # ExternalModel ORM entity
anvil/db/repositories/external_models.py   # ExternalModelRepository
anvil/services/import/
├── __init__.py                            # Bare docstring-only
├── import_service.py                      # ImportService — orchestration
├── model_source.py                        # ModelSource Protocol
├── hf_source.py                           # HF Hub ModelSource impl
└── local_source.py                        # Local file ModelSource impl
anvil/services/_shared/import_types.py     # ModelMetadata, ModelSourceError (Pydantic)
anvil/api/v1/models.py                     # API routes (/v1/models/...)
anvil/client/models/
├── __init__.py
├── models_client.py                       # ModelsClient domain aggregator
├── models_import_command.py               # ModelsImportCommand
├── models_get_status_command.py           # ModelsGetStatusCommand
└── models_get_command.py                  # ModelsGetCommand

# Modified files
pyproject.toml              # Add anvil-import entry point
anvil/workbench.py          # Wire ImportService + ExternalModelRepository
anvil/cli.py                # Add import_main() + import_status_main()
anvil/api/v1/router.py      # Register models_router
anvil/client/anvil_client.py # Add models property
anvil/_resources/migrations/versions/  # Add 005_add_external_models.py

tests/
├── unit/
│   ├── db/
│   │   └── test_external_model_repo.py
│   ├── services/
│   │   ├── test_import_service.py
│   │   ├── test_hf_source.py
│   │   └── test_local_source.py
│   └── api/
│       └── test_models_routes.py
└── e2e/
    └── test_external_models.py
```

**Structure Decision**: Single project (existing monorepo layout). New `import/` domain sub-package
under `anvil/services/` per Article X. New `models/` domain sub-package under `anvil/client/` per
existing SDK client convention. ORM model and repository follow existing patterns in
`anvil/db/models/` and `anvil/db/repositories/`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
