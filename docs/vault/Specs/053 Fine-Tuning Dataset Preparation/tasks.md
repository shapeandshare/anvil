# Tasks: Fine-Tuning Dataset Preparation

**Input**: Design documents from `docs/vault/Specs/053 Fine-Tuning Dataset Preparation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

**Tests**: TDD is **mandatory** (Constitution Article IV). Every implementation task has a unit test
written FIRST that must FAIL before implementation (Red-Green-Refactor). Coverage for new modules MUST
reach 100% (the project coverage `fail_under` ratchet may only increase, never decrease).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the NMRG baseline and create new package structure.

- [X] T001 Run `make test` to establish the NMRG baseline (record any pre-existing failures so SC-004 can prove "pre-existing tests pass unmodified")
- [X] T002 Create `anvil/services/finetuning/` domain sub-package with bare `__init__.py` in `anvil/services/finetuning/__init__.py`
- [X] T003 [P] Create `anvil/services/_shared/fine_tune_dataset_status.py` with `FineTuneDatasetStatus` StrEnum (`PREPARING`, `READY`, `FAILED`)
- [X] T004 [P] Create `anvil/services/_shared/chat_template_status.py` with `ChatTemplateStatus` StrEnum (`ACTIVE`, `DEPRECATED`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema, ORM models, and repositories. **TDD**: repository tests written before repository implementations.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Create Alembic migration `anvil/_resources/migrations/versions/006_add_fine_tune_datasets.py` — creates `chat_templates` and `fine_tune_datasets` tables with columns, FKs, and indexes per `data-model.md`
- [X] T006 [P] Create `ChatTemplate` ORM model in `anvil/db/models/chat_template.py`
- [X] T007 [P] Create `FineTuneDataset` ORM model in `anvil/db/models/fine_tune_dataset.py`
- [X] T008 [P] **(test-first, must FAIL)** Unit tests for `ChatTemplateRepository` (CRUD, unique-name, get-by-name/family) in `tests/unit/db/test_chat_templates.py` — FAIL confirmed → PASS after T010
- [X] T009 [P] **(test-first, must FAIL)** Unit tests for `FineTuneDatasetRepository` (CRUD, `get_active_for_dataset`, status/dataset/model filters, `update_status`) in `tests/unit/db/test_fine_tune_datasets.py` — FAIL confirmed → PASS after T011
- [X] T010 [P] Implement `ChatTemplateRepository` in `anvil/db/repositories/chat_templates.py` — make T008 pass
- [X] T011 [P] Implement `FineTuneDatasetRepository` in `anvil/db/repositories/fine_tune_datasets.py` (incl. `get_active_for_dataset` for the one-active-preparation rule) — make T009 pass

**Checkpoint**: Schema + models + repositories tested and green — user story implementation can begin.

---

## Phase 3: User Story 1 — Learner Prepares an Instruction Dataset (Priority: P1) 🎯 MVP

**Goal**: A learner turns raw instruction examples (JSONL) into prompt→response pairs formatted with the target model's chat template, tracked as a `FineTuneDataset` via the existing dataset governance (005), with deterministic template resolution, async job status, and skip-and-continue error reporting.

**Independent Test**: Submit a small JSONL with 3 valid SFT examples to dataset curation (005), POST `/v1/fine-tune-datasets`, poll until `ready`, verify rendered records + recorded template choice. Submit 2 valid + 1 malformed → `succeeded=2, failed=1`. Omit explicit template against a template-less model → labeled default + warning (SC-006).

### Tests for User Story 1 (TDD — write FIRST, ensure they FAIL) ⚠️

> **NOTE**: Write these unit tests before the implementation tasks they cover. Run them to confirm RED, then implement to GREEN.

- [ ] T012 [P] [US1] Unit tests for `PreparationResult` (construction, counts, serialization to summary JSON) in `tests/unit/services/finetuning/test_preparation_result.py`
- [ ] T013 [P] [US1] Unit tests for `ChatTemplateService` — CRUD, validation (unique name, non-empty `template_string`, valid `tokenizer_family`), and default-template derivation (derive from model tokenizer; built-in default + warning when absent; persist labeled default) in `tests/unit/services/finetuning/test_chat_template_service.py`
- [ ] T014 [US1] Unit tests for dataset preparation logic — JSONL validation (SFT `instruction`/`response`, `messages` array with roles, preference `chosen`/`rejected`; valid + invalid cases) in `tests/unit/services/finetuning/test_dataset_preparation_service.py`
- [ ] T015 [US1] Unit tests for template resolution + rendering — FR-005 a/b/c order, never-guess, choice recorded; SFT render, preference `{prompt, chosen, rejected}` render, tokenizer-family mismatch → fail-fast, tokenizer check unavailable → warning (FR-003) — append to `tests/unit/services/finetuning/test_dataset_preparation_service.py`
- [ ] T016 [US1] Unit tests for skip-and-continue batch processing — correct `total`/`succeeded`/`failed` on mixed input, empty input → `total=0` completes `ready`, configurable batch size — append to `tests/unit/services/finetuning/test_dataset_preparation_service.py`
- [ ] T017 [P] [US1] Unit tests for preparation job runner — status transitions (`preparing → ready | failed`), summary persisted, `CurationOperation(operation_type="prepare")` audit written, isolated-session behavior — in `tests/unit/services/finetuning/test_preparation_job.py`

### Implementation — ChatTemplate Service (make T012–T013 green)

- [ ] T018 [P] [US1] Create `PreparationResult` value object in `anvil/services/finetuning/preparation_result.py` (fields: `job_id`, `total`, `succeeded`, `failed`, `errors: list[dict]`)
- [ ] T019 [P] [US1] Create `ChatTemplateService` (CRUD + validation) in `anvil/services/finetuning/chat_template_service.py`
- [ ] T020 [US1] Implement default-template derivation in `anvil/services/finetuning/chat_template_service.py` — read base model's template from its attached tokenizer (FT-AD-3) on first use; persist labeled default if absent (covers pre-existing models); tokenizer access behind `[finetune]`, absence degrades to built-in default + warning (FR-003, FR-005b) (depends on T019)
- [ ] T021 [P] [US1] Create Pydantic schemas in `anvil/api/v1/schemas_fine_tune_datasets.py`: `CreateChatTemplateBody`, `FineTuneDatasetResponse`, `CreateFineTuneDatasetBody` (with **optional** `chat_template_id` per FR-005), `JobStatusResponse`, `PreparationSummary`
- [ ] T022 [US1] Create chat template API routes in `anvil/api/v1/fine_tune_datasets.py` — `POST /v1/chat-templates`, `GET /v1/chat-templates` (filters: `tokenizer_family`, `status`) (depends on T019, T021)

### Implementation — Dataset Preparation Service (make T014–T016 green)

- [ ] T023 [P] [US1] Implement JSONL record validation for all shapes (FR-002) in `anvil/services/finetuning/dataset_preparation_service.py`
- [ ] T024 [US1] Implement deterministic chat template resolution (FR-005 a→b→c, never guess, record choice on dataset per FR-001) in `anvil/services/finetuning/dataset_preparation_service.py` (depends on T019, T020)
- [ ] T025 [US1] Implement chat template rendering — apply resolved template + `TokenizerFactory.create_tokenizer()` for tokenizer-dependent checks (mismatch → fail-fast; check unavailable → warn) in `anvil/services/finetuning/dataset_preparation_service.py` (depends on T024)
- [ ] T026 [US1] Implement skip-and-continue batch processing — configurable batches (default 1000), per record-type rendering, per-record error collection, `total`/`succeeded`/`failed` accumulation, empty input → `ready` `total=0` in `anvil/services/finetuning/dataset_preparation_service.py` (depends on T023, T025)
- [ ] T027 [US1] Implement preparation job runner in `anvil/services/finetuning/preparation_job.py` — isolated `AsyncSession`, status transitions, summary writing, `CurationOperation` audit (make T017 green) (depends on T026, T018)
- [ ] T028 [US1] Wire `ChatTemplateService` and `DatasetPreparationService` into `AnvilWorkbench` in `anvil/workbench.py` — lazy `@property` accessors + `fine_tune_dataset_preparation(dataset_id)` factory (depends on T019, T027)

### Implementation — API Endpoints (Async Job Pattern)

- [ ] T029 [US1] Implement `POST /v1/fine-tune-datasets` — validate inputs, **enforce one active preparation per source dataset (reject concurrent with `409`)**, create record, fire `asyncio.create_task()` worker with isolated session, return `202` `{job_id, status: "preparing"}` (depends on T021, T027, T028)
- [ ] T030 [US1] Implement `GET /v1/fine-tune-datasets/jobs/{job_id}/status` — status, timestamps, summary report per contracts/README.md
- [ ] T031 [US1] Implement `GET /v1/fine-tune-datasets/{id}` — prepared dataset metadata incl. resolved template choice
- [ ] T032 [US1] Implement `GET /v1/fine-tune-datasets` — list with filters (`dataset_id`, `status`, `base_model_ref`)
- [ ] T033 [US1] Implement `POST /v1/fine-tune-datasets/{id}/retry` — new preparation job for a failed `FineTuneDataset`
- [ ] T034 [US1] Register routes in `anvil/api/v1/router.py` — `from .fine_tune_datasets import router as fine_tune_datasets_router` + `router.include_router(...)` (depends on T022, T029–T033)

### e2e Tests (HTTP API level — system tests per Article IV)

- [ ] T035 [P] [US1] e2e happy path: create chat template → create fine-tune-dataset → poll until `ready` → verify metadata + recorded template choice, in `tests/e2e/test_fine_tune_datasets.py`
- [ ] T036 [P] [US1] e2e skip-and-continue: mixed valid/invalid records → `succeeded=2, failed=1` (SC-005), in `tests/e2e/test_fine_tune_datasets.py`
- [ ] T037 [P] [US1] e2e error/conflict cases: invalid `dataset_id`, invalid `chat_template_id`, retry on non-failed status, **concurrent preparation → `409`**, in `tests/e2e/test_fine_tune_datasets.py`
- [ ] T038 [P] [US1] e2e template resolution + empty input: template-less model → labeled default + warning + choice recorded (SC-006); zero-record input → `ready` `total=0`, in `tests/e2e/test_fine_tune_datasets.py`

**Checkpoint**: User Story 1 fully functional and fully tested (unit + e2e). Deterministic template resolution, skip-and-continue, concurrency guard, async job status.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Coverage verification, regression gate, documentation.

- [ ] T039 Run `pytest --cov=anvil --cov-report=term-missing` — verify new modules (`anvil/services/finetuning/*`, `anvil/db/models/chat_template.py`, `anvil/db/models/fine_tune_dataset.py`, `anvil/db/repositories/chat_templates.py`, `anvil/db/repositories/fine_tune_datasets.py`, `anvil/api/v1/fine_tune_datasets.py`) reach 100%; raise the coverage `fail_under` ratchet if the measured baseline increased (never lower it)
- [ ] T040 Run `make lint`, `make typecheck`, `make test` — full suite green; confirm NMRG vs T001 baseline (pre-existing tests pass unmodified, base install unaffected — SC-004)
- [ ] T041 Update `docs/ux-rules.md` or related docs if any UI components were added/changed (N/A for this spec — all API/logic)
- [ ] T042 **[UX compliance gate]**: run `make ux-lint` on any changed UI/template/CSS files (N/A — no frontend changes in this spec)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 baseline first; T002–T004 follow. No external dependencies.
- **Foundational (Phase 2)**: Depends on Setup. TDD: T008/T009 (tests) before T010/T011 (impl). BLOCKS all user story work.
- **User Story 1 (Phase 3)**: Depends on Foundational.
  - Tests T012–T017 written FIRST (RED), then implementation T018–T034 brings them GREEN.
  - e2e T035–T038 after routes registered (T034).
- **Polish (Phase 4)**: Depends on all prior tasks.

### Within User Story 1 (TDD order)

| Step | Description | Depends On |
|------|-------------|------------|
| 1 | T012–T017 — write all unit tests (RED) | Phase 2 done |
| 2 | T018 — PreparationResult | T012 |
| 3 | T019 — ChatTemplateService | T013 |
| 4 | T020 — Default-template derivation | T019 |
| 5 | T021 — Pydantic schemas | nothing |
| 6 | T022 — Chat template routes | T019, T021 |
| 7 | T023 — JSONL validation | T014 |
| 8 | T024 — Template resolution (FR-005) | T019, T020 |
| 9 | T025 — Rendering + tokenizer checks | T024 |
| 10 | T026 — Skip-and-continue batch processing | T023, T025 |
| 11 | T027 — Job runner | T026, T018 |
| 12 | T028 — Workbench wiring | T019, T027 |
| 13 | T029 — POST endpoint + concurrency 409 | T021, T027, T028 |
| 14 | T030–T033 — remaining endpoints | T021, T027, T028 |
| 15 | T034 — Router registration | T022, T029–T033 |
| 16 | T035–T038 — e2e tests | T034 |

### Parallel Opportunities

- **Phase 1**: T003 and T004 in parallel (independent enum files)
- **Phase 2**: T006/T007 in parallel (ORM models); T008/T009 in parallel (repo tests); T010/T011 in parallel (repo impls)
- **Phase 3 test-writing (RED)**: T012, T013, T017 in parallel (distinct files). T014–T016 share `test_dataset_preparation_service.py` → sequential among themselves
- **Phase 3 impl, first wave**: T018, T019, T021, T023 in parallel (distinct files)
- **Phase 3 impl, preparation service**: T024 → T025 → T026 are sequential (same file `dataset_preparation_service.py`)
- **Phase 3 e2e**: T035–T038 in parallel (independent test functions in one file)

### Parallel Example: User Story 1 — Test-Writing Wave (RED)

```bash
# Write these failing unit tests simultaneously (distinct files):
Task: "Unit tests for PreparationResult in tests/unit/services/finetuning/test_preparation_result.py"
Task: "Unit tests for ChatTemplateService in tests/unit/services/finetuning/test_chat_template_service.py"
Task: "Unit tests for preparation job runner in tests/unit/services/finetuning/test_preparation_job.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (baseline + scaffolding)
2. Phase 2: Foundational (TDD: repo tests → repos)
3. Phase 3: write unit tests (RED) → implement to GREEN → e2e
4. **STOP and VALIDATE**: full unit + e2e suite green
5. Phase 4: coverage verification + regression gate

### Incremental Delivery

1. Setup + Foundational → tested schema/repos
2. ChatTemplate service + default derivation (T012–T013, T018–T022) → templates + resolution
3. Core preparation logic (T014–T016, T023–T028) → preparation at service level, fully unit-tested
4. API endpoints (T029–T034) → feature over HTTP
5. e2e + coverage (T035–T039) → validated end-to-end at 100% coverage

---

## Requirement → Task Coverage

| Requirement | Implementation | Tests |
|-------------|----------------|-------|
| FR-034 (dataset preparation) | T023, T025, T026, T027, T029 | T014–T016, T035 |
| FR-001 (record template/model) | T005, T007, T024, T028 | T009, T015, T035 |
| FR-002 (validate all shapes + skip) | T023, T026 | T014, T016, T036 |
| FR-003 (no heavy deps; degrade to warning) | T020, T025 | T013, T015 |
| FR-004 (job status API) | T003, T005, T029, T030, T033 | T017, T035, T037 |
| FR-005 (deterministic template resolution) | T020, T024 | T013, T015, T038 |
| SC-005 (mixed valid/invalid summary) | T026 | T016, T036 |
| SC-006 (default template + warning) | T020, T024 | T013, T015, T038 |
| Concurrency edge case (409) | T011, T029 | T009, T037 |
| Empty-input edge case | T026 | T016, T038 |
| SC-004 (NMRG) | — | T001, T040 |
| 100% coverage (Article IV) | all | T008, T009, T012–T017, T035–T038, T039 |

---

## Notes

- TDD is mandatory: tests in T008/T009 and T012–T017 are written FIRST and must FAIL before their implementations
- [P] tasks = different files, no dependencies
- [US1] label maps task to User Story 1
- Verify the API returns `202` (not `200`) for async job submission
- T014–T016 share `test_dataset_preparation_service.py`; T024–T026 share `dataset_preparation_service.py` — do NOT mark those groups [P] together
- Coverage `fail_under` may only increase (Constitution Article IV) — T039 ratchets, never lowers
- Follow existing patterns:
  - `ModelImportJob` async orchestration (`anvil/db/models/model_import_job.py`, `anvil/api/v1/models.py`)
  - `DatasetService` CRUD (`anvil/services/datasets/datasets.py`)
  - `SampleRepository.add_bulk()` batch inserts (`anvil/db/repositories/curation.py`)
  - `CurationOperation` audit trail (`anvil/db/models/curation_operation.py`)
  - `TokenizerFactory.create_tokenizer()` tokenizer access (`anvil/services/inference/tokenizer_factory.py`)
  - `client` fixture for e2e (`tests/conftest.py`)