---
title: 064 MLflow Model Catalog - Plan
type: spec
tags:
  - type/spec
created: 2026-07-03
updated: 2026-07-03
---

# Implementation Plan: Unified MLflow Model Catalog

**Branch**: `062-mlflow-model-catalog` | **Date**: 2026-07-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `docs/vault/Specs/064 MLflow Model Catalog/spec.md`

## Summary

Make the MLflow Model Registry the single source of truth for the model
catalog (identity, versions, metadata, lineage) for ALL model kinds —
trained, external (HF/local imports), and merged — per ADR-048. A new
`ModelCatalogService` (MLflow-backed, following `TrackingService`'s
lazy-init/executor conventions but **fail-closed** instead of silently
degrading) owns registry CRUD and search. A `ModelRef` value object
(`registered_model_name` + `version`) replaces `external_model_id` FKs in
all operational tables. External-model import registers the model via a
lightweight MLflow "import run" (required — MLflow servers reject
local-path sources without a `run_id`; verified against MLflow 3.x
server validation). Weights stay in `LocalFileStore` keyed by ModelRef;
the registry stores metadata + a tiny config manifest, never weights.
Greenfield: `external_models` table, ORM, and repository are deleted
outright — no migration, no dual-write (ADR-032).

## Technical Context

**Language/Version**: Python 3.11+ (PEP 604 unions, `StrEnum`, `from __future__ import annotations`)
**Primary Dependencies**: FastAPI, async SQLAlchemy + aiosqlite, Alembic, Jinja2, `mlflow>=3` client (all existing — **no new runtime dependencies**)
**Storage**: MLflow Model Registry (catalog SoT; sidecar server, SQLite backend at `mlruns/mlflow.db`); SQLite `anvil-state.db` (WAL) for operational state (jobs, per-file assets, adapters, evals, dedup guard); `LocalFileStore` for weights at `data/models/{catalog_name}/{version}/hf/`
**Testing**: pytest + pytest-asyncio; unit tests in `tests/unit/`, e2e HTTP tests in `tests/e2e/` via the `client` fixture; TDD Red-Green-Refactor mandatory (Article IV)
**Target Platform**: macOS/Linux local workbench; SaaS-ready (hosted MLflow via `ANVIL_MLFLOW_URI`, LakeFS assets per specs 042/047)
**Project Type**: Web service (FastAPI + Jinja2) — layered Repository → Service → `AnvilWorkbench` → Routes
**Performance Goals**: Catalog listing of ≤100 logical models renders < 2 s on a local instance (SC-008) — forces elimination of the current per-model N+1 enrichment pattern
**Constraints**: Fail-closed catalog (FR-009: 503 + explicit unavailability when MLflow down — deliberate contrast with TrackingService's silent degrade); append-only catalog (archive tag, no renames/hard deletes); transactional dedup guard in SQLite (never catalog search as lock); provider-neutral (`ModelSource` protocol unchanged)
**Scale/Scope**: Single-user local instance, dozens of models typical, 100 tested ceiling; ~6 services touched, 5 operational tables re-keyed, 1 table deleted, 3 listing endpoints unified

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Gate | Status |
|---------|------|--------|
| I — Zero-Dependency Core | `anvil/core/` untouched | ✅ PASS — no core changes |
| III — Seeded Reproducibility | No training-path changes | ✅ PASS |
| IV — TDD Mandatory | Red-Green-Refactor per task; coverage ratchet holds | ✅ PASS — plan mandates failing tests first for every unit |
| V — Async-First | New service async; MLflow client calls via `run_in_executor` (existing convention) | ✅ PASS |
| VI — `__init__.py` Ownership | New `anvil/services/catalog/` gets bare docstring-only `__init__.py` | ✅ PASS |
| VII — Layered Architecture | `CatalogIdentityRepository` (DB only) → `ModelCatalogService` → `AnvilWorkbench.catalog` → routes | ✅ PASS |
| X — Domain Decomposition | New `catalog/` domain sub-package; `ModelRef`/errors co-located (§10.2); plural noun naming (§10.4) | ✅ PASS |
| XI — Simplicity First | See gate below | ✅ PASS |
| Pydantic over dataclass | `ModelRef`, `CatalogEntry` are `BaseModel` | ✅ PASS |
| One class per file | One class per new file; tightly-coupled error may share (permitted) | ✅ PASS |
| Alembic reversible migrations | Single new revision (greenfield schema change) | ✅ PASS |

**Simplicity First gate (Article XI — hard MUST)**:

- [x] **Simplest viable** (§11.1) — one catalog replaces two synchronized
      stores; the import-run registration pattern is the simplest approach
      the MLflow server *permits* (direct local-path source is blocked by
      server-side validation — verified, see research.md D1).
- [x] **Boring over novel** (§11.2) — reuses the existing `mlflow` client,
      the existing `AdapterMergeService._register_lineage()` import-run
      pattern, and `TrackingService`'s executor/lazy-init conventions. No
      new dependency, framework, or experimental pattern.
- [x] **YAGNI** (§11.3) — no read-through cache (added only if offline
      catalog reads become a requirement — recorded in ADR-048); no
      adapter catalog entries (deferred to Spec 065); no multi-tenant
      naming machinery.
- [x] **Reuse first** (§11.4) — `ModelSource` protocol, `LocalFileStore`,
      Alembic, existing tag conventions (`anvil.*`) all reused.
- [x] **Testable** (§11.6) — every decision has a test hook: dedup via
      concurrent-import test, fail-closed via stopped-sidecar e2e test,
      SC-008 via seeded 100-model listing test.

> No deviations from the simplest viable solution → Complexity Tracking
> table is empty.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/064 MLflow Model Catalog/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── catalog-api.md   # Phase 1 output — unified catalog HTTP contract
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
anvil/
├── services/
│   ├── catalog/                      # NEW domain sub-package
│   │   ├── __init__.py               #   bare, docstring-only (Article VI)
│   │   ├── model_catalog_service.py  #   MLflow-backed catalog CRUD/search
│   │   ├── model_ref.py              #   ModelRef value object (BaseModel)
│   │   ├── catalog_entry.py          #   CatalogEntry DTO (BaseModel)
│   │   ├── catalog_kind.py           #   CatalogKind StrEnum (trained|external|merged|adapter)
│   │   ├── lifecycle_state.py        #   LifecycleState StrEnum (active|archived)
│   │   └── catalog_unavailable_error.py  # fail-closed exception
│   ├── model_import/
│   │   ├── model_import_service.py   # MODIFIED — registers via catalog; no ExternalModel row
│   │   └── model_asset_service.py    # MODIFIED — keyed by ModelRef; updates availability tag
│   ├── inference/
│   │   └── inference.py              # MODIFIED — load_model routes on anvil.kind; ModelRef-aware
│   ├── evaluation/
│   │   └── evaluation_service.py     # MODIFIED — ModelRef references
│   ├── training/
│   │   ├── training_run_service.py   # MODIFIED — registration adds kind/loss tags for listing
│   │   └── merge_service.py          # MODIFIED — merged entries carry kind=merged tags
│   └── _shared/                      # RunnableStatus/AssetState enums (reused as tag values)
├── db/
│   ├── models/
│   │   ├── external_model.py         # DELETED
│   │   ├── catalog_identity.py       # NEW — dedup guard + triple→ModelRef resolution
│   │   ├── model_import_job.py       # MODIFIED — ModelRef columns
│   │   ├── asset_download_job.py     # MODIFIED — ModelRef columns
│   │   ├── model_asset.py            # MODIFIED — ModelRef columns
│   │   ├── lora_adapter.py           # MODIFIED — ModelRef columns
│   │   └── (evaluation_runs model)   # MODIFIED — ModelRef columns
│   └── repositories/
│       ├── external_models.py        # DELETED
│       └── catalog_identities.py     # NEW — transactional dedup guard
├── api/v1/
│   ├── models.py                     # MODIFIED — unified GET /v1/models; import/download re-keyed
│   ├── registry.py                   # MODIFIED — reads via ModelCatalogService
│   ├── learning.py                   # MODIFIED — /inference/models reads unified catalog
│   ├── eval.py / pages.py            # MODIFIED — external_model_repo usages removed
│   └── (503 catalog-unavailable handling)
├── workbench.py                      # MODIFIED — .catalog property; external_model_repo removed
└── migrations/                       # NEW Alembic revision

tests/
├── unit/services/catalog/            # NEW — ModelRef, name derivation, service (mocked client)
├── unit/db/                          # NEW — CatalogIdentityRepository dedup guard
└── e2e/                              # MODIFIED/NEW — unified listing, import→catalog, fail-closed 503,
                                      #   archive semantics, SC-008 seeded listing perf
```

**Structure Decision**: Single web-service project (existing layout). New
`catalog/` domain sub-package under `anvil/services/` per Article X;
result/value types co-locate with the service (§10.2). DB changes follow
the existing `db/models` + `db/repositories` split (Article VII).

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
