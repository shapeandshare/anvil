---
description: "Task list for Content Repository (016-lakefs-content-repo)"
---

# Tasks: Content Repository (versioned, reproducible training data)

**Input**: Design documents from `/specs/016-lakefs-content-repo/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the project Constitution (Article IV) mandates TDD (Red-Green-Refactor)
with ratcheting coverage. Test tasks are written and must FAIL before implementation.

**Organization**: By user story. Phase order follows the plan's MVP-first phased delivery.
Local mode is pure-Python (research D1) — **no LakeFS, no new runtime dependency, no sidecar**.

**Naming**: User-facing unit = "Corpus"; new ORM classes use `Content*` prefix /
`content_*` tables to avoid collision with the legacy `Corpus`/`corpora` (Directory Corpus,
deprecated, out of scope). See data-model.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete deps)
- **[Story]**: US1–US9 mapping to spec.md
- All paths absolute from repo root `anvil/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Domain package skeleton, enums, config, test scaffolding.

- [ ] T001 Create domain package `anvil/services/content/__init__.py` (bare docstring per Article VI) and the directory.
- [ ] T002 [P] Create `ContentCorpusStatus` StrEnum in `anvil/services/content/content_corpus_status.py` (DRAFT/ACTIVE/ARCHIVED).
- [ ] T003 [P] Create `SourceKind` StrEnum in `anvil/services/content/source_kind.py` (INJECTOR/IMPORTER/MANUAL).
- [ ] T004 [P] Create `IngestStatus` StrEnum in `anvil/services/content/ingest_status.py` (OPEN/VALIDATING/ACCEPTED/FAILED).
- [ ] T005 [P] Create `LockState` StrEnum in `anvil/services/content/lock_state.py` (HELD/RELEASED).
- [ ] T006 Add content-storage config keys to `anvil/config.py` (`content_dir` default `data/content`, derived `content_blobs_dir`, `content_staging_dir`) in `get_config()`; document in `.env.example` (`ANVIL_CONTENT_DIR`).
- [ ] T007 [P] Create test package dirs + fixtures: `tests/unit/services/content/__init__.py`, `tests/integration/content/__init__.py`, and an async DB + temp-content-dir fixture in `tests/integration/content/conftest.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared value types, substrate ABC, ALL ORM models + the single migration,
repositories, and router/workbench wiring. **No user story can begin until this is done.**

**⚠️ CRITICAL**: Blocks every user story.

### Value types (Pydantic BaseModel, `anvil/services/content/`)

- [ ] T008 [P] Create `ManifestEntry` + `Manifest` value types and the canonical-digest helper in `anvil/services/content/manifest.py` (sha256 over canonical JSON per contracts/manifest.schema.md).
- [ ] T009 [P] Create `VersionRef` value type in `anvil/services/content/version_ref.py` (carries `manifest_digest`, `version_id`, `version_number`, `label`).
- [ ] T010 [P] Create `IngestSessionRef` value type in `anvil/services/content/ingest_session_ref.py`.
- [ ] T011 [P] Create `ValidationProblem` + `ValidationReport` value types in `anvil/services/content/validation_report.py`.
- [ ] T012 [P] Create `AcceptResult` value type in `anvil/services/content/accept_result.py`.

### Substrate interface

- [ ] T013 Create the `VersionedContentStore` ABC in `anvil/services/content/versioned_content_store.py` (all async methods per contracts/versioned-content-store.md).

### ORM models (one class per file, `anvil/db/models/`)

- [ ] T014 [P] Create `ContentSource` model in `anvil/db/models/content_source.py` (table `content_sources`).
- [ ] T015 [P] Create `ContentCorpus` model in `anvil/db/models/content_corpus.py` (table `content_corpora`, provenance FK to `license_catalog`, `current_version_id` FK).
- [ ] T016 [P] Create `ContentVersion` model in `anvil/db/models/content_version.py` (table `content_versions`, unique `(corpus_id, version_number)` and `(corpus_id, manifest_digest)`).
- [ ] T017 [P] Create `ContentEntry` model in `anvil/db/models/content_entry.py` (table `content_entries`, index `(version_id, path)`).
- [ ] T018 [P] Create `ContentBlob` model in `anvil/db/models/content_blob.py` (table `content_blobs`, PK `content_hash`).
- [ ] T019 [P] Create `ContentTag` model in `anvil/db/models/content_tag.py` (table `content_tags`, unique `version_id`/`name`).
- [ ] T020 [P] Create `IngestSession` model in `anvil/db/models/content_ingest_session.py` (table `content_ingest_sessions`).
- [ ] T021 [P] Create `ImportJob` model in `anvil/db/models/content_import_job.py` (table `content_import_jobs`).
- [ ] T022 [P] Create `CheckoutLock` model in `anvil/db/models/content_lock.py` (table `content_locks`).
- [ ] T023 [P] Create `VersionRunRef` model in `anvil/db/models/content_version_run_ref.py` (table `content_version_run_refs`, indexed `mlflow_run_id`).

### Migration + registration

- [ ] T024 Add explicit imports of all 10 new models to `anvil/_resources/migrations/env.py` (so `Base.metadata` sees them; `anvil/db/models/__init__.py` stays bare).
- [ ] T025 Create reversible Alembic migration `anvil/_resources/migrations/versions/0NN_add_content_repository.py` creating all 10 `content_*` tables (no changes to `corpora`/`datasets`; reuse `license_catalog` FK). Verify `upgrade`/`downgrade` round-trip.

### Repositories (`anvil/db/repositories/`)

- [ ] T026 [P] Create `ContentCorpusRepository` in `anvil/db/repositories/content_corpora.py` (CRUD, get_by_slug, list, set_current_version).
- [ ] T027 [P] Create `ContentSourceRepository` in `anvil/db/repositories/content_sources.py`.
- [ ] T028 [P] Create `ContentVersionRepository` in `anvil/db/repositories/content_versions.py` (add version+entries, get_by_digest, list_by_corpus, run-ref writes/reads).
- [ ] T029 [P] Create `ContentIngestSessionRepository` in `anvil/db/repositories/content_ingest_sessions.py`.
- [ ] T030 [P] Create `ContentBlobRepository` in `anvil/db/repositories/content_blobs.py` (upsert, exists, reachable-refs query for GC).
- [ ] T031 [P] Create `ContentImportJobRepository` in `anvil/db/repositories/content_import_jobs.py`.
- [ ] T032 [P] Create `ContentLockRepository` in `anvil/db/repositories/content_locks.py`.

### Wiring

- [ ] T033 Add lazy content accessors to `anvil/workbench.py` (`content_corpora`, `content_ingestion`, `content_composition`, `content_lineage`, `content_imports`, `content_locks`, repositories, and a `content_store` accessor returning `LocalVersionedContentStore` — the SaaS injection seam).
- [ ] T034 Create empty content router `anvil/api/v1/content.py` (`router = APIRouter()`) and include it in `anvil/api/v1/router.py`.

**Checkpoint**: Schema migrates, models/repos importable, mypy strict clean — stories can begin.

---

## Phase 3: User Story 1 - Reproducible training from a pinned version (P1) 🎯 MVP

**Goal**: Create corpus → ingest (single session) → per-batch validate → freeze immutable
version (manifest digest) → pin in a training run → re-resolve identically.

**Independent Test**: quickstart.md steps 1–6 — pin a version, mutate the corpus, re-resolve
the pinned version and confirm byte-identical entries (SC-001).

### Tests (write first, must FAIL)

- [ ] T035 [P] [US1] Unit test manifest digest determinism + immutability in `tests/unit/services/content/test_manifest_digest.py` (sorted entries, stable sha256, change→new digest).
- [ ] T036 [P] [US1] Unit test content-addressed blob store (put dedup, open_blob round-trip) in `tests/unit/services/content/test_local_store_blobs.py`.
- [ ] T037 [P] [US1] Contract test for `VersionedContentStore` freeze/resolve guarantees (VCS-1/2) in `tests/unit/services/content/test_versioned_content_store_contract.py`.
- [ ] T038 [P] [US1] Integration test full reproducibility flow (create→stage→validate→accept→freeze→resolve-after-mutation identical) in `tests/integration/content/test_reproducibility_flow.py`.
- [ ] T038a [P] [US1] Integration test promotion tagging (freeze → tag → version exposes tag; duplicate tag name rejected) in `tests/integration/content/test_promotion_tag.py` (FR-023).

### Implementation

- [ ] T039 [US1] Implement `LocalVersionedContentStore` in `anvil/services/content/local_versioned_content_store.py`: content-addressed blob put/open over `LocalFileStore` (`data/content/blobs/<aa>/<sha256>`), single-session `open_session`/`stage` into `data/content/staging/<key>/`, `freeze_version` (manifest+digest), `resolve`, `open_blob` (depends on T008–T013, T039 store needs repos T028/T030).
- [ ] T040 [P] [US1] Implement minimal per-batch `ValidationService` in `anvil/services/content/validation_service.py`: UTF-8/readability, size bounds, required provenance metadata, intra-batch exact dedup; returns `ValidationReport` (~5s target).
- [ ] T041 [US1] Implement `CorpusService` in `anvil/services/content/corpus_service.py`: `create` (with `GovernanceService` provenance/license gate), `get`, `list`, `list_versions` (depends on T026, T028).
- [ ] T042 [US1] Implement `IngestionService` (single-session happy path) in `anvil/services/content/ingestion_service.py`: `open_session`, `stage`, `validate` (per-batch), `accept` (fold→new version) (depends on T039, T040, T029).
- [ ] T043 [US1] Implement `LineageService.record_run_ref` in `anvil/services/content/lineage_service.py` (writes `VersionRunRef`) (depends on T028).
- [ ] T044 [US1] Add content Pydantic request/response bodies for US1 to `anvil/api/v1/schemas.py` (`CorpusCreate`, `SessionOpen`, `StageEntry`, `FreezeVersionBody`, `CorpusOut`, `VersionOut`, `SessionOut`, `ValidationReportOut`).
- [ ] T045 [US1] Implement US1 endpoints in `anvil/api/v1/content.py`: POST/GET `/content/corpora`, GET `/content/corpora/{id}`, GET `/content/corpora/{id}/versions`, POST `/content/sources`, POST `/content/sessions`, POST `/content/sessions/{id}/stage`, POST `/content/sessions/{id}/validate`, POST `/content/sessions/{id}/accept`, POST `/content/corpora/{id}/freeze`, GET `/content/versions/{id}` (uses `get_workbench`).
- [ ] T045a [US1] Implement promotion tagging (FR-023): add `tag(version_id, name)` to `ContentVersionRepository`/`CorpusService`, `TagBody`/`tag` field in `VersionOut` (`anvil/api/v1/schemas.py`), and `POST /content/versions/{id}/tag` in `anvil/api/v1/content.py` (sets `ContentTag`, `gc_protected=True`). Used by quickstart §4 + contracts/api-endpoints.md.
- [ ] T046 [US1] Wire reproducibility into training start: in `anvil/api/v1/training.py` accept `content_version_id`, resolve via `content_store`, log `corpus_ref`=digest + `MetaDataset` + `corpus_manifest.json`, and call `record_run_ref` (depends on T043).
- [ ] T047 [US1] Implement corpus version resolution for training data loading (resolve manifest → stream blobs → chunk via existing `ChunkingStrategy`) consumed by the training data path.

**Checkpoint**: MVP — reproducibility-by-reference works end-to-end. Delivers SC-001, SC-012(per-batch).

---

## Phase 4: User Story 8 - Transparent zero-config local operation (P1)

**Goal**: Everything above works on a clean install with zero config and zero awareness of
supporting services (no LakeFS/sidecar exists in local mode by design — research D1).

**Independent Test**: quickstart.md on a clean checkout: `make setup && make run`, run the
US1 flow with no configuration and confirm no content service appears in the ops surface.

### Tests

- [ ] T048 [P] [US8] e2e test in `tests/e2e/test_content_zero_config.py`: fresh DB + temp content dir, run create→ingest→freeze→resolve with default config only; assert no new env/credentials required.
- [ ] T049 [P] [US8] Test that `GET /v1/services` does NOT introduce a managed content sidecar in local mode (no extra process) in `tests/integration/content/test_no_local_sidecar.py`.

### Implementation

- [ ] T050 [US8] Ensure first-run content dirs are created lazily with sensible defaults (no setup step) in `LocalVersionedContentStore`/startup; confirm `make run` requires zero content config.
- [ ] T051 [US8] Add a short "Content repository (local)" note to README/quickstart confirming zero-config + no external service.

**Checkpoint**: SC-010 satisfied; local transparency validated.

---

## Phase 5: User Story 2 - Concurrent isolated content injection (P1)

**Goal**: Multiple producers ingest concurrently in isolation; serialized atomic acceptance;
app-level producer scoping; revert safety net.

**Independent Test**: two concurrent sessions stage distinct content, neither sees the other,
both accept without disturbing each other; producer write outside its session is denied.

### Tests

- [ ] T052 [P] [US2] Integration test concurrent isolation (two sessions, no cross-visibility) in `tests/integration/content/test_concurrent_isolation.py`.
- [ ] T053 [P] [US2] Integration test serialized atomic acceptance under simultaneous accept in `tests/integration/content/test_serialized_acceptance.py`.
- [ ] T054 [P] [US2] Unit test producer scoping denial (write outside own session) in `tests/unit/services/content/test_producer_scoping.py`.
- [ ] T055 [P] [US2] Integration test revert to prior version in `tests/integration/content/test_revert.py`.

### Implementation

- [ ] T056 [US2] Harden session isolation in `LocalVersionedContentStore`: per-session staging namespace, no canonical reads of other sessions' staging (FR-006).
- [ ] T057 [US2] Implement serialized acceptance in `IngestionService`/store: `asyncio.Lock` keyed per corpus + single SQLite write transaction for atomic fold (FR-010); add `abandon_session`.
- [ ] T058 [US2] Implement app-level producer scoping in `IngestionService` (session may only write its own staging; only accept mutates canonical) (FR-007/008).
- [ ] T058a [US2] Implement the management-action authorization seam (FR-036): a single guard/dependency through which management endpoints (rename/tag/compose/promote/lock) pass; in local single-user mode it permits the local operator (trivial), and it is the documented injection point for multi-principal RBAC in the future SaaS delivery. Add to `anvil/api/v1/content.py` (or a small `anvil/services/content/authz.py`).
- [ ] T059 [US2] Implement `revert` in store + `CorpusService.revert` + endpoint `POST /content/corpora/{id}/revert` (FR-011).
- [ ] T060 [US2] Implement failed/abandoned session staging retention marker (closed_at, status FAILED) for the ~30-day cleanup policy (FR-025).

**Checkpoint**: SC-003, SC-005 satisfied; isolation + serialized acceptance + revert work.

---

## Phase 6: User Story 3 - Automated quality & safety validation gates (P1)

**Goal**: Full gate suite — per-batch (fast) + cross-corpus pre-acceptance (~30s), fail-closed,
near-dup advisory post-acceptance.

**Independent Test**: submit malformed + exact-dup + valid items; valid proceeds, others
blocked with reasons; a near-dup is accepted but flagged.

### Tests

- [ ] T061 [P] [US3] Unit tests for each pre-acceptance gate (cross-corpus dedup, language allowlist, sensitive-info, shape) in `tests/unit/services/content/test_validation_gates.py`.
- [ ] T062 [P] [US3] Integration test fail-closed on gate timeout/unavailability in `tests/integration/content/test_fail_closed.py`.
- [ ] T063 [P] [US3] Integration test problems recorded + surfaced on rejected accept in `tests/integration/content/test_validation_problems.py`.
- [ ] T063a [P] [US3] Latency verification test (SC-012) in `tests/integration/content/test_validation_latency.py`: against the reference batch (~100 text entries, ≤ ~10 MB), assert per-batch validation completes within ~5s and pre-acceptance within ~30s (use generous CI-safe margins).

### Implementation

- [ ] T064 [US3] Extend `ValidationService` with pre-acceptance gates: cross-corpus exact dedup (content-hash set), language allowlist, sensitive-info scan (reuse `GovernanceService`), shape conformance (~30s target) (FR-013).
- [ ] T065 [US3] Implement fail-closed semantics + per-gate timeouts in `IngestionService.accept` (reject, canonical unchanged) (FR-014/016).
- [ ] T066 [US3] Persist structured problems to `IngestSession.problems_json` and return them in the accept `422` response (FR-014).
- [ ] T067 [US3] Implement license gate on ingestion (reject disallowed license) reusing governance (FR-017).

**Checkpoint**: SC-004 satisfied; full blocking gate suite + fail-closed validated.

---

## Phase 7: User Story 4 - Compose & ensemble weighted versions (P2)

**Goal**: Weighted multi-source composition with preview and reproducible frozen versions.

**Independent Test**: compose 70/30 from two sources, preview mix, freeze, re-open → identical
recipe; pin → training applies weights.

### Tests

- [ ] T068 [P] [US4] Unit test composition preview (per-source token/byte contribution) in `tests/unit/services/content/test_composition_preview.py`.
- [ ] T069 [P] [US4] Integration test freeze composition + identical re-resolution + weighted apply in `tests/integration/content/test_composition_freeze.py`.
- [ ] T070 [P] [US4] Unit test reject empty / all-zero-weight composition in `tests/unit/services/content/test_composition_guards.py`.

### Implementation

- [ ] T071 [US4] Implement `CompositionService` in `anvil/services/content/composition_service.py`: `preview(corpus_id, spec)` and `freeze(corpus_id, spec)` building a composition manifest (`is_composition=True`) (FR-018/019/020/022).
- [ ] T072 [US4] Implement weighted resolution in resolver/training data path (apply `weight` at sampling) (FR-021).
- [ ] T073 [US4] Add `CompositionSpec` schema + endpoints `POST /content/corpora/{id}/composition/preview` and composition path in `/content/corpora/{id}/freeze` in `anvil/api/v1/content.py` + `schemas.py`.
- [ ] T073a [US4] Implement the composition-preview SSE endpoint `GET /content/stream/composition` (`StreamingResponse` + `asyncio.Queue`, mirror `training.py`) that emits projected per-source token/byte contribution as the curator adjusts weights (FR-019; contracts/api-endpoints.md line 48). Backend only — consumed by the Composer view (T082a).

**Checkpoint**: SC-006 satisfied.

---

## Phase 8: User Story 5 - Browse library, version timeline & lineage (P2)

**Goal**: A polished, design-system-conformant **content hub** in the browser — Corpus
Library, Version Timeline (diff vs prior), Lineage, and a live Injection Monitor — plus the
client interactions (forms + SSE) for the full corpus workflow, and the **Ensemble Composer**
view (consuming US4's preview SSE). This is the phase where the content repository becomes
usable from the UI (the MVP, Phases 1–3, is intentionally API-first — quickstart uses curl).

**Independent Test**: with several corpora/versions, the content hub renders accurate library
summaries, timeline diffs, and lineage; a curator can create a corpus, ingest, validate,
accept, freeze, tag, and revert entirely from the browser; the Injection Monitor and Composer
update live; screens pass the design-system + accessibility checks (T080b).

### Tests

- [ ] T074 [P] [US5] Integration test library listing + version timeline diff in `tests/integration/content/test_library_timeline.py`.
- [ ] T075 [P] [US5] Integration test lineage (sources + run refs) in `tests/integration/content/test_lineage.py`.

### Implementation

- [ ] T076 [US5] Implement `LineageService.lineage(version_id)` (join entries→sources, run_refs→runs) (FR-026/031).
- [ ] T077 [US5] Implement version-timeline diff (entries added/removed vs prior version) in `ContentVersionRepository`/service (FR-028).
- [ ] T078 [US5] Implement endpoints: GET `/content/corpora`, GET `/content/corpora/{id}/versions` (timeline), GET `/content/versions/{id}/lineage`, GET `/content/sessions` in `anvil/api/v1/content.py` (FR-027/028/029/031).
- [ ] T079 [US5] Implement SSE injection-status stream `GET /content/stream/injection` (StreamingResponse + asyncio.Queue, mirror `training.py`) (FR-029).
- [ ] T080 [P] [US5] Create the **content hub shell** `anvil/api/templates/archetypes/content_library.html` (extends `base.html`; renders the Corpus Library, Version Timeline w/ diff, and Lineage views, with mount points for the Composer/Import Console/Checkout Board views added in their phases). Follow the forge archetype.
- [ ] T081 [US5] Add `/v1/content-page` route in `anvil/api/v1/pages.py` and a "Content" nav tab (with icon) in `anvil/api/templates/base.html`.
- [ ] T082 [P] [US5] Wire the Injection Monitor live view to the SSE injection-status stream using the existing `SSESession` client (`anvil/api/static/js/sse.js`).
- [ ] T080a [US5] Create `anvil/api/static/js/content.js` (+ `anvil/api/static/css/` additions if needed): client interactions/forms for create-corpus, register-source, open-session, stage/upload (multipart), validate, accept, freeze, tag, and revert; consume the `{data, error}` envelope and surface validation `problems`; use `SSESession` for live views. (Covers U-D.)
- [ ] T082a [P] [US5] Implement the **Ensemble Composer** view (design-doc forge screen): entry/source selection, weight sliders, live mix distribution (token/byte) + chunking preview via the composition-preview SSE (T073a), and a "freeze composition" action calling the US4 endpoints (FR-018/019/020/022). (Covers U-A.)
- [ ] T080b [US5] **Design-system & accessibility conformance** (Constitution Article VIII + `DESIGN.md`): all content forge screens MUST reference `tokens.css`/`components.css`/`archetypes.css`/`utilities.css` (no raw colors/spacing/type values), integrate the theme system (`data-skin`/`data-theme`), be responsive across breakpoints, meet WCAG AA contrast, and honor `prefers-reduced-motion` + `prefers-reduced-transparency`. Verify against `DESIGN.md`. **Execute via the `visual-engineering` category + `frontend-ui-ux` skill.** (Covers U-C.)

**Checkpoint**: SC-007, SC-008 satisfied.

---

## Phase 9: User Story 6 - Import from external/local sources (P2)

**Goal**: Kick + monitor import jobs that route content through the standard gates.

**Independent Test**: start an import job, watch progress to completion, confirm imported
content passed gates and appears in the corpus.

### Tests

- [ ] T083 [P] [US6] Integration test import job routes through gates → present in corpus in `tests/integration/content/test_import_job.py`.
- [ ] T084 [P] [US6] Integration test import failure recorded/surfaced in `tests/integration/content/test_import_failure.py`.

### Implementation

- [ ] T085 [US6] Implement `ImportService` in `anvil/services/content/import_service.py`: `start` (opens an IngestSession, streams source content, accepts through gates) + `status` (FR-032/033).
- [ ] T086 [US6] Add endpoints POST `/content/imports`, GET `/content/imports/{id}`, SSE `GET /content/stream/import` + `ImportStart`/`ImportJobOut` schemas.
- [ ] T087 [P] [US6] Add the Import Console view to the content hub (mount point from T080) + live progress via the import-progress SSE; conform to the design system (T080b). Build via `visual-engineering` + `frontend-ui-ux`.

**Checkpoint**: US6 import works through the standard validation path.

---

## Phase 10: User Story 7 - Checkout locks (P3)

**Goal**: Advisory checkout locks + board.

**Independent Test**: acquire lock → appears on board with holder/time → second curator sees
held → release clears it.

### Tests

- [ ] T088 [P] [US7] Integration test acquire/release/board in `tests/integration/content/test_locks.py`.

### Implementation

- [ ] T089 [US7] Implement `LockService` in `anvil/services/content/lock_service.py` (acquire/release/list_active) (FR-034).
- [ ] T090 [US7] Add endpoints POST/DELETE/GET `/content/locks`, SSE `GET /content/stream/locks` + `LockBody`/`LockOut` schemas (FR-035).
- [ ] T091 [P] [US7] Add the Checkout Board view to the content hub (mount point from T080) + live updates via the lock-events SSE; conform to the design system (T080b). Build via `visual-engineering` + `frontend-ui-ux`.

**Checkpoint**: US7 advisory locks work.

---

## Phase 11: User Story 9 - SaaS managed-component visibility (P2) — DEFERRED (separate delivery)

**Goal**: Content repository as a fully-managed, visible component in SaaS mode (LakeFS-backed).

> **Out of scope for this (local-first) delivery — see plan.md Phase F.** Listed for
> traceability; requires a separate ADR + `anvil/_saas/` scaffolding. Do NOT implement now.
> **The SaaS requirements are now captured in `specs/014-saas-architecture/spec.md`
> (FR-062–FR-067, SC-021, AD-17) and ADR-030 (AD-17) — this feature's SaaS work is
> delivered as part of the 014 SaaS body of work.**

- [ ] T092 [US9] (DEFERRED → 014) Implement `LakeFSVersionedContentStore` in `anvil/_saas/implementations/lakefs_versioned_content_store.py` behind the same `VersionedContentStore` ABC (014 FR-062/FR-063).
- [ ] T093 [US9] (DEFERRED → 014) Surface the content repository as a managed, org-isolated component with status/health in the SaaS services/config surface (016 FR-041; 014 FR-062/FR-063, SC-021); enforce producer + management authz at the app layer, NOT LakeFS OSS RBAC (014 FR-064); keep validation in-process, not LakeFS hooks (014 FR-065).
- [ ] T094 [US9] (DEFERRED → 014) Optional SQLAdmin `/admin` back-office (async, `add_view` at construction, auth-guarded) in `anvil/_saas/` (016 FR-037; 014 FR-067).

---

## Phase 12: Polish & Cross-Cutting Concerns

- [ ] T095 [P] Write `docs/vault/Decisions/ADR-033-content-repository-substrate.md` recording the LakeFS-vs-pure-Python-local decision + `VersionedContentStore` boundary; include a **"SaaS integration hand-off"** section cross-linking `specs/014-saas-architecture` (FR-062–067, SC-021) and ADR-030 AD-17 (LakeFS SaaS substrate, app-level RBAC, in-process validation, manifest-digest parity). Add ADR-033 to the `docs/vault/Decisions/README.md` index. (Constitution + plan require an ADR.)
- [ ] T096 Implement `AdvisoryService` in `anvil/services/content/advisory_service.py`: post-acceptance near-dup detection (flags only), derived-state refresh/re-tokenize, acceptance stats + lineage recording — non-blocking (FR-015, FR-026a). Record the chosen near-duplicate algorithm (e.g., shingled MinHash/Jaccard threshold) in ADR-033 (T095).
- [ ] T097 Implement retention/GC of unreferenced blobs + failed-session staging cleanup (reachable-ref walk; never collect run-referenced/tagged versions) (FR-024/025, SC-002).
- [ ] T097a [P] Retention/GC test in `tests/integration/content/test_retention_gc.py`: a run-referenced version AND its content-addressed blobs survive a GC cycle (zero loss), while unreferenced blobs + expired failed-session staging are collected (SC-002, FR-024/025).
- [ ] T098 [P] Add `data/content/` to `.gitignore` and to the Docker/compose volume + packaging notes (mirrors `mlruns/`, `data/`).
- [ ] T098a [P] Relabel the legacy directory-based corpus surface as "Directory Corpus (deprecated)" wherever it remains present (existing corpora templates/nav/labels) to distinguish it from the canonical Corpus (FR-038b).
- [ ] T099 Run quickstart.md end-to-end and check off its acceptance boxes (SC-001/002/003/004/005/006/010/012). Include a UI pass: verify the content hub renders the Library/Timeline/Lineage/Injection Monitor/Composer/Import Console/Checkout Board screens, is responsive, theme-switches cleanly (`data-skin`/`data-theme`), meets WCAG AA contrast, and honors reduced-motion (Article VIII / DESIGN.md).
- [ ] T100 Run `make lint`, `make typecheck` (mypy strict), `make test`; raise `fail_under` coverage to the new measured level (Article IV ratchet); ensure all gates pass.
- [ ] T101 [P] Vault enrichment: session log + any Discovery notes in `docs/vault/`; run `make vault-audit` (0 errors).

---

## Dependencies & Execution Order

### Phase dependencies
- **Setup (P1)** → no deps.
- **Foundational (P2)** → depends on Setup; **BLOCKS all stories**.
- **US1 (P3)** → depends on Foundational. **MVP.**
- **US8 (P4)** → depends on US1 (validates the transparent local experience of US1).
- **US2 (P5)**, **US3 (P6)** → depend on US1 (extend the store/ingestion). US3 builds on US2's accept path.
- **US4 (P7)** → depends on US1 (versions) + US3 (validated content).
- **US5 (P8)** → depends on US1–US4 (observes their data).
- **US6 (P9)** → depends on US2/US3 (reuses ingestion+gates).
- **US7 (P10)** → depends only on Foundational (independent; can run any time after P2).
- **US9 (P11)** → DEFERRED (separate delivery).
- **Polish (P12)** → after desired stories complete.

### Within each story
TDD: tests (marked) written and FAILING before implementation. Models → store → services →
endpoints → UI. Repository-only DB access (Article VII). All async (Article V).

### Parallel opportunities
- Setup: T002–T005, T007 in parallel.
- Foundational: value types T008–T012 [P]; all 10 models T014–T023 [P]; all 7 repos T026–T032 [P] (after models). T024/T025 (migration) after models; T033/T034 after repos.
- Within each story, all `[P]` test tasks run together; `[P]` template/UI tasks parallel to service tasks in different files.
- US7 can be built in parallel with US2–US6 by a second developer (independent).

---

## Parallel Example: Foundational models

```bash
# After T013 (ABC) + value types, create all ORM models in parallel:
Task: T014 ContentSource model
Task: T015 ContentCorpus model
Task: T016 ContentVersion model
Task: T017 ContentEntry model
Task: T018 ContentBlob model
Task: T019 ContentTag model
Task: T020 IngestSession model
Task: T021 ImportJob model
Task: T022 CheckoutLock model
Task: T023 VersionRunRef model
```

---

## Implementation Strategy

### MVP First (User Story 1)
1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & VALIDATE** (quickstart 1–6; SC-001).
Ship the reproducibility core. Local mode needs no new service/dependency.

### Incremental delivery
US1 (MVP) → US8 (validate transparency) → US2 (isolation) → US3 (full gates) → US4 (composition)
→ US5 (visibility) → US6 (import) → US7 (locks). Each is an independently testable increment.
US9/SaaS (LakeFS) is a **separate later delivery** (plan Phase F) gated by its own ADR.

### Notes
- [P] = different files, no incomplete deps. [Story] maps to spec user stories.
- Tests must fail before implementing. Commit per task or logical group (only when asked).
- One class per file; StrEnum over magic strings; Pydantic BaseModel for value/HTTP types.
- The single Alembic migration (T025) creates all tables; tables for later stories are
  harmless until used.
- **Visual/frontend tasks** (T080, T080a, T080b, T082a, the T087 Import Console view, and
  the T091 Checkout Board view) MUST be delegated to the **`visual-engineering`** category
  with the **`frontend-ui-ux`** skill and conform to `DESIGN.md` (Constitution Article VIII).
  Do not hand-build UI ad hoc.
- **MVP is intentionally API-first** (U-E): Phases 1–3 (US1) deliver the reproducibility
  flow via the API (quickstart uses curl); the browser experience lands in US5 (Phase 8).
  This is a deliberate sequencing decision, not a gap.
- **All 8 design-doc forge screens are covered**: Corpus Library (T080), Version Timeline
  (T080), Lineage (T080), Injection Monitor (T079/T082), Ensemble Composer (T082a/T073a),
  Import Console (T087), Checkout Board (T091); Back-office/SQLAdmin is the SaaS-deferred
  `/admin` (T094). All four SSE streams have tasks: injection (T079), composition (T073a),
  import (T086), locks (T090).
