# Tasks: Bootstrap Demo Datasets

**Input**: Design documents from `specs/001-bootstrap-datasets/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required by Constitution Article IV (TDD Mandatory — 100% coverage). Test tasks are included below in each relevant phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `anvil/`, `tests/`, `data/` at repository root
- All paths shown below reflect the actual project structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create demo data files and configure the project for the new feature

- [x] T001 Create `data/demo/` directory structure (small/, medium/, large/) with README.md overview
- [x] T002 [P] Create `data/demo/small/names/first-names.txt` — name list (~5KB, subset of public domain/MIT names)
- [x] T003 [P] Create `data/demo/small/hello-world/` corpus — `hello.py`, `factorial.py`, `fizzbuzz.py` (~1KB each, hand-crafted code snippets)
- [x] T004 [P] Create `data/demo/small/presidents.txt` — Washington's State of the Union addresses (~30KB, public domain via Gutenberg #5010)
- [x] T005 [P] Create `data/demo/medium/alice/` corpus — Alice in Wonderland chapters 1-2 (~25KB each, public domain via Gutenberg #11)
- [x] T006 [P] Create `data/demo/medium/math-facts.txt` — structured math facts (~10KB, hand-crafted)
- [x] T007 [P] Create `data/demo/large/earnest/` corpus — The Importance of Being Earnest acts I-III (~35KB each, public domain via Gutenberg #844)
- [x] T008 Add `anvil-bootstrap-datasets` entry point to `pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T009 Create `DemoBootstrapService` in `anvil/services/demo_bootstrap.py` with methods: `bootstrap_all()`, `get_default_corpus()`, `list_demo_corpora()`, `list_demo_datasets()`

**Details for T009**:
- `bootstrap_all()`: Walk `data/demo/` directories for corpora (→ `CorpusService.create()` + `ingest()`) and `.txt` files for datasets (→ `DatasetService.create_dataset()` + `DatasetImportService.commit_import()`)
- Idempotency: Check entity name before creating (name convention `"Demo - {size}/{name}"`)
- Returns `BootstrapResult` dataclass with counts and errors
- Use `file` chunking strategy for small dirs, `windowed` for large dirs
- Each item processed independently (errors don't abort others)
- Does NOT commit — caller manages session

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel

---

## Phase 2.5: Tests for Foundational Components

**Purpose**: Unit tests for `DemoBootstrapService` per Constitution Article IV (TDD Mandatory)

- [x] T009a Create `tests/test_bootstrap.py` with tests for `DemoBootstrapService.bootstrap_all()`: fresh bootstrap creates expected entities, idempotent re-run skips existing, partial failure accumulates errors, dry-run mode makes no changes
- [x] T009b [P] Create `tests/test_bootstrap.py` tests for `DemoBootstrapService.get_default_corpus()`: returns correct corpus when bootstrapped, returns `None` when not bootstrapped

**Checkpoint**: Foundational tests pass — core bootstrap logic is verified

---

## Phase 3: User Story 1 - Train on a Premade Demo Corpus Out of the Box (Priority: P1) 🎯 MVP

**Goal**: User can clone the repo, run `make setup`, start training without specifying any dataset — system auto-uses bundled demo data

**Independent Test**: Run `anvil train` with no `--corpus` or `--dataset` flags — training starts immediately using demo data (no network access needed)

### Implementation for User Story 1

- [x] T011 [US1] Write tests for training fallback in `tests/services/test_training.py` — test that `TrainingService._load_docs()` falls back to default demo corpus when no corpus_id/dataset_id given, and raises helpful error when not bootstrapped
- [x] T012 [US1] Modify `TrainingService._load_docs()` in `anvil/services/training.py` — replace lines 80-88 (`names.txt` download) with: query for default demo corpus by name `"Demo - medium/alice"` via `DemoBootstrapService.get_default_corpus()`, load docs from corpus if found, raise informative error if not bootstrapped
- [x] T013 [P] [US1] Modify `_load_docs()` in `anvil/cli.py` — replace lines 54-60 (`names.txt` download) with the same default demo corpus lookup logic (reuse `DemoBootstrapService`)
- [x] T014 [US1] Replace hardcoded `DEMO_CORPUS` in `anvil/services/inference.py` — update `_train_demo_model()` to accept optional `docs` parameter; update `DemoModelProvider.get_model()` to load docs from DB via default demo corpus first; add tiny embedded fallback (2-3 lines) as last resort
- [x] T015 [US1] Update `anvil/services/inference.py` `DemoModelProvider.get_model()` — add DB session creation and demo corpus lookup before falling back to embedded corpus

**Checkpoint**: At this point, User Story 1 should be fully functional — `anvil train` works out of the box with no arguments

---

## Phase 4: User Story 2 - Select from Multiple Demo Datasets (Priority: P2)

**Goal**: Users can run a bootstrap command to import all demo data, then browse and select from multiple datasets/corpora in the CLI and UI

**Independent Test**: Run `anvil bootstrap-datasets` — verify multiple corpora and datasets appear in `anvil corpus list` and can be selected for training

### Implementation for User Story 2

- [x] T015 [US2] Create `bootstrap_datasets_main()` function in `anvil/cli.py` — implement argparse with `--dry-run` and `--verbose` flags; call `DemoBootstrapService.bootstrap_all()` with proper async session management; display per-item progress and summary; exit codes (0=success, 1=partial, 2=fatal)
- [x] T016 [US2] Integrate bootstrap into app startup in `anvil/api/app.py` — during FastAPI lifespan, attempt `DemoBootstrapService.bootstrap_all()` silently (best-effort, catch exceptions) so demo data is available without manual CLI step
- [x] T017 [US2] Add `bootstrap-datasets` step to `Makefile` `setup` target — run `anvil bootstrap-datasets` after database initialization

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Datasets are Citable and Reproducible (Priority: P3)

**Goal**: Experiment metadata clearly shows which dataset was used; demo datasets are clearly labeled and distinguishable from user-created ones; deletion works with warning

**Independent Test**: Train a model, view experiment details — dataset name/ID is visible; demo datasets have clear `"Demo - "` prefix

### Implementation for User Story 3

- [x] T018 [P] [US3] Add `get_by_name(name: str) -> Corpus | None` method to `CorpusRepository` in `anvil/db/repositories/corpora.py`
- [x] T019 [P] [US3] Add `get_by_name(name: str) -> Dataset | None` method to `DatasetRepository` in `anvil/db/repositories/datasets.py`
- [x] T020 [P] [US3] Add `is_demo` helper to `DemoBootstrapService` — check if entity name starts with `"Demo - "` prefix; add `list_demo_entities()` method
- [x] T021 [US3] Implement deletion warning in `anvil/api/v1/datasets.py` — on DELETE `/datasets/{id}`, check if dataset name starts with `"Demo - "`; if so, return HTTP 409 with warning message; accept `force: true` in request body to bypass
- [x] T022 [US3] Ensure experiment metadata captures dataset/corpus name in `anvil/services/tracking.py` — verify `log_dataset_input()` and `log_corpus_input()` propagate the `"Demo - "` name into MLflow experiment tags
- [x] T023 [US3] Write tests for deletion warning in `tests/api/v1/test_datasets.py` — test that deleting a demo dataset returns 409, force-delete succeeds, non-demo datasets are unaffected

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T024 [P] Update `anvil/cli.py` `train()` help text — change `--corpus` default description from `"(default: input.txt)"` to `"(default: bundled demo corpus)"`
- [x] T025 [P] Create `data/demo/README.md` with licensing attribution: MIT for names, public domain for Gutenberg texts, generated for hand-crafted content
- [x] T026 [P] Remove any lingering references to `names.txt` URL download or `input.txt` default in documentation and comments
- [x] T027 [P] Clean up unused `urllib.request` imports from `anvil/cli.py` and `anvil/services/training.py` (no longer needed after removing download fallback)
- [x] T028 Run `make lint`, `make typecheck`, and `make test` on all changed files, fix any issues; verify all existing tests still pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **Tests for Foundational (Phase 2.5)**: Depends on Phase 2 completion
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories proceed sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) — independently testable from US1
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) — independently testable from US1/US2

### Within Each User Story

- Demo data files before service code
- Service code before CLI/API endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T002-T007 (all [P]) can all run in parallel — they create independent files
- **Phase 2**: No parallel opportunities — DemoBootstrapService is a single cohesive unit
- **Phase 2.5**: T009a-T009b can run in parallel — independent test scenarios
- **Phase 3**: T010 (test) before T011-T014; T012 can run in parallel with T011 (different files: `training.py` vs `cli.py`)
- **Phase 4**: T015 ([P]) can run in parallel with nothing; T016-T017 are sequential
- **Phase 5**: T018-T020 all [P] — independent repository and service methods; T021-T022 sequential; T023 tests after implementation
- **Phase 6**: T024-T027 can all run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch training fallback changes in parallel:
Task: "Modify TrainingService._load_docs() in anvil/services/training.py"
Task: "Modify cli.py _load_docs() in anvil/cli.py"

# After those complete, modify inference:
Task: "Replace DEMO_CORPUS in anvil/services/inference.py"
Task: "Update DemoModelProvider for DB lookup in anvil/services/inference.py"
```

## Parallel Example: Phase 1 Setup

```bash
# Launch all demo file creation in parallel:
Task: "Create data/demo/small/names/first-names.txt"
Task: "Create data/demo/small/hello-world/ corpus"
Task: "Create data/demo/small/presidents.txt"
Task: "Create data/demo/medium/alice/ corpus"
Task: "Create data/demo/medium/math-facts.txt"
Task: "Create data/demo/large/earnest/ corpus"
Task: "Add entry point to pyproject.toml"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup — create all demo data files
2. Complete Phase 2: Foundational — `DemoBootstrapService`
3. Complete Phase 2.5: Tests for Foundational — verify bootstrap logic
4. Complete Phase 3: User Story 1 — training fallback replacement (write tests before implementation per TDD)
5. **STOP and VALIDATE**: Run `make test && anvil train` — should train on demo data with no arguments
6. Deploy/demo if ready

### Incremental Delivery

1. **Setup + Foundational** → Foundation ready (demo data files exist, bootstrap service can import them)
2. **Add User Story 1** → Out-of-box training works → **MVP!**
3. **Add User Story 2** → CLI bootstrap + auto-import on startup → Deploy/Demo
4. **Add User Story 3** → Reproducibility + labeling → Deploy/Demo
5. Each story adds value without breaking previous stories

### Note on Testing

The project Constitution (Article IV) mandates TDD with 100% coverage. Test tasks are included in:
- **Phase 2.5**: Unit tests for `DemoBootstrapService` in `tests/test_bootstrap.py`
- **Phase 3 (US1)**: T010 — tests for training fallback in `tests/services/test_training.py`
- **Phase 5 (US3)**: T023 — tests for deletion warning in `tests/api/v1/test_datasets.py`
- **Phase 6**: T028 — `make test` must pass before completion

All tests MUST be written RED (failing) before implementation, then made GREEN.