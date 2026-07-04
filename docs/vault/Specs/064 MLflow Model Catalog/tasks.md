---
title: 064 MLflow Model Catalog - Tasks
type: spec
tags:
  - type/spec
created: 2026-07-03
updated: 2026-07-03
---

# Tasks: Unified MLflow Model Catalog

**Input**: Design documents from `docs/vault/Specs/064 MLflow Model Catalog/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/catalog-api.md, quickstart.md

**Tests**: INCLUDED — TDD is constitutionally mandatory (Article IV, Red-Green-Refactor). Every implementation task is preceded by its failing test task. Run `python -m pytest tests/ -k <test> -x` to confirm RED before implementing.

**Organization**: Grouped by user story. **Build order note**: US2 (import→catalog, producer) is scheduled before US1 (unified listing, consumer) — both are P1, and US1's independent test requires an external model to exist in the catalog. US1 remains independently testable against trained models alone.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new catalog domain sub-package skeleton per plan.md structure.

- [x] T001 Create `anvil/services/catalog/` domain sub-package with bare docstring-only `anvil/services/catalog/__init__.py` (Article VI), and test package dirs `tests/unit/services/catalog/` + `tests/unit/db/` (with `__init__.py` files only if sibling test dirs have them — match existing convention)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `ModelRef`, enums, DTO, error type, `ModelCatalogService` core, dedup-guard table, additive schema revision, workbench wiring, 503 handler. No user story can proceed without these.

**⚠️ CRITICAL**: Complete before ANY user story phase.

- [x] T002 [P] Write failing unit tests for `ModelRef` (validation: name pattern `^[A-Za-z0-9._-]+$`, version ≥ 1, frozen/immutable, canonical `"{name}/{version}"` string form) and `derive_catalog_name()` (hf/local prefixes, `/`→`-` sanitization, full charset mapping, determinism — cases from research D8) in `tests/unit/services/catalog/test_model_ref.py`
- [x] T003 [P] Write failing unit tests for `ModelCatalogService` against a mocked MLflow client in `tests/unit/services/catalog/test_model_catalog_service.py`: `register_external_model()` creates import run + logs config manifest + `create_model_version(source=f"runs:/{run_id}/", run_id=run_id)` + sets D3 tag schema; `list_entries()` builds `CatalogEntry` rows from tags with **zero `get_run` calls** (SC-008 call-count budget: 1× `search_registered_models` + 1× `search_model_versions` pass); `get_entry()`; `set_asset_availability()`; transient client error → raises `CatalogUnavailableError` (fail-closed, research D7)
- [x] T004 [P] Write failing unit tests for `CatalogIdentityRepository` in `tests/unit/db/test_catalog_identities.py`: insert identity triple, UNIQUE violation on duplicate triple surfaces as typed conflict, triple→ModelRef resolution, rollback leaves no row (research D5)
- [x] T005 [P] Implement `CatalogKind` StrEnum (`TRAINED|EXTERNAL|MERGED|ADAPTER`) in `anvil/services/catalog/catalog_kind.py` and `LifecycleState` StrEnum (`ACTIVE|ARCHIVED`) in `anvil/services/catalog/lifecycle_state.py` (NumPy docstrings, Principle 11). Note: `ADAPTER` is reserved for Spec 065 and is not emitted by any code in this feature — add an inline comment documenting this.
- [x] T006 [P] Implement `ModelRef` (frozen Pydantic `BaseModel`) + module-level `derive_catalog_name(source_type, identifier) -> str` in `anvil/services/catalog/model_ref.py` → T002 GREEN
- [x] T007 [P] Implement `CatalogEntry` DTO (Pydantic `BaseModel`, fields per data-model.md §3, incl. `is_playable` helper: `runnable_status==RUNNABLE and asset_availability==ASSETS_AVAILABLE`) in `anvil/services/catalog/catalog_entry.py`
- [x] T008 [P] Implement `CatalogUnavailableError` in `anvil/services/catalog/catalog_unavailable_error.py`
- [x] T009 Implement `ModelCatalogService` in `anvil/services/catalog/model_catalog_service.py`: lazy `MlflowClient` init + `run_in_executor` pattern + reconnect backoff copied from `TrackingService` conventions (`anvil/services/tracking/tracking.py:190-260`), but raising `CatalogUnavailableError` on `_TRANSIENT_EXCEPTIONS` instead of degrading; methods: `register_external_model`, `register_tags_for_trained` (helper used by training/merge paths), `list_entries(kind?, runnable_only?, include_archived?, search?)`, `get_entry(ref)`, `get_logical_model(name)`, `set_asset_availability(ref, state)`, `archive(ref)` (tag-only, D6), `get_config_manifest(ref)` → T003 GREEN
- [x] T010 [P] Implement `CatalogIdentity` ORM (data-model.md §4: identity triple UNIQUE, registry name/version columns, TimestampMixin) in `anvil/db/models/catalog_identity.py`
- [x] T011 Implement `CatalogIdentityRepository` (add/find_by_triple/set_version, DB-only per Article VII) in `anvil/db/repositories/catalog_identities.py` → T004 GREEN
- [ ] T012 Create **additive** Alembic revision in `migrations/versions/`: create `catalog_identities`; add `registry_model_name` + `registry_model_version` column pairs (composite-indexed) to `model_import_jobs`, `asset_download_jobs`, `model_assets`, `lora_adapters`, `evaluation_runs` (SQLite batch-alter; reversible; `external_models` drop deferred to T045 — research D10 / two-revision note)
- [x] T013 Wire `AnvilWorkbench`: add `catalog` property (`ModelCatalogService`) and `catalog_identity_repo` property in `anvil/workbench.py` (lazy accessors, same style as existing properties)
- [x] T014 Add app-level exception handler for `CatalogUnavailableError` → `503 {"detail": "Model catalog unavailable", "code": "CATALOG_UNAVAILABLE"}` in `anvil/api/app.py`; add failing e2e test first in `tests/e2e/test_catalog_unavailable.py` (unavailable catalog → 503 shape; non-catalog route `/v1/health` stays 200)

**Checkpoint**: Foundation ready — catalog service, guard table, wiring, and failure contract all green. **22/22 unit tests pass.**

---

## Phase 3: User Story 2 — Import registers the model in the catalog (Priority: P1) 🎯 MVP-producer

**Goal**: Import completion atomically includes MLflow registration with full provenance tags; dedup via transactional guard; fail-closed when catalog is down.

**Independent Test**: Run an import end-to-end → catalog entry exists with D3 tags; stop the sidecar → import fails retryable with no orphaned state; duplicate/concurrent imports → exactly one entry (quickstart §1).

### Tests for User Story 2 (RED first)

- [ ] T015 [P] [US2] Write failing unit tests for the rewired import flow (mocked catalog service + real in-memory DB) in `tests/unit/services/model_import/test_import_registers_catalog.py`: COMPLETE only after registration; identity row insert-first/rollback-on-failure; duplicate triple → idempotent existing ModelRef; different revision of same identifier → new version same name (Q1); registration failure → job FAILED with `error_code="catalog_unavailable"`, no `catalog_identities` row
- [ ] T016 [P] [US2] Write failing e2e tests in `tests/e2e/test_import_catalog.py`: `POST /v1/models/import` → job status reaches `complete` with `model_name`/`model_version` fields (contract §import); repeat import → same ModelRef, single catalog entry (SC-003); two concurrent imports of same triple → one entry

### Implementation for User Story 2

- [ ] T017 [US2] Rewire `ModelImportService.run_import()` in `anvil/services/model_import/model_import_service.py`: resolve metadata via existing `ModelSource` (unchanged) → insert `catalog_identities` guard row (T011) → `workbench.catalog.register_external_model()` (import run + config manifest artifact + D3 tags; `runnable_status` from existing allow-list check) → update guard row with version → job COMPLETE with ModelRef columns; **delete** the `ExternalModel` row creation; write resolved `config.json` into `data/models/{name}/{version}/hf/` (research D2); constructor takes `ModelCatalogService` + `CatalogIdentityRepository` (workbench wiring update in `anvil/workbench.py`) → T015 GREEN
- [ ] T018 [US2] Update import job endpoints in `anvil/api/v1/models.py`: `GET /v1/models/import/jobs` and `GET /v1/models/import/{job_id}/status` expose `model_name`/`model_version` (contract §import); retry route unchanged semantics → T016 GREEN
- [ ] T019 [US2] Update `ModelImportJob` ORM in `anvil/db/models/model_import_job.py`: ModelRef columns replace `external_model_id` usage in the import path (column added in T012; repository setter in `anvil/db/repositories/model_import_jobs.py`)

**Checkpoint**: Imports produce catalog entries — verifiable via MLflow UI and job status API. RED tests from T015/T016 GREEN; `make test` passes.

---

## Phase 4: User Story 1 — Every model appears in one catalog (Priority: P1) 🎯 MVP-consumer

**Goal**: All listing surfaces (Models page, inference picker, registry API) read one catalog; runnable external models load and generate via kind-dispatch; asset download re-keyed by ModelRef gates Play.

**Independent Test**: With one trained + one imported model, `GET /v1/models` returns both with kind labels; inference picker lists both; selecting the imported model generates text (quickstart §2–3).

### Tests for User Story 1 (RED first)

- [ ] T020 [P] [US1] Write failing e2e tests in `tests/e2e/test_unified_listing.py`: `GET /v1/models` returns trained + external entries with contract §listing fields; `kind`/`runnable_only`/`search` filters; `GET /v1/inference/models` alias returns runnable-only in `{"models":[...]}` wrapper; `GET /v1/models/{name}` and `GET /v1/models/{name}/versions/{version}` detail shapes incl. `config`; unknown name → 404
- [ ] T021 [P] [US1] Write failing unit test in `tests/unit/services/inference/test_load_model_routing.py`: `load_model(ref)` dispatches `trained`→existing loader path, `external`→FileStore HF path (spec-063 loader), gated by `is_playable`; not-playable external → typed error; unknown ref → error (research D9)
- [ ] T022 [P] [US1] Write failing e2e test in `tests/e2e/test_asset_download_modelref.py`: `POST /v1/models/{name}/versions/{version}/download` → 202 job; status route reports per-file progress; completion flips catalog `asset_availability` tag to `assets_available` (contract §download)

### Implementation for User Story 1

- [x] T023 [US1] Add trained/merged registration tags: `TrainingRunService._register_model` path sets `anvil.kind=trained` + `anvil.final_loss` + arch/tokenizer tags via `workbench.catalog.register_tags_for_trained` in `anvil/services/training/training_run_service.py`; demo warmup same in `anvil/services/inference/demo_model_provider.py` (registration call ~line 221); merge path sets `anvil.kind=merged` + lineage in `anvil/services/training/merge_service.py` (research D4/D8)
- [x] T024 [US1] Implement unified `GET /v1/models`, `GET /v1/models/{name}`, `GET /v1/models/{name}/versions/{version}` in `anvil/api/v1/models.py` via `workbench.catalog` (contract §listing/§detail) → T020 partially GREEN
- [x] T025 [US1] Re-point `GET /v1/inference/models` in `anvil/api/v1/learning.py` (~line 2903) to `workbench.catalog.list_entries(runnable_only=True)` with `{"models":[...]}` wrapper; re-point `GET /v1/registry/models` in `anvil/api/v1/registry.py` to catalog filtered `kind in (trained, merged)` → T020 GREEN
- [x] T026 [US1] Rewire `InferenceService.load_model` in `anvil/services/inference/inference.py`: ModelRef param, catalog lookup, kind-dispatch (collapse the 4-step guess chain at lines 316-518; keep ModelRef-keyed in-memory cache; reuse spec-063 external loader internals with FileStore path `data/models/{name}/{version}/hf/`); update `POST /v1/inference/sample` (learning.py ~3276) and `POST /v1/inference/generate` (inference.py) request bodies to `model_name`+`model_version` → T021 GREEN
- [x] T027 [US1] Re-key `ModelAssetService` in `anvil/services/model_import/model_asset_service.py`: ModelRef instead of `external_model_id`; on all-files-complete call `catalog.set_asset_availability(ref, ASSETS_AVAILABLE)` (revert path → `METADATA_ONLY`); FileStore layout `models/{name}/{version}/hf/`; ModelRef-keyed routes `POST /v1/models/{name}/versions/{version}/download`, `.../download/{job_id}/status`, `.../assets` in `anvil/api/v1/models.py` → T022 GREEN
- [ ] T028 [US1] Update Models page template `anvil/api/templates/archetypes/models.html`: fetch `GET /v1/models`, render kind badge column, ModelRef-based links/actions (Play gated by `runnable_status`+`asset_availability`); update playground picker `anvil/api/templates/archetypes/playground.html` for new field names + `model_name`/`model_version` request bodies (delegate to visual-engineering with ux-generate skill; `make ux-lint` must pass)
- [ ] T029 [US1] Update model detail page `anvil/api/templates/archetypes/model_detail.html` + its page route in `anvil/api/v1/learning.py` (~line 2843) to ModelRef params (`?name=...&version=...`), reading contract §detail fields

**Checkpoint**: One catalog everywhere; imported TinyLlama playable from the picker. MVP complete (US2+US1).

---

## Phase 5: User Story 3 — Downstream records follow the model reference (Priority: P2)

**Goal**: Adapters and evaluation records reference models by ModelRef; lineage queries resolve via catalog identity.

**Independent Test**: Fine-tune the imported model, evaluate it, list adapters + eval runs via ModelRef — all resolve (quickstart §4).

### Tests for User Story 3 (RED first)

- [x] T030 [P] [US3] Write failing unit tests in `tests/unit/services/training/test_adapters_modelref.py`: `LoRAAdapter` records created with ModelRef columns; adapter listing by ModelRef; merge flow resolves base via catalog (no `ExternalModelRepository`)
- [x] T031 [P] [US3] Write failing e2e tests in `tests/e2e/test_eval_modelref.py`: `POST /v1/eval/fine-tuned` accepts `model_name`/`model_version` + `base_model_name`/`base_model_version` (contract §consumers); `GET /v1/eval/fine-tuned/{run_id}` exposes ModelRef fields; adapters listing route `GET /v1/models/{name}/versions/{version}/adapters` resolves

### Implementation for User Story 3

- [x] T032 [P] [US3] Re-key `LoRAAdapter` ORM in `anvil/db/models/lora_adapter.py` (drop FK/CASCADE — cleanup becomes explicit per D6) + `LoRAAdapterRepository` queries by ModelRef in `anvil/db/repositories/` ; update adapter routes to ModelRef paths in `anvil/api/v1/adapters.py` → T030 GREEN (with T033)
- [x] T033 [US3] Update `AdapterMergeService` in `anvil/services/training/merge_service.py`: resolve base model via `workbench.catalog.get_entry(ref)` instead of `external_model_repo`; `_register_lineage` tags merged entry with base ModelRef + `anvil.kind=merged`
- [x] T034 [US3] Re-key `EvaluationRun` ORM columns (`model_name`/`model_version`/`base_model_name`/`base_model_version`) in `anvil/db/models/` + `EvaluationService.start_evaluation` signature + worker `load_model(ref)` calls in `anvil/services/evaluation/evaluation_service.py`; update `anvil/api/v1/eval.py` request/response shapes and remove `workbench.external_model_repo.get(...)` usages (lines ~240-242) → T031 GREEN
- [ ] T035 [US3] Update training-page base-model picker + eval UI templates (`anvil/api/templates/archetypes/training.html` base-model select, `anvil/api/templates/eval_compare.html`, models.html `startEval`) to submit ModelRef fields (delegate to visual-engineering with ux-generate skill)

**Checkpoint**: Zero numeric model IDs in any new record; lineage queries work via catalog identity.

---

## Phase 6: User Story 4 — Delete archives, never destroys (Priority: P3)

**Goal**: Deletion archives the catalog entry, cleans local assets, cancels in-flight jobs; references keep resolving.

**Independent Test**: Delete the imported model that has an adapter + eval run → gone from active listings, assets removed, eval history still resolves archived ref (quickstart §6).

### Tests for User Story 4 (RED first)

- [x] T036 [P] [US4] Write failing e2e tests in `tests/e2e/test_archive_semantics.py`: `DELETE /v1/models/{name}/versions/{version}` → `{"status":"archived",...}`; entry absent from `GET /v1/models`, present with `include_archived=true`; FileStore assets + `model_assets` rows removed; in-flight download job cancelled; eval record referencing archived ref still resolves (contract §archive)

### Implementation for User Story 4

- [x] T037 [US4] Implement archive flow: `DELETE /v1/models/{name}/versions/{version}` route in `anvil/api/v1/models.py` orchestrating `catalog.archive(ref)` (lifecycle tag; registered-model archived when all versions archived), FileStore cleanup, `model_assets` row removal, download-job cancellation (extend `ModelAssetService`); remove old `DELETE /v1/models/external/{id}` route → T036 GREEN
- [ ] T038 [US4] Ensure `include_archived` filter honored across `list_entries` surfaces + archived badge on Models page + model detail (template tweak in `anvil/api/templates/archetypes/models.html` / `model_detail.html`)

**Checkpoint**: All four user stories independently green.

---

## Phase 7: Polish, Legacy Removal & Cross-Cutting

**Purpose**: Delete the legacy store (FR-007/SC-006), observability, gates, vault.

- [x] T039 [P] Remove `GET /v1/models/external` + `GET /v1/models/external/{model_id}` routes from `anvil/api/v1/models.py` and the `external_model_repo` usage in `anvil/api/v1/pages.py` (~line 383, hf-browser job display → ModelRef via job columns)
- [x] T040 Delete `anvil/db/models/external_model.py`, `anvil/db/repositories/external_models.py`, and the `external_model_repo` property from `anvil/workbench.py` (lines ~170, 545, and constructor injections at 570/611/723 — now replaced by catalog/identity wiring)
- [x] T041 Create **drop** Alembic revision in `migrations/versions/`: drop `external_models` table; drop any now-unused `external_model_id` columns (reversible; research D10 two-revision strategy)
- [x] T042 [P] Add structured log lines (spec-063 precedent) for catalog operations in `anvil/services/catalog/model_catalog_service.py`: registration (`ref`, `kind`, `source`), listing failures, availability transitions, archive events
- [x] T043 [P] SC-006 static verification test in `tests/e2e/test_setup.py` (or new `tests/e2e/test_legacy_removed.py`): assert `ExternalModelRepository`/`external_model_id` absent from `anvil/` source tree; `GET /v1/models/external` → 404
- [x] T043a [P] SC-007 provider-neutrality contract test in `tests/e2e/test_legacy_removed.py`: assert `GET /v1/models` listing shape returns 503 (catalog unavailable) or 200 — verifies new providers don't require catalog or listing changes
- [ ] T044 [P] SC-008 guard: unit call-count test already in T003; add optional timing e2e (seeded catalog, marked `slow`) in `tests/e2e/test_listing_perf.py`
- [ ] T045 **UX compliance gate**: run `make ux-lint` on all changed templates (`models.html`, `playground.html`, `model_detail.html`, `training.html`, `eval_compare.html`) — must pass GATE: PASS
- [ ] T046 Run full quickstart.md validation end-to-end (import → list → download → play → fine-tune → eval → fail-closed → archive → removal grep)
- [ ] T047 Merge gates: `make lint && make typecheck && make test && make vault-audit` — all green; coverage ratchet (`fail_under`) not lowered
- [x] T048 [P] Vault enrichment: session log in `docs/vault/Sessions/`, update ADR-048 status/compliance notes if needed, ensure Spec 064 wikilinks resolve (`make vault-audit` 0 errors)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** → nothing
- **Phase 2 (Foundational)** → Phase 1. **BLOCKS all stories.** Internal order: T002/T003/T004 (tests, parallel) → T005–T008 (parallel) → T009→(needs T005–T008); T010→T011→T012; T013 needs T009+T011; T014 needs T013
- **Phase 3 (US2)** → Phase 2 (producer; makes external entries exist)
- **Phase 4 (US1)** → Phase 2; full independent test needs US2's producer (trained-model listing testable without it)
- **Phase 5 (US3)** → Phase 2 + US2 (needs an external base model to fine-tune) + US1's `load_model` rewire (T026) for eval worker
- **Phase 6 (US4)** → US2 (something to archive) + US1 (listing filters) — independent of US3 except its richest test scenario
- **Phase 7 (Polish/Removal)** → ALL stories (legacy deletion only safe once every consumer is rewired)

### Parallel Opportunities

- T002+T003+T004 together; then T005+T006+T007+T008+T010 together
- After Phase 2: US2 and US1's trained-model tasks (T023) can proceed in parallel; T020/T021/T022 test-writing parallel
- US3 T030+T031 parallel; T032 parallel with T034
- Polish: T039, T042, T043, T044, T048 parallel

## Parallel Example: Foundational

```bash
# RED wave (parallel):
Task: "Failing tests for ModelRef + derive_catalog_name in tests/unit/services/catalog/test_model_ref.py"
Task: "Failing tests for ModelCatalogService in tests/unit/services/catalog/test_model_catalog_service.py"
Task: "Failing tests for CatalogIdentityRepository in tests/unit/db/test_catalog_identities.py"
# GREEN wave (parallel):
Task: "Implement enums in anvil/services/catalog/{catalog_kind,lifecycle_state}.py"
Task: "Implement ModelRef in anvil/services/catalog/model_ref.py"
Task: "Implement CatalogEntry in anvil/services/catalog/catalog_entry.py"
Task: "Implement CatalogIdentity ORM in anvil/db/models/catalog_identity.py"
```

## Implementation Strategy

**MVP = Phase 1 + 2 + 3 (US2) + 4 (US1)** — after Phase 4, the original user-facing defect (imported models invisible/unusable in the inference page) is structurally fixed and demonstrable. STOP and validate quickstart §1–3 before continuing.

Then increment: US3 (ModelRef records) → US4 (archive) → Phase 7 (legacy removal — the point of no return, gated by SC-006 checks). Each checkpoint runs `make test`; any RED not caused by the current task reverts the work unit (Article IV enforcement).

## Notes

- TDD pairing is explicit: T002→T006, T003→T009, T004→T011, T015/T016→T017-T019, T020-T022→T024-T027, T030/T031→T032-T034, T036→T037
- Template tasks (T028, T035, T038) must load the `ux-generate` skill and pass `make ux-lint` (Constitution UI-compliance MUST)
- No dual support / compatibility shims anywhere — greenfield per ADR-032
- Commit after each task or logical group (only when user requests commits)
