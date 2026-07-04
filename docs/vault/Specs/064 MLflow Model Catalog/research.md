---
title: 064 MLflow Model Catalog - Research
type: spec
tags:
  - type/spec
created: 2026-07-03
updated: 2026-07-03
---

# Research: Unified MLflow Model Catalog

**Feature**: 064 MLflow Model Catalog | **Date**: 2026-07-03
**Sources**: MLflow 3.x source-code verification (`mlflow/server/handlers.py`,
`mlflow/utils/uri.py`, `mlflow/store/artifact/local_artifact_repo.py`),
official MLflow Model Registry docs, codebase exploration (tracking,
model_import, inference, evaluation, workbench), Oracle architecture
consultation, ADR-048.

All NEEDS CLARIFICATION items from the Technical Context are resolved
below. No open unknowns remain.

---

## D1 — Registration mechanics: lightweight import run (REQUIRED by MLflow)

**Decision**: Register external models by creating a lightweight MLflow
"import run", logging a small config manifest as the run artifact, and
calling `create_model_version(name=<catalog_name>, source=f"runs:/{run_id}/", run_id=run_id)`.

**Rationale**: Direct registration from a local filesystem source without
a run is **blocked by the MLflow server**. Verified in MLflow 3.x source:
`_validate_source_run` (`mlflow/server/handlers.py:2867-2889`) rejects any
local URI (bare path or `file://`) unless `run_id` is provided AND the
source resolves inside that run's artifact directory — error: *"To use a
local path as a model version source, the run_id request parameter has to
be specified…"*. This hardening (CVE-2023-6014/6015/6018/6831 era, present
since ~2.10) is unconditional; the only env knob
(`MLFLOW_CREATE_MODEL_VERSION_SOURCE_VALIDATION_REGEX`) further
*restricts* sources, it cannot exempt local paths. The import-run pattern
is also the exact pattern the codebase already uses for merged adapters
(`AdapterMergeService._register_lineage()`, `merge_service.py:481`) —
reuse per Article XI §11.4.

**Alternatives considered**:
- *Direct local-path `source` without run* — rejected: blocked by server-side
  validation (verified, not speculative).
- *`MLFLOW_CREATE_MODEL_VERSION_SOURCE_VALIDATION_REGEX` override* —
  rejected: it cannot bypass the local-source/run check, and weakening
  registry validation is the wrong direction for SaaS.
- *`mlflow.transformers.log_model` with the weights directory* — rejected:
  `LocalArtifactRepository.log_artifacts` **copies** the full tree into
  `mlruns/` (`shutil_copytree_without_file_permissions`), duplicating
  multi-GB weights that already live in `LocalFileStore`; ADR-048 keeps
  weights out of the registry.

## D2 — Weights placement: FileStore, keyed by ModelRef; registry holds metadata only

**Decision**: Weights/config/tokenizer files live in `LocalFileStore` at
`models/{catalog_name}/{version}/hf/` (canonical HF layout per spec 063).
The import run's artifact is only the resolved `config.json` manifest
(KB-scale — satisfies FR-003 "retrievable documents"). The model
version's `source` points at the tiny run artifact dir, not at weights.

**Rationale**: The registry is a *catalog*, not an artifact server
(ADR-048 boundary split). Logging weights as run artifacts would copy
2 GB+ per model into `mlruns/` (verified: local artifact repo copies, it
does not reference). Inference loads weights from FileStore via ModelRef;
in SaaS the same metadata points at LakeFS-backed assets (specs 042/047).

**Alternatives considered**:
- *Weights as run artifacts* — rejected: full local copy, double storage,
  slower imports.
- *`config_json` as a version tag* — rejected: MLflow tag values are
  length-limited and configs can exceed limits; tags are for searchable
  scalars only (spec FR-003).

## D3 — Tag schema placement: identity on registered model, per-version provenance on versions

**Decision**:
- **Registered-model tags** (constant per logical model):
  `anvil.kind`, `anvil.source_type`, `anvil.source_identifier`,
  `anvil.display_name`, `anvil.lifecycle_state`.
- **Model-version tags** (vary per version): `anvil.revision_sha`,
  `anvil.architecture_family`, `anvil.tokenizer_family`, `anvil.license`,
  `anvil.parameter_count`, `anvil.runnable_status`, `anvil.runnable_reason`
  (optional), `anvil.asset_availability` (mutable), `anvil.final_loss`
  (trained kinds), `anvil.lifecycle_state` (mutable).

**Rationale**: Q1 clarification made versions = source revisions, so
revision-varying metadata must be per-version. Kind/source identity is
version-invariant. `set_registered_model_tag` / `set_model_version_tag`
are the supported mutation APIs (official docs) — availability and
lifecycle are the only mutable tags, satisfying append-only semantics
(FR-008) without stages (MLflow stages are deprecated; tags+aliases are
the documented replacement).

**Alternatives considered**: MLflow *aliases* for lifecycle — rejected:
aliases mark promotion targets, not archival; a plain
`anvil.lifecycle_state=archived` tag filters naturally in listings.

## D4 — Listing performance (SC-008): tags carry everything the list needs; no per-model run lookups

**Decision**: The unified listing reads `search_registered_models()` once
plus `search_model_versions()` per page of results, and renders entirely
from tags. All fields any surface needs (kind, display name, architecture,
params, tokenizer, license, runnable, availability, final_loss) are
written as tags at registration time. **No `get_run()` calls in the list
path.**

**Rationale**: The current `list_registered_models()`
(`tracking.py:1430-1527`) issues `search_model_versions` × 2 **and**
`get_run` *per registered model* — the N+1 pattern that would blow the
2-second/100-model budget. Trained-model registration
(`training_run_service.py::_register_model`) and demo warmup
(`demo_model_provider.py:221`) will set `anvil.final_loss` +
`anvil.kind=trained` version tags at registration so the enrichment
lookup disappears.

**Alternatives considered**: Response caching — rejected (YAGNI §11.3, a
cache is a second source of truth; the tag denormalization is sufficient
at 100-model scale).

## D5 — Dedup guard: `catalog_identities` table with UNIQUE constraint (SQLite)

**Decision**: New operational table `catalog_identities` with columns
`(source_type, source_identifier, revision_sha, registry_model_name,
registry_model_version)` and a UNIQUE constraint on the identity triple.
Import flow: INSERT the identity row (transactional lock) → on conflict,
report the existing ModelRef (idempotent success) → else register in
MLflow → UPDATE the row with the resulting version → COMPLETE the job.
If MLflow registration fails, the identity row is rolled back with the
job transaction.

**Rationale**: FR-005 requires a transactional guard; the MLflow registry
has no transactions or unique-tag constraints, so concurrent imports
could otherwise both pass a search-then-create check. A single-purpose
identity table is the minimal transactional primitive (it stores no
catalog metadata — it is a lock + triple→ModelRef resolution, not a
mirror). SQLite UNIQUE + the request-scoped session gives the atomicity.

**Alternatives considered**:
- *UNIQUE on `model_import_jobs`* — rejected: jobs are historical (failed
  + retried jobs legitimately repeat triples).
- *Registry search as lock* — rejected explicitly by FR-005 (race window,
  no transactions).

## D6 — Archive semantics: `anvil.lifecycle_state=archived` tag + explicit asset cleanup

**Decision**: DELETE endpoints set `anvil.lifecycle_state=archived` on the
model version (and on the registered model when all versions are
archived), remove FileStore assets and per-file asset rows, and cancel
in-flight download jobs. Active listings filter `lifecycle_state !=
archived`. No `delete_registered_model`/`delete_model_version` calls, no
renames, ever (FR-008).

**Rationale**: Append-only catalog per ADR-048; referencing records
(evals, adapters) keep resolving because the registry entity still
exists. Matches spec US4 acceptance scenarios directly.

## D7 — Fail-closed contract: `CatalogUnavailableError` → HTTP 503

**Decision**: `ModelCatalogService` follows `TrackingService`'s
lazy-init + `run_in_executor` + reconnect-backoff conventions
(`tracking.py:252,190-250`) but on `_TRANSIENT_EXCEPTIONS` raises a typed
`CatalogUnavailableError` instead of silently returning empty results.
Routes translate it to `503 {"detail": ..., "code": "CATALOG_UNAVAILABLE"}`
via an app-level exception handler. Import jobs catch it and transition
to FAILED (retryable, `error_code=catalog_unavailable`). UI listing
surfaces render an explicit "Model catalog unavailable" state on 503.

**Rationale**: FR-009/SC-005 require fail-closed with a clear signal —
the deliberate inverse of TrackingService's silent degrade (which remains
correct for *tracking*). A distinct service with distinct failure
semantics keeps both contracts honest and testable (stop the sidecar in
e2e → assert 503 + assert training/ops pages still 200).

**Alternatives considered**: Reusing TrackingService with a "strict"
flag — rejected: one class per file / single-responsibility; the two
failure contracts would tangle every call site.

## D8 — Name derivation and URL shape

**Decision**: `catalog_name = f"{source_prefix}--{sanitized_identifier}"`
where `source_prefix` ∈ {`hf`, `local`} (from `SourceType`) and
sanitization maps any character outside `[A-Za-z0-9._-]` to `-` (extends
the existing `_sanitize_model_name`, `tracking.py:1092`). Trained models
keep their existing `dataset-{name}` / `corpus-{name}` / `demo` names
(tagged `anvil.kind=trained` at registration). Merged models keep
`adapter-merge-{adapter_id}` (tagged `anvil.kind=merged`). ModelRef in
URLs: `/v1/models/{name}` and `/v1/models/{name}/versions/{version}` —
names are URL-safe by construction.

**Rationale**: Q3 clarification (provider-prefixed deterministic names);
MLflow rejects `/` and `:` in registry names (existing sanitizer);
keeping trained/merged names unchanged means zero churn in the training
and merge paths beyond adding tags.

## D9 — Inference routing on `anvil.kind`

**Decision**: `InferenceService.load_model` accepts a ModelRef, fetches
the catalog entry once, and dispatches: `trained`/`merged` → existing
artifact/MLflow-run loading path; `external` → FileStore HF layout via
the spec-063 loader (`from_pretrained` on
`data/models/{name}/{version}/hf/`), gated by
`runnable_status == runnable` and `asset_availability ==
assets_available` tags. The current 4-step guess chain (cache →
experiment file → MLflow name-guess → external fallback,
`inference.py:316-518`) collapses to catalog-lookup + kind dispatch;
the in-memory model cache keyed by ModelRef is retained.

**Rationale**: FR-011; removes the bug class where MLflow name-guessing
(`dataset-{id}`/`corpus-{id}`/`demo`) shadowed external models. The
external loading internals (HF→anvil conversion, tokenizer creation) from
spec 063 are reused unchanged — only resolution changes.

## D10 — Operational tables re-keyed by ModelRef columns

**Decision**: `model_import_jobs`, `asset_download_jobs`, `model_assets`,
`lora_adapters`, `evaluation_runs` replace `external_model_id` integer
FKs with `registry_model_name: str` + `registry_model_version: int`
column pairs (indexed together). `external_models` table, `ExternalModel`
ORM, `ExternalModelRepository`, and `workbench.external_model_repo`
(consumed at `workbench.py:570,611,723` and in `api/v1/eval.py:240`,
`api/v1/pages.py:383`, `api/v1/models.py:135,304`) are deleted. One
Alembic revision creates `catalog_identities` and the re-keyed columns
(greenfield — no data migration, ADR-032).

**Rationale**: FR-006/FR-007; cross-store FK/CASCADE is replaced by
policy (D6). String-pair references survive a move to hosted MLflow
untouched (SaaS requirement).

---

## Resolution summary

| Unknown | Resolution |
|---|---|
| Can we register local-path sources without a run? | **No** (verified in MLflow server source) → import-run pattern (D1) |
| Where do weights live? | FileStore keyed by ModelRef; registry holds manifest only (D2) |
| Tag placement for Q1 versioning | Identity on registered model, provenance per version (D3) |
| SC-008 feasibility | Tag denormalization kills the N+1 (D4) |
| FR-005 transactional guard shape | `catalog_identities` UNIQUE table (D5) |
| Archive without hard delete | `anvil.lifecycle_state` tag (D6) |
| Fail-closed vs degrade | New `CatalogUnavailableError` → 503 (D7) |
| Name scheme details | `{prefix}--{sanitized}`, trained names unchanged (D8) |
| load_model unification | Catalog lookup + kind dispatch (D9) |
| Schema changes | 1 revision: new guard table + re-keyed columns, drop external_models (D10) |
