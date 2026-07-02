---

description: "Task list for 054 Fine-Tuned Model Evaluation"
---

# Tasks: Fine-Tuned Model Evaluation

**Input**: Design documents from `docs/vault/Specs/054 Fine-Tuned Model Evaluation/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.md ✅, quickstart.md ✅

**Tests**: Included — Constitution Article IV (TDD) mandates Red-Green-Refactor for every feature.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the evaluation domain sub-package and shared infrastructure prerequisites.

- [X] T001 [P] Create evaluation service domain sub-package at `anvil/services/evaluation/` with bare docstring-only `__init__.py` (Article VI)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before the user story can be implemented — ORM models, enums, migrations, repository, SSE event types.

**⚠️ CRITICAL**: User story work cannot begin until this phase is complete.

### Tests for Foundational Infrastructure

- [X] T002 [P] Write unit test for EvaluationRunStatus enum in `tests/unit/evaluation/test_evaluation_run_orm.py` — verify all members, str values, and that only valid transitions are permitted
- [X] T003 [P] Write unit test for EvaluationRun ORM model in `tests/unit/evaluation/test_evaluation_run_orm.py` — verify column types, nullable constraints, FKs, default values, cascade rules
- [X] T004 [P] Write unit test for MetricDelta ORM model in `tests/unit/evaluation/test_evaluation_run_orm.py` — verify FK cascade, uniqueness constraint (run_id + metric_name), comparable flag logic
- [X] T005 [P] Write unit test for EvalSample ORM model in `tests/unit/evaluation/test_evaluation_run_orm.py` — verify FK cascade, composite uniqueness (run_id + prompt_index), nullable side-by-side fields
- [X] T006 [P] Write unit test for EvaluationRunRepository in `tests/unit/evaluation/test_evaluation_repository.py` — verify CRUD methods (create, get_by_id, list_by_model, find_by_status), pagination, filter by model_id/status

### Implementation for Foundational Infrastructure

- [X] T007 [P] Create EvaluationRunStatus enum in `anvil/services/_shared/evaluation_status.py` — members: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED` (cross-domain shared type per §10.3)
- [X] T008 [P] Create EvaluationRun ORM model in `anvil/db/models/evaluation_run.py` — columns per `data-model.md` (id, external_model_id FK, base_external_model_id FK, adapter_id, tokenizer_family, base_tokenizer_family, eval_dataset_name, status, mlflow_run_id, prompt_count, meta, started_at, finished_at, error_message, + TimestampMixin); indexes on (external_model_id), (base_external_model_id), (status), (created_at)
- [X] T009 [P] Create MetricDelta ORM model in `anvil/db/models/evaluation_run.py` — columns per data-model (id, evaluation_run_id FK CASCADE, metric_name, fine_tuned_value, base_value, delta, comparable, + TimestampMixin); unique constraint on (evaluation_run_id, metric_name)
- [X] T010 [P] Create EvalSample ORM model in `anvil/db/models/evaluation_run.py` — columns per data-model (id, evaluation_run_id FK CASCADE, prompt_index, input, base_output, fine_tuned_output, base_loss, fine_tuned_loss, + TimestampMixin); unique constraint on (evaluation_run_id, prompt_index)
- [X] T011 Create Alembic migration for `evaluation_runs`, `metric_deltas`, and `eval_samples` tables — auto-generate with `make db-revision`, review and finalize
- [X] T012 [P] Create EvaluationRunRepository in `anvil/db/repositories/evaluation_runs.py` — methods: `create(run)`, `get_by_id(id)`, `update_status(id, status, error_message)`, `list_by_model(model_id, limit, offset)`, `list_by_status(status, limit, offset)`, `add_metric_delta(run_id, delta)`, `add_sample(sample)`, `get_metrics(run_id)`, `get_samples(run_id)`

**Checkpoint**: Foundation ready — ORM models, migration, repository, and status enum are all created and tested.

---

## Phase 3: User Story 1 — Learner Compares Fine-Tuned Model to Base (Priority: P1) 🎯 MVP

**Goal**: A learner triggers Evaluate/Compare from the Models page, runs an async evaluation on a held-out split or eval-dataset, sees side-by-side samples and metric delta in a dedicated eval-compare view, and results are recorded with lineage.

**Independent Test**: With a base model and a fine-tuned variant (warm-start or adapter), run an evaluation on a small held-out split via `POST /v1/eval/fine-tuned`; verify SSE stream delivers progress, final `GET /v1/eval/fine-tuned/{run_id}` returns metrics with delta, and `GET /v1/eval/fine-tuned/{run_id}/samples` returns side-by-side outputs.

**Acceptance Scenario Coverage**:
- AS1: Side-by-side sample outputs on identical prompts ✓
- AS2: Quantitative metrics + delta recorded ✓
- AS3: Adapter model composes base+adapter (045), correct tokenizer (043) ✓
- AS4: Track-only model refused with clear message ✓

### Tests for User Story 1

- [X] T013 [P] [US1] Write unit test for Evaluator in `tests/unit/evaluation/test_evaluator.py` — verify per-sample loss computation reuses `InferenceService.loss_breakdown()`, adapter composition via `load_model(adapter_id=...)`, tokenizer dispatch reads `ExternalModel.tokenizer_family`
- [X] T014 [P] [US1] Write unit test for track-only refusal in `tests/unit/evaluation/test_evaluator.py` — verify `RunnableStatus.TRACK_ONLY` raises clear refusal before any computation begins
- [X] [P] [US1] Write unit test for TrackingService eval methods in `tests/unit/tracking/test_tracking_eval.py` — verify `start_eval_run()` creates MLflow run with eval-specific tags, `log_eval_metric()` logs metrics with correct keys, `finish_eval_run()` / `fail_eval_run()` set correct tags and status
- [X] T015 [P] [US1] Write e2e test for happy path eval in `tests/e2e/test_evaluation.py`
- [X] T016 [P] [US1] Write e2e test for track-only refusal in `tests/e2e/test_evaluation.py`
- [X] T017 [P] [US1] Write e2e test for cross-tokenizer display in `tests/e2e/test_evaluation.py`
- [X] T018 [P] [US1] Write e2e test for no-dataset refusal in `tests/e2e/test_evaluation.py`
- [X] T019 [P] [US1] Write e2e test for adapter model eval in `tests/e2e/test_evaluation.py`
- [X] [P] [US1] Write e2e test for SSE event type contract in `tests/e2e/test_evaluation.py`

### Implementation for User Story 1

#### Service Layer

- [X] T020 [P] [US1] Implement Evaluator in `anvil/services/evaluation/evaluator.py` — per-prompt: load base + fine-tuned model (adapter composition via `InferenceService.load_model(adapter_id=...)`), generate side-by-side sample text via `InferenceService.generate(loaded, prompt=..., ...)` (returns `str`), compute per-prompt loss via `InferenceService.loss_breakdown()` (returns losses, NOT text — the two are combined here); dispatch on `ExternalModel.tokenizer_family`; gate on `RunnableStatus.TRACK_ONLY` before loading
- [X] [US1] Implement model resolution in `anvil/services/evaluation/evaluation_service.py` (FR-006) — map the referenced `ExternalModel` to a `load_model`-serviceable identifier (`source_identifier`/experiment id) OR add an `ExternalModel`-lookup path to `load_model`; MUST be verified against real `load_model` behavior (it does NOT resolve `ExternalModel` PKs directly today)
- [X] T021 [P] [US1] Extend TrackingService in `anvil/services/tracking/tracking.py` — add `start_eval_run()`, `log_eval_metric()`, `finish_eval_run()`, `fail_eval_run()` methods that reuse existing `start_run()/log_metric()/set_tag()/finish_run()` with eval-specific tags per research.md conventions
- [X] T022 [US1] Implement EvaluationService in `anvil/services/evaluation/evaluation_service.py` — orchestration: create EvaluationRun in DB, start MLflow eval run, dispatch evaluator per-prompt via async generator yielding SSE events, persist MetricDelta + EvalSample per prompt, update status on completion/failure, stream events via asyncio.Queue

#### API Layer

- [X] T023 [P] [US1] Create request/response Pydantic models in `anvil/api/v1/schemas_eval.py` — `EvalFineTunedBody`, `EvaluationRunResponse`, `MetricDeltaResponse`, `EvalSampleResponse`, `EvaluationRunListResponse` per contracts/api.md
- [X] T024 [US1] Implement `POST /v1/eval/fine-tuned` in `anvil/api/v1/eval.py` — validate input (check model exists, not track_only, eval-dataset resolves, adapters exist), create EvaluationRun via service, return run_id + sse_url with 201
- [X] T025 [US1] Implement `GET /v1/sse/eval/{run_id}` SSE endpoint in `anvil/api/v1/eval.py` — stream progress events (status, progress, metric, complete, error) from service's async generator; reuse existing anvil SSE convention
- [X] T026 [P] [US1] Implement `GET /v1/eval/fine-tuned/{run_id}` in `anvil/api/v1/eval.py` — fetch persisted EvaluationRun + MetricDeltas, return `EvaluationRunResponse`
- [X] T027 [P] [US1] Implement `GET /v1/eval/fine-tuned/{run_id}/samples` in `anvil/api/v1/eval.py` — fetch persisted EvalSamples, return per-prompt side-by-side outputs
- [X] T028 [P] [US1] Implement `GET /v1/eval/fine-tuned` list endpoint in `anvil/api/v1/eval.py` — list runs with optional filters (model_id, status), pagination (limit, offset), return `EvaluationRunListResponse`
- [X] [P] [US1] Add EvaluationService import and lazy property to `anvil/workbench.py` — import `EvaluationService` and `EvaluationRunRepository`, add `_evaluation_service` lazy property matching existing patterns (see `_training_service`, `_inference_service` for convention)
- [X] [P] [US1] Add EvaluationRunRepository import and lazy property to `anvil/workbench.py` — import `EvaluationRunRepository`, add `_evaluation_run_repository` lazy property
- [X] [US1] Add god class delegate methods to `anvil/workbench.py` — `evaluate_fine_tuned()`, `get_evaluation_run()`, `get_evaluation_samples()`, `list_evaluation_runs()` per signatures in `contracts/api.md`, delegating to `EvaluationService`

#### UI Layer

- [X] T029 [US1] Create eval-compare Jinja2 template in `anvil/api/templates/eval_compare.html` — render side-by-side sample outputs (base vs fine-tuned), metric table with delta column, caveat label for non-comparable tokenizers per SC-004; use design tokens from `tokens.css` (surface colors, accent, radius, text hierarchy)
- [X] T030 [US1] Extend existing `SSESession` in `anvil/api/static/js/sse.js` to handle eval-specific SSE events (progress, metric, complete); add eval-compare callback wiring (live sample rendering, progress bar, complete/error handlers) — no new standalone SSE client
- [X] T031 [US1] Add Evaluate/Compare action button to Models page template at `anvil/api/templates/models_page.html` — conditional on model having a fine-tuned variant; open eval-compare view with model_id and base_model_id pre-populated
- [X] T032 [US1] Add held-out split auto-derivation logic in `anvil/services/evaluation/evaluation_service.py` — deferred per spec; require user-selected eval-dataset (path a) and refuse with clear message when `eval_dataset_name` is null

**Checkpoint**: User Story 1 fully functional — POST creates eval, SSE streams progress, GET returns results with metrics/samples/delta, Models page has Evaluate/Compare action, track-only models refused, cross-tokenizer handled correctly.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Quality assurance, validation gates, and completeness checks.

- [X] T033 [P] **UX compliance gate**: run `make ux-lint` on all changed UI/template/CSS files — must pass GATE: PASS before merge
- [X] T034 Run validation suite: `make lint`, `make typecheck`, `make test` — all must pass
- [X] T035 Run `make vault-audit` — must report 0 errors before committing vault changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS user story
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion
- **Polish (Phase 4)**: Depends on User Story 1 being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — no dependencies on other stories (only story)

### Within Each Phase

- Tests (T002–T006, T013–T019) MUST be written and FAIL before implementation
- Within Foundational: enums → models → migration → repository (sequential chain)
- Within US1: service → API → UI (service layer before API/UI)
- Models (T008–T010) can be parallel since they're independent files
- Repository (T012) depends on models — wait for T008–T010
- API endpoints (T024–T028) depend on EvaluationService (T022) — can be parallel among themselves
- UI tasks (T029–T031) can be parallel with API tasks
- SSE client JS (T030) can be parallel with API endpoint (T025)

### Parallel Opportunities

- **Setup**: Single task — no parallelism
- **Foundational**: T002–T006 (tests) parallel; T007–T010 (enums + models) parallel; T012 depends on models
- **US1**: T013–T019 (tests) parallel; T020–T021 (Evaluator + TrackingService extension) parallel; T023 (Pydantic models) parallel; T026–T028 (GET endpoints) parallel; T029–T031 (UI) parallel with API

### Parallel Execution Example: User Story 1

```bash
# 1. Write all tests first (in parallel):
Task: "Write unit test for Evaluator in tests/unit/evaluation/test_evaluator.py"
Task: "Write e2e tests in tests/e2e/test_evaluation.py"

# 2. Implement service layer (parallel):
Task: "Implement Evaluator in anvil/services/evaluation/evaluator.py"
Task: "Extend TrackingService in anvil/services/tracking/tracking.py"

# 3. Implement API + UI (parallel after EvaluationService):
Task: "Implement POST /v1/eval/fine-tuned in anvil/api/v1/eval.py"
Task: "Create eval-compare Jinja2 template in anvil/api/templates/eval_compare.html"
Task: "Create SSE client JS in anvil/api/static/js/eval.js"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (1 task)
2. Complete Phase 2: Foundational (11 tasks — BLOCKS all)
3. Complete Phase 3: User Story 1 (20 tasks)
4. **STOP and VALIDATE**: Run the independent test — `POST /v1/eval/fine-tuned` with models, verify SSE + GET results
5. Run Phase 4: Polish (3 tasks)

### Incremental Delivery within US1

1. Service layer first (Evaluator + EvaluationService) — testable via unit tests
2. API endpoints second (POST + SSE + GET) — testable via e2e tests
3. UI last (template + JS + Models page integration) — visible in browser

### Note

**Total tasks**: 39 (8 test, 6 foundational impl, 16 impl, 3 polish, 6 e2e test). The e2e tests for adapter and cross-tokenizer scenarios (T017–T019) depend on the full integration being in place, so they can't run until the service + API layers are complete. Unit tests (T013–T014) can run as soon as Evaluator (T020) is implemented.
