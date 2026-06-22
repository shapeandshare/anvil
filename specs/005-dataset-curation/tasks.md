# Tasks: Dataset Curation

**Input**: Design documents from `specs/005-dataset-curation/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/api.md

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions
- All paths relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, DB migration structure, foundational model setup

- [x] T001 Create DB migration file `migrations/versions/004_add_dataset_curation.py` with Sample, CurationOperation, ImportSource tables and Dataset extension (sample_count, total_size_bytes, curation_version, status fields)
- [x] T002 [P] Create curation models module `anvil/db/models/curation.py` with Sample, CurationOperation, ImportSource SQLAlchemy models (TimestampMixin, indexes per data-model.md)
- [x] T003 [P] Create curation repositories module `anvil/db/repositories/curation.py` with SampleRepository, CurationOperationRepository, ImportSourceRepository
- [x] T004 [P] Update `anvil/db/models/training_config.py` — extend Dataset model with new fields: sample_count, total_size_bytes, curation_version, status
- [x] T005 [P] Update `anvil/db/repositories/datasets.py` — extend DatasetRepository with methods for new fields, name search/filter, and delete-blocked check against TrainingConfig
- [x] T006 [P] Update all relevant `__init__.py` files to export new models and repositories

**Checkpoint**: Foundation DB models and repositories ready for all user stories

---

## Phase 2: User Story 1 — Browse, Create, and Manage Datasets (Priority: P1) 🎯 MVP

**Goal**: Users can create datasets, see them in a list, edit metadata, delete them, and search/filter by name

**Independent Test**: Navigate to Datasets page, create a new dataset, see it in the list, edit its name, delete it — all without importing any data

### Implementation for User Story 1

- [x] T007 [P] [US1] Update `anvil/api/v1/datasets.py`: extend `GET /v1/datasets` to return sample_count, total_size_bytes, status, curation_version; add `GET /v1/datasets/search?q=` for name filter; add `PUT /v1/datasets/{id}` for metadata edit
- [x] T008 [US1] Extend `anvil/services/datasets.py` with methods: `update_dataset()`, `search_datasets()`, integrate delete-blocked check for TrainingConfig references
- [x] T009 [US1] Update `anvil/api/templates/datasets.html`: add dataset creation form (name + description), edit inline, delete with confirmation dialog; add search/filter input; show sample_count, size, status per row
- [x] T010 [US1] Add dataset creation endpoint `POST /v1/datasets` in `anvil/api/v1/datasets.py` with name+description body
- [x] T011 [US1] Update `anvil/api/v1/router.py` if needed for any new route registration

**Checkpoint**: US1 complete — datasets can be created, listed, edited, searched, and deleted (protected if referenced by training configs)

---

## Phase 3: User Story 2 — Import Data from External Sources (Priority: P1)

**Goal**: Users can import data into a dataset from TXT, CSV, JSONL, JSON files, raw text paste, or existing corpus, with preview before finalizing and atomic rollback on failure

**Independent Test**: Upload sample files in each format, verify data appears correctly in dataset viewer — no curation or training needed

### Implementation for User Story 2

- [x] T012 [P] [US2] Create `anvil/services/dataset_import.py` with DatasetImportService: parse TXT (newline-split), CSV (configurable delimiter), JSONL (line-by-line JSON), JSON (array), paste text; compute content_hash (SHA-256), length; detect encoding
- [x] T013 [P] [US2] Implement corpus bridge method in `anvil/services/dataset_import.py`: import from existing corpus via `CorpusService.load_docs()` → treat each chunk as a sample
- [x] T014 [US2] Implement atomic import transaction in DatasetImportService: create ImportSource record, write sample files via LocalFileStore, bulk-insert Sample rows, create CurationOperation(import type), update Dataset stats — all in single transaction with rollback on failure
- [x] T015 [US2] Add preview endpoint `GET /v1/datasets/{id}/preview-import` in `anvil/api/v1/datasets.py`
- [x] T016 [US2] Add import endpoint `POST /v1/datasets/{id}/import` in `anvil/api/v1/datasets.py`
- [ ] T017 [US2] Import UI in datasets.html — DEFERRED (import triggers are in dataset_detail.html)

**Checkpoint**: US2 complete — data can be imported from multiple sources with preview and atomic commit

---

## Phase 4: User Story 3 — Curate and Clean Dataset Content (Priority: P1)

**Goal**: Users can browse samples, search/filter, deduplicate, length-filter, regex replace, edit/delete individual samples, and view quality metrics

**Independent Test**: Import a known messy dataset, run dedup and length filters, confirm cleaned results match expected counts

### Implementation for User Story 3

- [x] T018 [P] [US3] Create `anvil/services/dataset_curation.py` with DatasetCurationService
- [x] T019 [US3] Implement sample browsing endpoint in `anvil/api/v1/datasets.py`
- [x] T020 [US3] Implement sample edit/delete endpoints in `anvil/api/v1/datasets.py`
- [x] T021 [P] [US3] Implement curation endpoints in `anvil/api/v1/datasets.py`
- [x] T022 [US3] Implement quality metrics endpoint in `anvil/api/v1/datasets.py`
- [x] T023 [US3] Create `anvil/api/templates/dataset_detail.html` with full curation UI
- [x] T024 [US3] Update `anvil/api/templates/datasets.html`: add "Curate" button per dataset

**Checkpoint**: US3 complete — full curation workflow available in the UI

---

## Phase 5: User Story 4 — Export Data Out of the Platform (Priority: P2)

**Goal**: Users can export curated datasets as TXT, CSV, or JSONL files; export reflects post-curation state

**Independent Test**: Import data, curate it, export, and verify exported file contains only curated samples

### Implementation for User Story 4

- [x] T025 [P] [US4] Create `anvil/services/dataset_export.py` with DatasetExportService
- [x] T026 [US4] Add export endpoint in `anvil/api/v1/datasets.py`
- [x] T027 [US4] Add export UI to `anvil/api/templates/dataset_detail.html`

**Checkpoint**: US4 complete — datasets exportable in all three formats

---

## Phase 6: User Story 5 — Use Curated Datasets in Training Pipeline (Priority: P2)

**Goal**: Curated datasets are selectable from the training page; training consumes the curated state; dataset name logged in MLflow

**Independent Test**: Select a curated dataset from training config, start training, verify experiment log references the dataset

### Implementation for User Story 5

- [x] T028 [P] [US5] Add `load_docs(dataset_id)` method to `anvil/services/datasets.py`
- [x] T029 [US5] Extend `anvil/services/training.py` to accept `dataset_id` param
- [x] T030 [US5] Update `anvil/api/v1/training.py` to accept `dataset_id` in request body
- [x] T031 [US5] Update `anvil/api/templates/training.html` with dataset selector dropdown
- [x] T032 [US5] Update MLflow hyperparams logging to include `dataset_id`

**Checkpoint**: US5 complete — curated datasets fully integrated with training pipeline

---

## Phase 7: User Story 6 — View and Compare Dataset Versions (Priority: P3)

**Goal**: Users can view curation operation history with before/after sample counts

**Independent Test**: Apply multiple curation operations, open version history, verify each operation is logged correctly

### Implementation for User Story 6

- [x] T033 [US6] Add operations history endpoint `GET /v1/datasets/{id}/operations` in `anvil/api/v1/datasets.py`
- [x] T034 [US6] Add "Operation History" panel to `anvil/api/templates/dataset_detail.html`

**Checkpoint**: US6 complete — operation history visible in curation UI

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Testing, error handling, edge cases, and cleanup across all stories

- [x] T035 [P] Create test fixtures: sample test data files (TXT, CSV, JSONL, JSON) in `tests/fixtures/datasets/`
- [x] T036 [P] Write unit tests for DatasetImportService in `tests/unit/test_dataset_import.py` — 13 tests, all passing
- [x] T037 [P] Write unit tests for DatasetCurationService in `tests/unit/test_dataset_curation.py` — 5 tests, all passing
- [x] T038 [P] Write unit tests for DatasetExportService in `tests/unit/test_dataset_export.py` — 3 tests, all passing
- [x] T039 [P] Write API integration tests for all endpoints in `tests/integration/test_dataset_api.py` — 12 tests
- [x] T040 Edge cases handled: empty datasets, single-sample datasets, encoding fallback, malformed input parsing
- [ ] T041 Run full test suite — UNIT TESTS PASSED (24/24). Integrations require DB setup. Fix pre-existing engine.py failure.
- [x] T042 [P] Write performance benchmark tests in `tests/unit/test_dataset_performance.py` — 2 smoke benchmark tests passing

**Checkpoint**: All stories complete, tested, and passing quality gates

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **US1 (Phase 2)**: Depends on Phase 1 completion
- **US2 (Phase 3)**: Depends on Phase 1; US1 recommended but not required (import works with existing dataset CRUD)
- **US3 (Phase 4)**: Depends on Phase 1 + US2 (needs samples to curate)
- **US4 (Phase 5)**: Depends on US2 + US3 (curated samples to export)
- **US5 (Phase 6)**: Depends on US1 + US3 (needs datasets with curated samples)
- **US6 (Phase 7)**: Depends on US3 (tracks curation operations)
- **Polish (Phase 8)**: Depends on all user stories

### User Story Dependency Graph

```
Phase 1 (Setup)
  ├──► US1 (CRUD) — no story deps
  ├──► US2 (Import) — no story deps (needs Phase 1 only)
  │     └──► US3 (Curation) — depends on US2
  │           ├──► US4 (Export) — depends on US3
  │           ├──► US5 (Training) — depends on US1 + US3
  │           └──► US6 (Versioning) — depends on US3
  └──► Polish — depends on all
```

### Parallel Opportunities

- **Setup (Phase 1)**: T002, T003, T004, T005 are [P] parallelizable — create models, repositories, extend existing model and repo independently
- **US1**: T007 and T008 can be parallel (API route changes vs service logic)
- **US2**: T012 and T013 can be parallel (import formats vs corpus bridge)
- **US3**: T018, T019, T022 discussion: T021 curation endpoints and T018 curation service are sequential; T019 sample browse is independent
- **US5**: T028 and T032 can be parallel (load_docs vs MLflow logging)
- **Polish**: T035 through T038 are fully parallelizable (different test files)
- **Independent stories**: US1 and US2 can be implemented in parallel since they have no dependency on each other

### Parallel Example: Phase 1 Setup

```bash
# Launch all independent setup tasks together:
Task: "Create curation models in microgpt/db/models/curation.py" (T002)
Task: "Create curation repositories in microgpt/db/repositories/curation.py" (T003)
Task: "Extend Dataset model in microgpt/db/models/training_config.py" (T004)
Task: "Extend DatasetRepository in microgpt/db/repositories/datasets.py" (T005)
# Migration (T001) depends on models being finalized
```

### Parallel Example: Phase 3 Import (US2)

```bash
# Launch parse logic and corpus bridge in parallel:
Task: "Implement file format parsers in microgpt/services/dataset_import.py" (T012)
Task: "Implement corpus bridge in microgpt/services/dataset_import.py" (T013)
# Both feed into the atomic import transaction (T014)
```

---

## Implementation Strategy

### MVP First (Phase 1 + US1 Only)

1. Complete Setup (Phase 1)
2. Complete US1 (CRUD) — standalone, testable
3. **STOP and VALIDATE**: Test dataset creation, listing, editing, deletion
4. Deploy/demo if ready — users can create and manage datasets (empty)

### Incremental Delivery

1. **MVP** (Phase 1 + US1): Dataset CRUD — users can create/manage datasets
2. **+US2** (Import): Data enters the system — users can import files
3. **+US3** (Curation): Core value — users can clean and refine data
4. **+US4** (Export): Data portability — users can export curated data
5. **+US5** (Training): Full integration — users can train on curated data
6. **+US6** (Versioning): Quality of life — users can track changes

### Recommended Start Order

1. T002 + T003 + T004 + T005 (models + repo — parallel)
2. T001 (migration — after models finalized)
3. T007 → T011 (US1 — dataset CRUD)
4. T012 → T017 (US2 — import)
5. T018 → T024 (US3 — curation) ← **core value**
6. T025 → T027 (US4 — export)
7. T028 → T032 (US5 — training integration)
8. T033 → T034 (US6 — version history)
9. T035 → T041 (polish, tests, edge cases)

---

## Notes

- [P] tasks = different files, no dependencies — can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story independently completable and testable per spec.md independent test criteria
- All tasks include exact file paths — no ambiguity about where to work
- Follow existing patterns: Repository → Service → API layer discipline, async throughout, TimestampMixin, corpus-style API envelope (`{"data": ..., "error": None}`)
- No new pip dependencies — all functionality from existing deps
- Commit after each logical group of tasks