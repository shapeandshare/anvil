---

description: "Task list for Interactive Teaching Loop (055) feature implementation"
---

# Tasks: Interactive Teaching Loop (055)

**Input**: Design documents from `docs/vault/Specs/055 Interactive Teaching Loop/`
**Prerequisites**: plan.md, spec.md, research.md (esp. §9-§12), data-model.md, contracts/api.md

**Tests included**: Yes — per TDD mandate (Constitution Article IV). Write tests FIRST, ensure they FAIL, then implement.

**User Stories**: 1 story (P1) — native iterative teaching. Adapter, formal-eval, and imported-seed are deferred (see spec Scope).

> **Architecture (post-review)**: The training lifecycle (validation → MLflow setup → run → **model-artifact persistence at `data/models/experiment_{id}.json`** → registration) currently lives in the `POST /training/start` route closure. Phase 2 EXTRACTS it into a reusable `TrainingRunService` that BOTH the route and teaching consume. A route-parity test guards NMRG. Teaching chains on the **native experiment id** (no `ExternalModel` FK). Compare = side-by-side inference (formal eval deferred). SSE reuses the existing `/v1/training/stream/{run_id}` directly.

**Format**: `[ID] [P?] [Story] Description with file path`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the enum, ORM model, migration, repository, and domain sub-package scaffold.

- [ ] T001 [P] Create TeachingSessionStatus StrEnum in `anvil/db/models/teaching_session_status.py` (DRAFT/ACTIVE/COMPLETED per constitution Principle 11)
- [ ] T002 Create TeachingSession ORM model in `anvil/db/models/teaching_session.py` (fields per data-model.md: id, name, description, `seed_experiment_id`, `current_base_experiment_id`, status, created_at, updated_at — NO ExternalModel FK)
- [ ] T003 Create Alembic migration for `teaching_sessions` table via `make db-revision` (indexes on status, created_at) per data-model.md schema
- [ ] T004 [P] Create TeachingSessionRepository in `anvil/db/repositories/teaching_session_repository.py` (CRUD: create, get, list w/ status filter + pagination, update_status, update_current_base_experiment_id, delete)
- [ ] T005 [P] Create teaching service sub-package `anvil/services/teaching/__init__.py` (bare docstring-only, Article VI)

---

## Phase 2: Foundational — TrainingRunService Extraction (Blocking Prerequisites)

**⚠️ CRITICAL & HIGHEST RISK**: This refactor extracts the training lifecycle so teaching can produce a loadable model. The existing `/training/start` behavior MUST be preserved. Write the parity test FIRST.

### Parity guard (write FIRST, must pass before + after refactor)

- [ ] T006 Write route-parity e2e test in `tests/e2e/test_training_parity.py` capturing current `POST /training/start` behavior: response shape (`run_id`, `mlflow_run_id`, `experiment_id`, `status`), MLflow tags set, and that `data/models/experiment_{id}.json` is written on completion. Must PASS against the pre-refactor code.

### Extraction

- [ ] T007 Create TrainingRunService in `anvil/services/training/training_run_service.py` — move the `/training/start` orchestration (validation via `_validate_hparams`, backend resolution, memory estimation, run reservation, MLflow run setup + tags, asyncio task creation) AND the ~200-line `on_complete` closure (finish run, lineage tags, samples/model.json + safetensors export, **`data/models/experiment_{id}.json` persistence**, `register_source_model`) into methods on this class. One class per file (Article VI/one-class rule).
- [ ] T008 Refactor `POST /training/start` in `anvil/api/v1/training.py` to a thin delegate that calls `TrainingRunService` — keep request parsing + response shaping in the route; behavior unchanged.
- [ ] T009 Expose `workbench.training_runs` property on AnvilWorkbench in `anvil/workbench.py` (lazy-init TrainingRunService with session/tracking/training/inference deps)
- [ ] T010 Run T006 parity test — MUST still PASS after refactor (NMRG). Fix until green.

### Teaching foundation

- [ ] T011 Implement TeachingService in `anvil/services/teaching/teaching_service.py` (create_session, get_session w/ lineage from MLflow tags, list_sessions, update_session_status, delete_session; start_round → create dataset (origin=teaching) + call TrainingRunService warm-starting from `current_base_experiment_id`, set teaching MLflow tags, update `current_base_experiment_id` ONLY after finalization; inspect_round via InferenceService; compare via side-by-side inference between two experiment ids; rollback_to_round → new round warm-started from target. Force `method="full"`; reject LoRA. Check `tracking.is_degraded` before tag ops.)
- [ ] T012 Add dataset origin support: extend `DatasetImportService`/repository (and `DatasetService.create_dataset`) to accept and persist `origin` (set `"teaching"` for teaching datasets) in `anvil/services/datasets/`
- [ ] T013 Expose `workbench.teaching` property on AnvilWorkbench in `anvil/workbench.py`

**Checkpoint**: Training lifecycle is reusable (route parity green); TeachingService can orchestrate native rounds.

---

## Phase 3: User Story 1 — Learner Teaches a Model Iteratively (Priority: P1) 🎯 MVP

**Goal**: A learner runs a short native fine-tune, inspects outputs, adds corrective examples, and runs another round warm-started from the previous — checkpoint-chained with visible lineage.

**Independent Test**: Start a session (from scratch or seed); run round 1 (few examples, short budget); inspect samples; add examples; run round 2 warm-started from round 1's experiment id; verify round 2's `parent_experiment_id` = round 1's experiment id, `current_base_experiment_id` updated, and session lineage visible.

### Tests for User Story 1 ⚠️ (write FIRST, ensure FAIL)

- [ ] T014 [P] [US1] Unit test for TeachingSessionRepository CRUD + `update_current_base_experiment_id` in `tests/unit/db/test_teaching_session_repository.py`
- [ ] T015 [P] [US1] Unit test for TeachingService (create session, start round, chain update, lineage, rollback, LoRA rejection) in `tests/unit/services/test_teaching_service.py`
- [ ] T016 [P] [US1] Unit test for TrainingRunService persistence (model artifact written) in `tests/unit/services/test_training_run_service.py`
- [ ] T017 [US1] e2e test for full teaching loop (create session → round 1 → inspect → round 2 chained → verify lineage + chain head → compare side-by-side) in `tests/e2e/test_teaching_loop.py`

### Implementation for User Story 1

- [ ] T018 [P] [US1] Add GET `/v1/teach` page route handler in `anvil/api/v1/pages.py` (TemplateResponse with sessions list context)
- [ ] T019 [P] [US1] Create teach.html template at `anvil/api/templates/teach.html` (extends base.html; session list/selector, active round workflow, inference output display, side-by-side compare panel)
- [ ] T020 [P] [US1] Add "Teach" sidebar entry in `anvil/api/templates/base.html` (tab-item → /v1/teach with SVG icon)
- [ ] T021 [US1] Implement session CRUD routes in `anvil/api/v1/teach.py` (POST/GET/PATCH/DELETE /v1/teach/sessions; GET /v1/teach/sessions/{id} with round lineage; DELETE 204 + NO cascade to MLflow; all bodies Pydantic BaseModel)
- [ ] T022 [US1] Implement round routes in `anvil/api/v1/teach.py` (POST /v1/teach/sessions/{id}/rounds → create dataset + start warm-start training via TrainingRunService, return `run_id` + `stream_url=/v1/training/stream/{run_id}`; GET .../rounds; reject `method != full` with 422; Pydantic bodies)
- [ ] T023 [US1] Implement inspect + compare routes in `anvil/api/v1/teach.py` (POST .../rounds/{index}/inspect → InferenceService.generate(); POST .../compare → side-by-side inference between two experiment ids — NOT EvaluationService; Pydantic bodies)
- [ ] T024 [US1] Register teach_router in `anvil/api/v1/router.py` (include_router(teach_router))
- [ ] T025 [US1] Wire SSE in `anvil/api/templates/teach.html`: frontend connects DIRECTLY to `/v1/training/stream/{run_id}` via `SSESession` from sse.js (do NOT proxy); onmetrics → live chart; oncomplete → refresh round status + show inspect; onerror → error state

**Checkpoint**: Full native teaching loop works — create session, chained rounds, inspect, side-by-side compare, rollback.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T026 Run `make ux-lint` on changed templates/CSS — must pass GATE: PASS
- [ ] T027 Run `make lint` + `make typecheck` (mypy --strict) — zero new violations
- [ ] T028 Run `make test` — NMRG; T006 parity test + full suite green
- [ ] T029 Run `make vault-audit` — 0 errors before committing vault changes
- [ ] T030 Enrich vault: session log in `docs/vault/Sessions/`; ADR for the TrainingRunService extraction in `docs/vault/Decisions/`

---

## Dependencies & Execution Order

| Phase | Depends On | Notes |
|-------|-----------|-------|
| Phase 1 (Setup) | — | Enum/ORM/migration/repo/pkg |
| Phase 2 (Extraction + Foundation) | Phase 1 | **T006 parity test BEFORE T007 refactor; T010 re-verifies** |
| Phase 3 (US1) | Phase 2 | Needs TrainingRunService + TeachingService |
| Phase 4 (Polish) | Phase 3 | Quality gates |

### Critical ordering within Phase 2

```
T006 (parity test, PASS on old code)
  → T007 (extract TrainingRunService)
  → T008 (route delegates)
  → T009 (workbench.training_runs)
  → T010 (parity test PASS on new code) ← GATE
  → T011 (TeachingService) → T012 (dataset origin) → T013 (workbench.teaching)
```

### Parallel Opportunities

- Setup: T001, T004, T005 parallel
- US1 tests: T014, T015, T016 parallel
- US1 frontend: T018, T019, T020 parallel

---

## Parallel Example: User Story 1

```bash
# Tests first (parallel):
Task: "Unit test TeachingSessionRepository in tests/unit/db/test_teaching_session_repository.py"
Task: "Unit test TeachingService in tests/unit/services/test_teaching_service.py"
Task: "Unit test TrainingRunService persistence in tests/unit/services/test_training_run_service.py"

# Independent frontend (parallel):
Task: "Add teach page handler in anvil/api/v1/pages.py"
Task: "Create teach.html in anvil/api/templates/teach.html"
Task: "Add Teach sidebar entry in anvil/api/templates/base.html"
```

---

## Implementation Strategy

### MVP First (US1, native only)

1. Phase 1: Setup (enum + ORM + migration + repo)
2. Phase 2: **Parity test → extract TrainingRunService → re-verify parity → TeachingService**
3. Phase 3: US1 — tests fail → implement → pass
4. **STOP & VALIDATE**: run full teaching-loop e2e + parity test
5. Phase 4: Polish gates

### Deferred (NOT in this MVP — see spec Scope / plan Complexity Tracking)

- Formal evaluation via 054 (`EvaluationService`) — needs ExternalModel.id
- LoRA/adapter teaching rounds — no loadable artifact + no adapter DB auto-registration
- Imported HF/local model as round-1 seed — no experiment artifact

---

## Notes

- [P] = different files, no dependencies
- **T006/T010 are the NMRG guard** for the extraction — do not skip
- Teaching reuses: TrainingRunService (new), warm-start (039), dataset prep (053), inference (045), existing training SSE. Evaluation (054) NOT used in MVP.
- `current_base_experiment_id` updates ONLY after round finalization (never optimistically)
- All API request/response bodies MUST be Pydantic BaseModel
- Commit after each logical group; ADR required for the extraction decision
