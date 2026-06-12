# Tasks: Directory Corpus Ingestion

**Input**: Design documents from `specs/002-directory-corpus-ingestion/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included per Constitution Article IV (TDD Mandatory) — unit tests at 100% coverage + e2e tests across all layers.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **microgpt/**: Python package (implicit namespace)
- **tests/**: Test suite (TDD, 100% coverage)
- All paths relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add `pathspec` dependency and install migration tooling

- [x] T001 Add `pathspec` to project dependencies in `pyproject.toml`
- [x] T002 Run `pip install -e .` or equivalent to install new dep

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model, migration, and repository that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Phase

- [x] T003 [P] Write unit tests for Corpus ORM model in `tests/unit/db/test_corpus_model.py`
- [x] T004 [P] Write unit tests for CorpusFile ORM model in `tests/unit/db/test_corpus_model.py`
- [x] T005 [P] Write unit tests for CorpusRepository in `tests/unit/db/test_corpus_repository.py`
- [x] T006 [P] Write migration test verifying `002_add_corpus_tables` creates corpora + corpus_files tables correctly in `tests/unit/db/test_migrations.py`

### Implementation for Foundational Phase

- [x] T007 [P] Create Corpus ORM model in `microgpt/db/models/corpus.py`
- [x] T008 [P] Create CorpusFile ORM model in `microgpt/db/models/corpus.py`
- [x] T009 [P] Export Corpus + CorpusFile from `microgpt/db/models/__init__.py`
- [x] T010 Create migration `migrations/versions/002_add_corpus_tables.py` for corpora + corpus_files tables
- [x] T011 [P] Create CorpusRepository in `microgpt/db/repositories/corpora.py`
- [x] T012 [P] Export CorpusRepository from `microgpt/db/repositories/__init__.py`

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Ingest a Source Code Directory for Training (Priority: P1) 🎯 MVP

**Goal**: Users can point the system at a directory of source files and have those files automatically ingested, chunked, and registered as a training corpus (with default patterns — no user-configurable filtering yet).

**Independent Test**: Create a corpus pointing at a small directory (5 source files). Verify the corpus appears in the corpus list with file_count and document_count matching expectations.

### Tests for User Story 1

- [x] T013 [P] [US1] Write unit tests for LineAsDocChunker in `tests/unit/services/test_chunking.py`
- [x] T014 [P] [US1] Write unit tests for FixedSizeWindowChunker in `tests/unit/services/test_chunking.py`
- [x] T015 [P] [US1] Write unit tests for FileAsDocChunker in `tests/unit/services/test_chunking.py`
- [x] T016 [US1] Write unit tests for CorpusLoader (directory walk, default ignore patterns, chunk orchestration) in `tests/unit/services/test_corpus_loader.py`
- [x] T017 [US1] Write unit tests for CorpusService (create, ingest, list, delete) in `tests/unit/services/test_corpus_service.py`
- [x] T018 [P] [US1] Write unit tests for corpus API endpoints (POST/GET/DELETE) in `tests/unit/api/test_corpus_api.py`
- [x] T019 [US1] Write e2e test for corpus lifecycle (create → ingest → verify stats → delete) in `tests/e2e/test_corpus_lifecycle.py`

### Implementation for User Story 1

- [x] T020 [P] [US1] Create Chunker base class/interface in `microgpt/services/chunking/__init__.py`
- [x] T021 [P] [US1] Implement LineAsDocChunker in `microgpt/services/chunking/line_chunker.py`
- [x] T022 [P] [US1] Implement FixedSizeWindowChunker in `microgpt/services/chunking/window_chunker.py`
- [x] T023 [P] [US1] Implement FileAsDocChunker in `microgpt/services/chunking/file_chunker.py`
- [x] T024 [US1] Implement CorpusLoader (directory walk + default ignore patterns + chunk orchestration) in `microgpt/services/corpus_loader.py`
- [x] T025 [US1] Implement CorpusService (create with field validation including `chunking_strategy` and `chunk_overlap`, ingest, list, get, delete) in `microgpt/services/corpora.py`
- [x] T026 [P] [US1] Implement corpus API routes (POST/GET/DELETE) in `microgpt/api/v1/corpora.py`
- [x] T027 [US1] Wire corpus router into `microgpt/api/v1/router.py`
- [x] T028 [US1] Add `microgpt corpus` CLI subcommand (create, ingest, list, show, delete) in `microgpt/cli.py`

**Checkpoint**: At this point, User Story 1 should be fully functional — users can create/ingest/list/delete corpora via CLI and API

---

## Phase 4: User Story 2 - Configure File Patterns and Ignore Rules (Priority: P2)

**Goal**: Users can specify include/exclude patterns at corpus creation time, and the ingest step respects them. Default patterns for standard source files are applied when no user patterns are specified.

**Independent Test**: Create two corpora on the same directory — one with `include_patterns=["*.py"]` and one with default patterns. Verify the first has only .py files and the second has all default source file types.

### Tests for User Story 2

- [x] T029 [P] [US2] Write unit tests for pattern filtering in `tests/unit/services/test_corpus_loader.py` (extend existing)
- [x] T030 [US2] Write API contract test for pattern fields in corpus creation in `tests/unit/api/test_corpus_api.py`
- [x] T031 [P] [US2] Add `include_patterns` and `exclude_patterns` field validation to CorpusService.create() in `microgpt/services/corpora.py`
- [x] T032 [US2] Implement pattern merging (user patterns + system defaults) in CorpusLoader in `microgpt/services/corpus_loader.py`
- [x] T033 [US2] Update corpus creation CLI in `microgpt/cli.py` to accept `--pattern` and `--ignore` flags
- [x] T034 [US2] Update corpus creation API validation in `microgpt/api/v1/corpora.py` to validate pattern format
- [x] T035 [US2] Update corpus creation CLI in `microgpt/cli.py` to accept `--pattern` and `--ignore` flags

**Checkpoint**: Users can control which files are included and how they are chunked

---

## Phase 5: User Story 3 - Select a Directory Corpus for a Training Run (Priority: P2)

**Goal**: Users can select an ingested corpus when starting a training run (instead of using the default `input.txt`). The training service loads docs from the corpus's chunked output.

**Independent Test**: Create and ingest a corpus, start a training run selecting that corpus, verify training progresses with data from the corpus (loss values, no errors).

### Tests for User Story 3

- [x] T036 [US3] Write unit tests for TrainingService corpus_id parameter in `tests/unit/services/test_training.py`
- [x] T037 [US3] Write e2e test: ingest corpus → start training with corpus_id → verify training completes in `tests/e2e/test_corpus_training.py`

### Implementation for User Story 3

- [x] T038 [US3] Add `corpus_id` FK to TrainingConfig model in `microgpt/db/models/training_config.py`
- [x] T038b [US3] Create migration to add `corpus_id` column to training_configs table in `migrations/versions/003_add_corpus_id_to_training_configs.py`
- [x] T039 [US3] Modify `TrainingService._load_docs()` to accept `corpus_id` and delegate to `CorpusService.load_docs()` in `microgpt/services/training.py`
- [x] T040 [US3] Implement `CorpusService.load_docs()` method that produces `list[str]` from corpus files + chunking strategy in `microgpt/services/corpora.py`
- [x] T041 [US3] Update `POST /v1/training/start` to accept `corpus_id` field in `microgpt/api/v1/training.py`
- [x] T041b [US3] Add `--corpus` flag to `microgpt train` CLI command in `microgpt/cli.py`
- [x] T042 [US3] Add corpus selector dropdown to `microgpt/api/templates/training.html`
- [x] T043 [P] [US4] Write unit tests for corpus file listing endpoint in `tests/unit/api/test_corpus_api.py`
- [x] T044 [US4] Write unit tests for language detection helper in `tests/unit/services/test_corpus_loader.py`
- [x] T045 [US4] Implement file listing endpoint `GET /v1/corpora/{id}/files` in `microgpt/api/v1/corpora.py`
- [x] T046 [US4] Implement file detail endpoint `GET /v1/corpora/{id}/files/{file_id}` in `microgpt/api/v1/corpora.py`
- [x] T047 [US4] Implement language detection via extension mapping in `microgpt/services/corpus_loader.py`
- [x] T048 [US4] Add corpus browser section to `microgpt/api/templates/datasets.html` (corpus list + file tree in retro terminal style)
- [x] T049 [US4] Update CorpusService.get() to include `language_map` in response (aggregated language stats) in `microgpt/services/corpora.py`
- [x] T050 [P] Handle zero-file ingestion (empty directory or no matches) gracefully — return clear error message in `microgpt/services/corpus_loader.py`
- [x] T051 Handle non-UTF-8 file encodings (skip with warning) in `microgpt/services/corpus_loader.py`
- [x] T052 Handle symlinks (skip symlinks pointing outside corpus root) in `microgpt/services/corpus_loader.py`
- [x] T052b [P] Handle large directories (>10,000 files) — add progress logging and a configurable file limit in `microgpt/services/corpus_loader.py`
- [x] T052c Define re-ingestion semantics (replace existing records) in `microgpt/services/corpora.py` (CorpusService.ingest)
- [x] T052d Handle corpus deletion while a training run references it — set corpus_id to NULL on TrainingConfig in `microgpt/services/corpora.py` (CorpusService.delete)
- [x] T053 [P] Add `microgpt corpus files` CLI subcommand in `microgpt/cli.py`
- [x] T054 Update `AGENTS.md` with new modules and patterns for this feature
- [x] T055 Update `README.md` with corpus ingestion usage examples
- [x] T056 Update `docs/user-requirements.md` with corpus format documentation
- [x] T057 Run full test suite and fix any regressions
- [x] T058 Run `make lint` and fix any lint violations
- [x] T059 Update `.env.example` if any new config vars added

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — CORNERSTONE of this feature
- **User Story 2 (Phase 4)**: Depends on US1 (modifies CorpusLoader ingestion flow to accept user patterns)
- **User Story 3 (Phase 5)**: Depends on US1 (needs ingested corpus data) — independent of US2, US4
- **User Story 4 (Phase 6)**: Depends on US1 (needs ingested corpus data to browse) — independent of US2, US3
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: FOUNDATION — all other stories build on this
- **User Story 2 (P2)**: Depends on US1 — adds pattern configuration on top of corpus creation
- **User Story 3 (P2)**: Depends on US1 — needs ingested data to train on. Can be done in parallel with US2/US4
- **User Story 4 (P3)**: Depends on US1 — needs ingested data to browse. Can be done in parallel with US2/US3

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- Chunkers before loader
- Loader before service
- Service before API endpoints
- API before CLI
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Foundational [P] tasks (T003-T006 tests, T007-T009 models, T011 repo) can run in parallel
- Within US1: T020-T023 (4 chunkers) can run in parallel; T026-T027 (API wiring) can run in parallel
- After US1 completes: US2, US3, and US4 can all be implemented in parallel
- US3 and US4 are completely independent of each other

---

## Parallel Example: User Story 1

```bash
# Write all chunker tests together:
Task: "Write unit tests for LineAsDocChunker in tests/unit/services/test_line_chunker.py"
Task: "Write unit tests for FixedSizeWindowChunker in tests/unit/services/test_window_chunker.py"
Task: "Write unit tests for FileAsDocChunker in tests/unit/services/test_file_chunker.py"

# Implement all chunkers together:
Task: "Create Chunker base class/interface in microgpt/services/chunking/__init__.py"
Task: "Implement LineAsDocChunker in microgpt/services/chunking/line_chunker.py"
Task: "Implement FixedSizeWindowChunker in microgpt/services/chunking/window_chunker.py"
Task: "Implement FileAsDocChunker in microgpt/services/chunking/file_chunker.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (basic directory ingestion with default patterns)
4. **STOP and VALIDATE**: Test corpus creation, ingestion, listing, deletion independently
5. Users can now ingest directories with default settings

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Basic ingest works (MVP!)
3. Add User Story 2 → Pattern configuration
4. Add User Story 3 → Training on corpora
5. Add User Story 4 → Corpus browser
6. Each story adds value without breaking previous stories

### Parallel Strategy (Post-MVP)

After US1 is complete:
- US2 and US3 can be implemented in parallel (different concerns: filtering vs training)
- US4 can be done alongside US2/US3 (purely UI/API)
- Polish tasks can begin once all stories converge

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD: Red-Green-Refactor)
- Commit after each logical group of tasks
- Stop at any checkpoint to validate story independently
- Core engine (`microgpt/core/`) MUST NOT be modified — all changes in services/db/api layers