---
title: MLflow Model Registry as Model Catalog Source of Truth
type: decision
tags:
  - type/decision
  - domain/registry
  - domain/architecture
  - domain/mlops
created: '2026-07-03'
updated: '2026-07-03'
aliases:
  - ADR-046
  - MLflow Model Catalog
source: agent
code-refs:
  - anvil/services/tracking/tracking.py
  - anvil/services/model_import/model_import_service.py
  - anvil/services/model_import/model_asset_service.py
  - anvil/db/models/external_model.py
  - anvil/db/models/lora_adapter.py
  - anvil/workbench.py
---
# ADR-046: MLflow Model Registry as Model Catalog Source of Truth

## Status

Accepted

## Context

Anvil maintains **two parallel model tracks** with no shared catalog:

1. **Trained models** — registered in the MLflow Model Registry via
   `TrackingService.register_source_model()` after training completes
   (per [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016]], which already
   made MLflow the source of truth for experiments and trained-model
   registry state).
2. **External models** (HuggingFace imports, spec 040) — stored in the
   SQLite `external_models` table with zero MLflow integration.

This split causes concrete user-facing defects and structural debt:

- The inference page model picker lists only MLflow-registered models —
  imported HF models (e.g. TinyLlama) are invisible even when fully
  downloaded and runnable.
- Every surface that lists models (Models page, inference picker, eval
  pickers) must query two stores with two different shapes, or silently
  miss one track.
- `external_models.id` is the relational anchor for `lora_adapters`,
  `model_assets`, `asset_download_jobs`, `model_import_jobs`, and
  `evaluation_runs` — while eval MLflow runs *already* tag
  `anvil.base_model_ref` with these same SQLite PKs (spec 054), creating
  a cross-store identity scheme tied to one workspace's database.
- The SaaS trajectory ([[Decisions/ADR-030-saas-architecture|ADR-030]],
  specs 042/047: hosted MLflow via `ANVIL_MLFLOW_URI`, LakeFS asset
  store) makes workspace-local SQLite PKs a poor long-term model
  identity.
- Additional import providers beyond HuggingFace are planned; the
  catalog schema must be provider-neutral.

Strategic requirements driving this decision: (1) long-term
maintainability, (2) clean transition to SaaS when ready, (3) support
for import providers beyond HuggingFace.

**Scope note (greenfield)**: per
[[Decisions/ADR-032-greenfield-legacy-removal|ADR-032]], this change
ships with **no legacy support, no data migration, and no transitional
dual-write states**. All instances are new after this change.

## Decision

**The MLflow Model Registry becomes the single source of truth for the
model catalog — identity, versions, searchable metadata, and lineage —
for ALL model kinds (trained, external, merged). SQLite retains only
operational and relational workflow state, which references catalog
entries by `ModelRef` instead of a local foreign key.**

### Boundary split

| Concern | Owner |
|---------|-------|
| Model identity, versions, metadata, lineage | MLflow Model Registry |
| Import jobs, download jobs, per-file asset state | SQLite (operational) |
| Eval records, adapter records | SQLite, referencing catalog via `ModelRef` |
| Weights / artifacts | `LocalFileStore` locally; LakeFS in SaaS (specs 042/047) |

### What is added

| Component | Purpose |
|-----------|---------|
| `ModelCatalogService` (new domain sub-package) | MLflow-backed registry CRUD + search. `TrackingService` stays focused on runs/metrics. |
| `ModelRef` value object | Canonical model reference: `(registered_model_name, version)`. Used everywhere a model is referenced. |
| Registry tag schema | `anvil.kind` (`trained\|external\|merged\|adapter`), `anvil.source_type`, `anvil.source_identifier`, `anvil.revision_sha`, `anvil.architecture_family`, `anvil.tokenizer_family`, `anvil.license`, `anvil.runnable_status`. Narrow and searchable — bulky `config_json` and file manifests are logged as artifacts, not tags. |
| Dedup guard in SQLite import-job layer | Transactional uniqueness on `(source_type, source_identifier, revision_sha)`. MLflow search is a read path, never the lock (the registry has no transactions). |

### What is removed

| Component | Replacement |
|-----------|-------------|
| `external_models` table + `ExternalModel` ORM class | MLflow registered models/versions with `anvil.kind=external` tags |
| `ExternalModelRepository` | `ModelCatalogService` (registry queries) |
| `external_model_id` FK columns on `lora_adapters`, `model_assets`, `asset_download_jobs`, `model_import_jobs`, `evaluation_runs` | `ModelRef` string columns (`registry_model_name`, `registry_model_version`) |
| Dual-track listing endpoints (`GET /v1/models/external` vs `GET /v1/registry/models`) | Single unified catalog listing |

### Import flow (target state)

1. `ModelImportService` resolves metadata via the existing `ModelSource`
   protocol (provider-neutral; HF and local today, more later).
2. Dedup check against the SQLite uniqueness guard.
3. Model is registered in MLflow with the tag schema; the registry entry
   *is* the model. Import job reaches `COMPLETE` only after registration
   succeeds.
4. Asset downloads track per-file state in SQLite keyed by `ModelRef`;
   `asset_availability` lives as a mutable registry tag.

### Delete semantics

The catalog is **append-only**. Cross-store CASCADE is replaced by
policy: "delete" archives the registry entry (tag) and runs explicit
asset cleanup. Registry names are never renamed; entries are never
hard-deleted by the app.

## Consequences

**Easier:**

- One catalog, one reference type (`ModelRef`), one listing path — the
  "models not showing up in the inference page" class of bug is
  structurally eliminated.
- SaaS transition: point `ANVIL_MLFLOW_URI` at hosted MLflow and the
  catalog moves with it; no workspace-local PK remapping.
- Provider extensibility: new import providers are a `ModelSource`
  implementation + `SourceType` member; the catalog schema is already
  provider-neutral.
- No mirror/sync code, no drift reconciliation — consistent with
  [[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041]]
  (one boring source of truth beats two synchronized stores).
- Extends ADR-016's principle (MLflow owns experiment/model registry
  state) to cover external models — removing the last dual-catalog
  exception.

**Harder:**

- **MLflow becomes a hard dependency for catalog features.** Import,
  model listing, and model selection fail closed when MLflow is down.
  Degraded mode narrows from "tracking disabled, everything else works"
  to "tracking + catalog disabled". Accepted because MLflow ships as a
  supervised sidecar locally and managed MLflow provides HA in SaaS. No
  read-through cache is added now (a cache is a second source of truth;
  add a last-known-good cache only if offline catalog reads become a
  hard requirement).
- Referential integrity across stores is by convention (append-only +
  archive policy), not by FK/CASCADE. Orphan detection moves to an
  explicit reconciliation check rather than schema guarantees.
- Tag-filter search (`search_model_versions`) is slower and less
  expressive than SQL — mitigated by keeping the tag schema narrow and
  the dedup/identity guard in SQLite.

**Explicitly preserved:**

- `model_import_jobs`, `asset_download_jobs`, `model_assets` — genuine
  transactional workflow state (progress bytes, per-file SHA-256, state
  machines with revert-on-failure) that a tag store cannot model.
- `lora_adapters`, `evaluation_runs` — durable business records; they
  point at the catalog, they are not the catalog.
- `ModelSource` protocol and `SourceType` enum — unchanged.

## Compliance

1. `grep -r 'ExternalModelRepository' anvil/` returns zero results.
2. `grep -r 'external_model_id' anvil/` returns zero results (replaced
   by `ModelRef` columns).
3. `external_models` table absent from the schema (no ORM model, no
   Alembic table).
4. Importing a model creates an MLflow registered model version tagged
   `anvil.kind=external` with the full tag schema; the import job is
   `COMPLETE` only after registration.
5. The inference page model picker and the Models page list trained,
   external, and merged models from the single catalog.
6. Concurrent duplicate imports of the same
   `(source_type, source_identifier, revision_sha)` triple produce
   exactly one registry entry (SQLite uniqueness guard).
7. Deleting a model archives the registry entry and removes local
   assets; no hard delete of registry entities.
8. `make test` passes with the unified catalog; e2e tests cover list,
   import, play, and eval flows against the single catalog.

## See Also

- [[Decisions/README|Decisions]]
- [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016]] — MLflow as
  primary lineage source of truth (trained models/experiments)
- [[Decisions/ADR-030-saas-architecture|ADR-030]] — SaaS three-mode
  operating model
- [[Decisions/ADR-032-greenfield-legacy-removal|ADR-032]] — Greenfield
  legacy removal (no migration mandate)
- [[Decisions/ADR-033-content-repository-substrate|ADR-033]] — LakeFS
  substrate for SaaS assets
- [[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041]] —
  Simplicity First (Boring Technology)
- [[Decisions/ADR-043-warm-start-vocabulary-inheritance|ADR-043]] —
  Warm-start MLflow tag lineage
