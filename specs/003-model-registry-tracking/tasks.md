# Tasks: Model Registry Tracking

**Input**: Design documents from `specs/003-model-registry-tracking/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The examples below include test tasks. Tests are OPTIONAL - only include them if explicitly requested in the feature specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `anvil/`, `tests/` at repository root
- Paths follow existing anvil structure per plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project is already set up — this phase covers adding registry-specific structure

- [x] T001 Create `models.py` registry ORM module at `anvil/db/models/registry.py` with RegisteredModel and ModelVersion SQLAlchemy tables (following training_config.py pattern with Base + TimestampMixin)
- [x] T002 Create Alembic migration `migrations/versions/002_add_model_registry.py` with `registered_models` and `model_versions` tables (following 001_initial.py pattern, pointing down_revision="001")

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Create `ModelRepository` in `anvil/db/repositories/models.py` with async CRUD methods: get, get_all (with search), get_by_name, add, delete, get_versions, get_version, delete_version, get_next_version_number (following ExperimentRepository pattern)
- [x] T004 Create `ModelRegistryService` in `anvil/services/models.py` with async methods: register_model, list_models, get_model, get_model_versions, get_version, delete_model, delete_version, get_inference_models (following ExperimentService pattern)
- [x] T005 Expose `ModelRegistryService` via God Class in `anvil/cli.py` — add `_registry` attribute and `registry` property to `MicroGPTWorkbench`

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Register a Trained Model from an Experiment (Priority: P1) 🎯 MVP

**Goal**: Users can register a trained model from a completed experiment with a name and optional description. Auto-versioning creates a new version when the same name is registered again.

**Independent Test**: Train a model through an experiment, register it via API, confirm it appears in the registry list.

### Implementation for User Story 1

- [x] T006 [P] [US1] Create registry API routes module `anvil/api/v1/registry.py` with POST /v1/registry/models endpoint that validates experiment is completed, creates RegisteredModel + first ModelVersion, copies artifact from experiment training output to `data/models/registry/{name}/v1/model.json` (independent from experiment storage per FR-008), and returns 201 with model version metadata
- [x] T007 [P] [US1] Create GET /v1/registry/models endpoint in `anvil/api/v1/registry.py` that lists all registered models sorted by most recently registered, with optional `?search=` query parameter for name filtering
- [x] T008 [US1] Register the registry router in `anvil/api/v1/router.py` by including `registry_router` (follow existing router inclusion pattern)
- [x] T009 [US1] Modify `anvil/api/v1/experiments.py` to return experiment detail including `artifact_available` flag for completed experiments (so UI knows when "Register Model" button should be enabled)
- [x] T010 [US1] Add "Register Model" button to `anvil/api/templates/experiments.html` in the experiment list htop-row for completed experiments — button opens a modal with model name + description fields, calls POST /v1/registry/models
- [x] T011 [US1] Create model registry browse page `anvil/api/templates/models.html` following retro terminal theme (htop-style rows matching experiments.html pattern) — shows list of registered models with name, latest_version, latest_loss, created_at, and search input
- [x] T012 [US1] Add "Models" navigation tab to `anvil/api/templates/base.html` in the nav bar — link to /v1/models-page or equivalent page route
- [x] T013 [US1] Add GET /v1/models-page route in `anvil/api/v1/router.py` that serves the models.html template with registered models data

**Checkpoint**: User Story 1 complete — users can register, browse, and search models via both API and UI

---

## Phase 4: User Story 2 — Browse and Select a Registered Model for Inference (Priority: P1)

**Goal**: Inference page presents registered models (not experiments) as selectable. Users choose a model + version, configure params, and run inference.

**Independent Test**: Register a model, go to inference page, see it in dropdown, select it, run inference, get samples.

### Implementation for User Story 2

- [x] T014 [P] [US2] Modify `GET /v1/inference/models` endpoint in `anvil/api/v1/router.py` to query `ModelRegistryService.get_inference_models()` instead of experiments table — returns list of registered models with latest version info; returns empty list with message if no models registered
- [x] T015 [P] [US2] Modify `POST /v1/inference/sample` endpoint in `anvil/api/v1/router.py` to accept `model_id` + `version` fields (instead of `experiment_id`), load model artifact from `data/models/registry/{name}/v{version}/model.json`, and generate samples
- [x] T016 [US2] Update `anvil/api/templates/inference.html` to load models from registry endpoint, display model name + version in dropdown (with version sub-selector for multi-version models), hide experiments from selector; show "No models registered" message with link to training when registry is empty

**Checkpoint**: User Story 2 complete — inference exclusively uses registered models

---

## Phase 5: User Story 3 — View Model Version History and Metadata (Priority: P2)

**Goal**: Users can view version history for a registered model with full metadata (source experiment, loss, hyperparameters, dataset). Users can delete individual versions or entire models.

**Independent Test**: Register two versions of the same model, view model detail page, confirm both versions shown with metadata; delete a version, confirm it's removed; delete the model, confirm removed from list.

### Implementation for User Story 3

- [x] T017 [P] [US3] Add GET /v1/registry/models/{model_id} endpoint in `anvil/api/v1/registry.py` that returns model detail with full version history (chronological, newest first), including metadata for each version (experiment_id, dataset_name, final_loss, hyperparameters JSON, created_at)
- [x] T018 [P] [US3] Add GET /v1/registry/models/{model_id}/versions/{version} endpoint in `anvil/api/v1/registry.py` that returns metadata for a specific version
- [x] T019 [P] [US3] Add DELETE /v1/registry/models/{model_id}/versions/{version} endpoint in `anvil/api/v1/registry.py` that removes the version artifact from filesystem and deletes the version record; returns 409 with warning if the model is currently selected for inference
- [x] T020 [P] [US3] Add DELETE /v1/registry/models/{model_id} endpoint in `anvil/api/v1/registry.py` that cascades delete of all versions (artifacts + records) and the model record; returns 409 with warning if any version is currently selected for inference
- [x] T021 [US3] Create model detail page `anvil/api/templates/model_detail.html` following retro terminal theme — shows model name, description, chronological version list with experiment links, metadata display, and delete buttons (with confirmation dialogs)
- [x] T022 [US3] Add GET /v1/model-detail-page/{model_id} route in `anvil/api/v1/router.py` that serves model_detail.html with model data and version history

**Checkpoint**: User Story 3 complete — full version history, metadata viewing, and deletion flows work

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T023 [P] Add tests for ModelRepository in `tests/test_db/test_model_repository.py` — test create, read, search, delete, version numbering (follow existing conftest async patterns)
- [x] T024 [P] Add tests for ModelRegistryService in `tests/test_services/test_model_service.py` — test register, list, get, delete flows with mocked repository
- [x] T025 [P] Add API endpoint tests in `tests/test_api/test_registry_routes.py` — test POST/GET/DELETE registry endpoints via AsyncClient (follow test_endpoints.py pattern)
- [x] T026 Add registry fixtures to `tests/conftest.py` — fixture for creating sample registered models and versions in test DB
- [x] T027 Run `alembic upgrade head` and verify migration applies cleanly with `make test` to confirm no regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — migration + ORM models first
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 — no dependencies on other stories
- **User Story 2 (Phase 4)**: Depends on Phase 2 + Phase 3 (US1) — needs registered models to exist
- **User Story 3 (Phase 5)**: Depends on Phase 2 + Phase 3 (US1) — needs registered models to exist; can run parallel with US2
- **Polish (Phase 6)**: Depends on all stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational — No dependencies on other stories — **MVP candidate**
- **User Story 2 (P1)**: Depends on US1 (needs registered models) — independently testable once models exist
- **User Story 3 (P2)**: Depends on US1 only — can run in parallel with US2

### Within Each User Story

- Models before services
- Services before endpoints
- Backend before frontend
- Core implementation before integration
- Story complete before moving to next

### Parallel Opportunities

- T006 + T007 (registry API routes) can run in parallel
- T014 + T015 (inference model/version endpoints) can run in parallel
- T017-T020 (version history + delete endpoints) can all run in parallel
- T023-T025 (test files) can all run in parallel
- US3 can start in parallel with US2 (both depend only on US1)

---

## Parallel Example: User Story 1

```bash
# Launch API route creation in parallel:
Task: "Create POST /v1/registry/models and GET /v1/registry/models in microgpt/api/v1/registry.py"
Task: "Modify experiments.py to expose artifact_available flag"
```

## Parallel Example: User Story 3

```bash
# Launch all version endpoints in parallel:
Task: "GET /v1/registry/models/{model_id} in microgpt/api/v1/registry.py"
Task: "GET /v1/registry/models/{model_id}/versions/{version} in microgpt/api/v1/registry.py"
Task: "DELETE /v1/registry/models/{model_id}/versions/{version} in microgpt/api/v1/registry.py"
Task: "DELETE /v1/registry/models/{model_id} in microgpt/api/v1/registry.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup → Migration + ORM models
2. Complete Phase 2: Foundational → Repository + Service + God Class
3. Complete Phase 3: User Story 1 → Register model via API + UI
4. **STOP and VALIDATE**: Register a model, see it in the models list
5. Deploy/demo if ready — users can register and browse models

### Incremental Delivery

1. Complete Setup + Foundational → Registry data layer ready
2. Add User Story 1 → Register + browse → **MVP ready**
3. Add User Story 2 → Inference from registry → **Core value delivered**
4. Add User Story 3 → Version history + deletion → Full feature complete

### Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence