---
title: 064 MLflow Model Catalog - Data Model
type: spec
tags:
  - type/spec
created: 2026-07-03
updated: 2026-07-03
---

# Data Model: Unified MLflow Model Catalog

**Feature**: 064 | **Date**: 2026-07-03 | **Sources**: spec.md Key Entities, research.md D3/D5/D10

## 1. Catalog Entry (MLflow Model Registry — source of truth)

A **logical model** = one MLflow *registered model*; each imported source
revision (or trained/merged registration) = one *model version* (spec
Clarification Q1).

### Registered model (per logical model)

| Field | Where | Values / Rules |
|---|---|---|
| `name` | registry name | Derived, immutable, URL-safe: external → `{prefix}--{sanitized_identifier}` (`hf--…`, `local--…`); trained → existing `dataset-{name}` / `corpus-{name}` / `demo`; merged → `adapter-merge-{adapter_id}`. Charset `[A-Za-z0-9._-]` (research D8) |
| `anvil.kind` | RM tag | `trained` \| `external` \| `merged` (`adapter` reserved for Spec 065) — `CatalogKind` StrEnum |
| `anvil.source_type` | RM tag | `SourceType` value (`huggingface` \| `local`); `internal` for trained/merged |
| `anvil.source_identifier` | RM tag | Raw provider identifier (e.g. `TinyLlama/TinyLlama-1.1B-Chat-v1.0`) |
| `anvil.display_name` | RM tag | Mutable human label — never identity (FR-013) |
| `anvil.lifecycle_state` | RM tag | `active` \| `archived` — `LifecycleState` StrEnum; archived when ALL versions archived |

### Model version (per revision / registration)

| Field | Where | Values / Rules |
|---|---|---|
| `version` | MLflow version int | Assigned by registry; ModelRef pins it |
| `source` / `run_id` | version fields | `runs:/{import_run_id}/` — import run holds the config manifest artifact only (research D1/D2) |
| `anvil.revision_sha` | MV tag | Provider revision (identity triple member); required (edge case: import fails if unresolvable) |
| `anvil.architecture_family` | MV tag | e.g. `LlamaForCausalLM` |
| `anvil.tokenizer_family` | MV tag | e.g. `sentencepiece`, `char` |
| `anvil.license` | MV tag | SPDX id |
| `anvil.parameter_count` | MV tag | int-as-string |
| `anvil.runnable_status` | MV tag | `RunnableStatus` value (`runnable` \| `track_only` \| `unavailable`) |
| `anvil.runnable_reason` | MV tag (optional) | Plain-text reason when not runnable |
| `anvil.asset_availability` | MV tag (MUTABLE) | `AssetState` value (`metadata_only` → `assets_pending` → `assets_available`); gates Play (FR-012) |
| `anvil.final_loss` | MV tag (trained/merged) | Written at registration → listing needs no `get_run` (research D4) |
| `anvil.lifecycle_state` | MV tag (MUTABLE) | `active` \| `archived` (research D6) |

**Mutation rules (FR-008)**: only `anvil.asset_availability`,
`anvil.lifecycle_state`, and `anvil.display_name` are ever mutated. No
renames. No `delete_registered_model` / `delete_model_version` calls.

**State transitions**:

```
asset_availability: metadata_only ──submit_download──▶ assets_pending ──all files ok──▶ assets_available
                          ▲                                   │ any failure
                          └───────────────(revert)────────────┘
lifecycle_state:    active ──delete──▶ archived   (terminal; no un-archive in this feature)
```

## 2. ModelRef (value object — Pydantic `BaseModel`)

`anvil/services/catalog/model_ref.py`

| Field | Type | Rules |
|---|---|---|
| `name` | `str` | Registry model name; pattern `^[A-Za-z0-9._-]+$` |
| `version` | `int` | ≥ 1 |

- Canonical string form `"{name}/{version}"` for logs; DB persistence is
  always the two-column pair (below). Immutable (`model_config frozen`).
- Replaces every `external_model_id` reference (FR-006).

## 3. CatalogEntry (read DTO — Pydantic `BaseModel`)

`anvil/services/catalog/catalog_entry.py` — the service's return shape
(one per model version, joined with registered-model tags): `ref:
ModelRef`, `kind: CatalogKind`, `display_name`, `source_type`,
`source_identifier`, `revision_sha`, `architecture_family`,
`tokenizer_family`, `license`, `parameter_count: int`,
`runnable_status: RunnableStatus`, `runnable_reason: str | None`,
`asset_availability: AssetState`, `final_loss: float | None`,
`lifecycle_state: LifecycleState`, `created_at: datetime`.

## 4. catalog_identities (NEW SQLite table — transactional dedup guard)

`anvil/db/models/catalog_identity.py` / repository
`anvil/db/repositories/catalog_identities.py` (research D5)

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `source_type` | VARCHAR(20) | NOT NULL |
| `source_identifier` | VARCHAR(255) | NOT NULL |
| `revision_sha` | VARCHAR(255) | NOT NULL |
| `registry_model_name` | VARCHAR(255) | NOT NULL |
| `registry_model_version` | INTEGER | NULL until registration completes |
| `created_at` / `updated_at` | DATETIME | TimestampMixin |

- **UNIQUE(source_type, source_identifier, revision_sha)** — the FR-005
  lock. Insert-first, register-second; rollback on registration failure.
- NOT a catalog mirror: no metadata columns, ever.

## 5. Re-keyed operational tables (MODIFIED)

Every `external_model_id: int FK` column is replaced by the pair
`registry_model_name: VARCHAR(255) NOT NULL` +
`registry_model_version: INTEGER NOT NULL`, composite-indexed
(research D10). No FK constraint to the (external) registry — integrity
by policy (append-only catalog, D6).

| Table | Old reference | Notes |
|---|---|---|
| `model_import_jobs` | `external_model_id` | Set on COMPLETE; job also carries the identity triple |
| `asset_download_jobs` | `external_model_id` | Cancelled/failed cleanly on model archive (edge case) |
| `model_assets` | `external_model_id` | Per-file sha256/size/progress unchanged; rows removed on archive |
| `lora_adapters` | `external_model_id` (FK CASCADE) | CASCADE removed; cleanup explicit in archive flow |
| `evaluation_runs` | `external_model_id`, `base_external_model_id` | → `model_name`/`model_version` + `base_model_name`/`base_model_version` |

## 6. Removed

- `external_models` table (Alembic drop in the feature revision)
- `anvil/db/models/external_model.py` (`ExternalModel` ORM)
- `anvil/db/repositories/external_models.py` (`ExternalModelRepository`)
- `AnvilWorkbench.external_model_repo` property (consumers at
  `workbench.py:570,611,723`; routes `eval.py:240`, `pages.py:383`,
  `models.py:135,304` re-wired to `ModelCatalogService` / ModelRef)

## 7. Validation rules (from FRs)

- Identity triple complete or import fails (FR + edge case: missing
  revision → clear error naming the field).
- Catalog name derivation total function: any identifier maps to valid
  charset; collisions impossible within a provider by construction; cross
  provider by prefix (FR-013, Q3).
- Import job may reach COMPLETE only after `create_model_version`
  succeeded AND `catalog_identities.registry_model_version` is set
  (FR-004).
- Listing surfaces exclude `lifecycle_state=archived` unless
  `include_archived=true` (US4).
- `runnable_status=runnable AND asset_availability=assets_available` ⟺
  Play enabled (FR-012) — single helper on `CatalogEntry`, reused by all
  surfaces.

## 8. Alembic

One reversible revision: create `catalog_identities`; drop
`external_models`; recreate re-keyed columns on the five operational
tables (SQLite batch-alter). Greenfield — no data copy (ADR-032).
