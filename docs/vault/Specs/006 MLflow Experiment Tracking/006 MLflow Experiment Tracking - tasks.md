---
title: 006 MLflow Experiment Tracking - tasks
type: tasks
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/006 MLflow Experiment Tracking/
related:
  - '[[006 MLflow Experiment Tracking]]'
created: ~
updated: ~
---
---
description: "Task list for MLflow Experiment & Data Lifecycle Tracking"
---

# Tasks: MLflow Experiment & Data Lifecycle Tracking

**Input**: Design documents from `/docs/vault/Specs/006 MLflow Experiment Tracking/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (tracking-service.md, http-api.md), quickstart.md

**Tests**: TDD is MANDATORY (AGENTS.md: tests first, Red-Green-Refactor, **100% coverage via `fail_under=100`**). Every implementation task is preceded by a failing test task.

**Organization**: Grouped by user story (priority order). A foundational backbone — the single `TrackingService` seam (canonical **HTTP server** URI), the `Experiment` lifecycle record created at run start, the status-vocabulary migration, and the MLflow **3.x** bump — is a blocking prerequisite for all stories.

**Post-merge context**: the codebase now has a dual stdlib/torch engine, async CLI, GPU detection, and `mlflow>=2.16,<3` (to be bumped to 3.x). Registration is **source-keyed and automatic on success** (1 dataset/corpus → 1 registered model → N versions). Status vocabulary moves from the legacy `pending`/`completed` to `running`/`finished`/`failed`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete dependencies)
- **[Story]**: US1–US6 for story phases; Setup/Foundational/Registry/Polish carry no story label
- Paths are repository-root-relative

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency + configuration scaffolding.

- [X] T001 In `pyproject.toml`: bump core dep `mlflow>=2.16,<3` → **`mlflow>=3.1,<4`**, and add `nvidia-ml-py>=12,<13` to the **`gpu` optional-dependencies extra** (alongside `torch`, per Constitution Article I — NOT core deps) (research.md R1/R11; spec FR-031)
- [X] T002 Refresh the lock file and `make setup`; verify `mlflow.__version__` >= 3.1, `import mlflow.genai.datasets` succeeds, and `import psutil` works
- [X] T002a **Dependency-resolution pre-check (BLOCKING — do before relying on the 3.x bump)**: confirm `mlflow>=3.1,<4` resolves cleanly against the existing pins — `pydantic<3` (MLflow 3.x needs pydantic≥2, so 2.x must satisfy both), `torch>=2.0`, `alembic<2`, plus transitive `sqlalchemy`/`protobuf`. Run the resolver (`pip install --dry-run` / lock refresh), record the **resolved version set** in research.md (or a comment in `pyproject.toml`), and if any constraint conflicts, surface it and adjust pins **before** proceeding to Phase 2. NOTE (verified): `mlflow.genai` managed datasets require a **SQL backend** (SQLite/Postgres/MySQL) reached via the server — they are NOT FileStore-compatible and do NOT require Databricks; this is why R2's HTTP-server-over-SQLite destination is mandatory for US6.
- [X] T003 [P] Document `MICROGPT_MLFLOW_URI=http://127.0.0.1:5000` (canonical HTTP server URI, NOT a sqlite path) in `.env.example` with a comment that this single value drives writers and readers

**Checkpoint**: MLflow 3.x installed; genai importable.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Canonical HTTP-server tracking URI, `Experiment` lifecycle schema + status migration, and the `TrackingService` seam with the run created at start.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

### Configuration & tracking URI (FR-006, R2)

- [X] T004 Write failing test `tests/unit/test_config.py` asserting `get_config()` exposes a canonical `mlflow_uri` defaulting to `http://127.0.0.1:5000` (HTTP server) and a `mlflow_backend_store_uri` resolving to an **absolute** `sqlite:///<abs>/mlruns/mlflow.db`
- [X] T005 Implement in `anvil/config.py`: change `mlflow_uri` default to the HTTP server URI and add `mlflow_backend_store_uri` (absolute sqlite via `Path(...).resolve()`), keeping `MICROGPT_MLFLOW_URI` as the single override and preserving the existing `device` key
- [X] T006 Write failing test `tests/unit/test_supervisor_services.py` asserting `MLflowService` derives `--backend-store-uri` from `get_config()["mlflow_backend_store_uri"]` and exposes the canonical HTTP `mlflow_uri` as `tracking_uri` (no hardcoded `sqlite:///./mlruns/...`)
- [X] T007 Update `anvil/supervisor/services.py` so `MLflowService` reads the backend-store + tracking URI from config

### Experiment lifecycle schema + status migration (data-model A1; FR-010/011/015/016/028)

- [X] T008 Write failing test `tests/unit/db/test_experiment_lifecycle.py` for new `Experiment` fields (`run_name`, `corpus_id`, `input_digest`, `input_role`, `engine_backend`, `device`) and statuses `running`/`finished`/`failed`
- [X] T009 Edit `anvil/db/models/training_config.py` `Experiment`: add `run_name`, `corpus_id` (FK→corpora), `input_digest`, `input_role`, `engine_backend`, `device`; change status default to `running`
- [X] T010 Generate the migration via `make db-revision MESSAGE="experiment lifecycle fields + status backfill"`; it MUST chain onto the current head (`006_add_model_registry`; expected file `migrations/versions/007_experiment_lifecycle.py`) without colliding with `002b`/`006`. Hand-verify it adds the columns, is reversible, AND **data-backfills legacy status values**: `completed → finished`, and any non-terminal `pending` → `failed` with `error_message="legacy/unknown"`. **Safety guard**: the backfill MUST be terminal-status-preserving — a `completed` row MUST map to `finished` and MUST NEVER be marked `failed`; the migration MUST be a no-op for rows already in a terminal state. NOTE: today the `Experiment` row is created only at completion (research R4), so legacy `pending` rows are rare/genuinely-stuck — mapping them to `failed` is correct, but verify against real legacy data shape before applying. Write a migration regression test (`tests/test_db/`) asserting `completed → finished` (never `failed`), `pending → failed` with the reason, and idempotency on re-run.
- [X] T011 Write failing test in `tests/unit/db/test_experiment_lifecycle.py` for repository methods `create_running`, `mark_finished`, `mark_failed`, `find_orphaned`
- [X] T012 Implement those methods in `anvil/db/repositories/experiments.py` (create-at-start; terminal transitions setting `completed_at`/`error_message`; orphan query for `status='running'`)
- [X] T013 Write failing tests, then update ALL remaining status-string readers to the new vocabulary (resolves the legacy `completed`/`pending` drift): `anvil/services/experiments.py` (line ~21, creation `status="pending"` → `running` or delegate to `create_running`), `anvil/api/v1/registry.py` (line ~38, `!= "completed"` → `!= "finished"`), and the frontend status displays in `anvil/api/templates/archetypes/experiment.html`, `anvil/api/templates/archetypes/models.html`, `anvil/api/static/js/widgets/training-loop.js`, and `anvil/api/static/js/core.js`. Grep the repo for `"completed"`/`"pending"` to confirm none remain unhandled.

### Capability detection + TrackingService seam (contracts/tracking-service.md)

- [X] T014 [P] Write failing test `tests/unit/services/test_mlflow_capabilities.py` for genai/version detection (genai importable + server-backed → available) per research.md R10
- [X] T015 [P] Implement `anvil/services/mlflow_capabilities.py` (`TrackingCapabilities` + detection via guarded `import mlflow.genai.datasets` + store-type check)
- [X] T016 Write failing test `tests/unit/services/test_tracking_service.py` with an **injected fake client factory**: canonical-URI resolution, `start_run(run_name, params, engine_backend, device)` (returns run_id + logs params + creates `Experiment` running), `log_metric`/`log_final_metric`, `finish_run`/`fail_run` (update BOTH MLflow status and local `Experiment`; agree per FR-016), `log_artifacts`, and **Article IX degraded mode**: when the destination is unreachable, `start_run` enters degraded no-op mode (no raise; `is_degraded` True; subsequent calls are safe no-ops) per FR-009
- [X] T017 Implement `anvil/services/tracking.py` `TrackingService` per the contract (constructor with config-default `tracking_uri` + injectable `client_factory`; experiment get-or-create; `start_run`/`log_metric`/`log_final_metric`/`finish_run`/`fail_run`/`log_artifacts`/`capabilities`; **degraded no-op mode + `is_degraded`** when the destination is unreachable — never raises to fail a run, per Article IX/FR-009; `CapabilityUnavailable` only for the genai path; blocking calls via `run_in_executor`). The default run name follows `<source-slug>-<UTC-timestamp>` (FR-010)

### Backbone route refactor (http-api.md; create Experiment at start)

- [X] T018 Write failing test `tests/unit/api/test_training_start_lifecycle.py` asserting `POST /v1/training/start` creates the local `Experiment` (`status="running"` + `started_at` + `run_name` + `mlflow_run_id` + `engine_backend` + `device`) BEFORE completion and returns `experiment_id`
- [X] T019 Refactor `anvil/api/v1/training.py` to delegate all MLflow access to `TrackingService` (remove module-level `MlflowClient` + the hardcoded `MLFLOW_TRACKING_URI` at line 21); resolve `engine_backend`/`device` via `anvil/gpu.py`; create the `Experiment` at start (status `running`); call `finish_run`/`fail_run` + `log_artifacts` on terminal events

**Checkpoint**: Canonical HTTP-server URI on the start path; runs create a lifecycle `Experiment` from start; status vocabulary unified; `TrackingService` is the sole MLflow seam. Stories can begin.

---

## Phase 3: User Story 1 - Reproducible run provenance (Priority: P1) 🎯 MVP

**Goal**: Every run records the dataset/corpus that fed it as a labeled input with a content-derived identity + source reference.

**Independent Test**: Start a run on a known dataset → MLflow run shows it as a `training` input with a stable digest + source; same content ⇒ same digest; corpus shows as `corpus` input.

- [X] T020 [P] [US1] Write failing test `tests/unit/services/test_mlflow_inputs.py` for `MlflowInputResolver`: dataset→`from_pandas` (`context="training"`), validation (`context="validation"`), corpus→`MetaDataset` + file artifacts (`context="corpus"`), **content-derived digest stability** (identical docs ⇒ identical digest; changed ⇒ different), AND a guard asserting the resolver composes ONLY from `from_*`/`MetaDataset`/artifacts (no bespoke corpus store — FR-024)
- [X] T021 [US1] Implement `anvil/services/mlflow_inputs.py` `MlflowInputResolver` (FR-005 source→representation decision + content hash)
- [X] T022 [US1] Add `log_dataset_input`/`log_corpus_input` to `anvil/services/tracking.py` (delegating to `MlflowInputResolver`, `log_input` with role context, returning digest) — extend `tests/unit/services/test_tracking_service.py` with failing cases first
- [X] T023 [US1] Write failing test `tests/unit/api/test_training_lineage.py` asserting the start path attaches the correct labeled input and persists `input_digest`/`input_role` on the `Experiment`
- [X] T024 [US1] Wire lineage into `anvil/api/v1/training.py` start path (after `start_run`, call the appropriate `log_*_input` from resolved `dataset_id`/`corpus_id` — no phantom input for the unused reference)

**Checkpoint**: US1 independently testable (SC-002, SC-003).

---

## Phase 4: User Story 2 - Consistent, configurable tracking destination (Priority: P1)

**Goal**: Web start, CLI start, and experiment browsing all use the one canonical destination; unreachable destinations **degrade gracefully** (training proceeds untracked with a non-blocking warning — no error, no block, per Constitution Article IX / FR-009).

**Independent Test**: Configure destination once → web run, CLI run, and experiment list all use it; an unreachable destination degrades gracefully (training proceeds untracked with a non-blocking warning, no error — Article IX).

- [X] T025 [P] [US2] Write failing test `tests/unit/api/test_tracking_uri_consistency.py` asserting `experiments.py` and `registry.py` contain NO hardcoded `sqlite:///./mlruns/...` or `http://127.0.0.1:5000` literals and resolve URIs/links from `get_config()`
- [X] T026 [US2] Refactor `anvil/api/v1/experiments.py` to obtain the MLflow client + UI base URL from config/`TrackingService` (remove `MLFLOW_TRACKING_URI`/`MLFLOW_UI_URI`); expose `run_name`, `status`, `input_digest`, `input_role`, `engine_backend`, `device` (FR-007)
- [X] T027 [US2] Write failing test in `tests/unit/api/test_tracking_uri_consistency.py`: when the destination is unreachable at run start, `POST /v1/training/start` does NOT return 5xx — training still starts, the response sets `"tracking": "degraded"` (`mlflow_run_id: null`), and a non-blocking `warning` SSE event is emitted (Article IX / FR-009)
- [X] T028 [US2] Implement graceful degradation in `anvil/api/v1/training.py`: when `TrackingService` is degraded, proceed with training, return `"tracking": "degraded"`, and emit the warning event — never raise an error solely because tracking is down (Article IX)
- [X] T029 [P] [US2] Write failing test `tests/e2e/test_cli_training_tracked.py` asserting `anvil train --dataset <id>` produces a tracked run at the canonical destination (parity with web) and supports `--dataset`/`--corpus`/`--gpu`
- [X] T030 [US2] Refactor `anvil/cli.py` `train()` to route through `TrainingService` + `TrackingService` (create run, lifecycle `Experiment`, lineage, metrics) and add the `--dataset` argument (FR-008)

**Checkpoint**: US1 + US2 independent (SC-001, SC-009).

---

## Phase 5: User Story 3 - Live & historical metrics + device provenance (Priority: P1)

**Goal**: Per-step loss on a consistent axis, distinct final-loss, eval metrics on the same axis, plus backend/device recorded as params.

**Independent Test**: Short run → live per-step `loss`; completed run shows distinct `final_loss`; run params include `engine_backend`/`device`; two runs overlay on a shared step axis.

- [X] T031 [P] [US3] Write failing test `tests/unit/api/test_metrics_logging.py` asserting the callback logs `loss` per step on a monotonic `step` axis via `TrackingService.log_metric`, and completion logs a distinct `final_loss` via `log_final_metric`
- [X] T032 [US3] Ensure `anvil/services/training.py` forwards `(step, loss)` through the `TrackingService` callback with a consistent global step index and reports `final_loss` at completion (FR-012/013) — already correct; verified with passing tests
- [X] T033 [US3] Write failing test in `tests/unit/api/test_metrics_logging.py` asserting (a) eval/validation metrics share the training step axis (FR-014) and (b) `engine_backend`/`device` are recorded as run params (FR-011/Q3)
- [X] T034 [US3] Add an eval-metric logging hook reusing the training step axis in `anvil/services/tracking.py`, and ensure `engine_backend`/`device` are passed to `TrackingService.start_run` from both web (`api/v1/training.py`) and CLI (`cli.py`) paths — web path verified; CLI path handled by Phase 4 (T030)

**Checkpoint**: US1–US3 independent (SC-005).

---

## Phase 6: User Story 4 - Failure & lifecycle integrity (Priority: P2)

**Goal**: Crashed/interrupted runs show failed/terminated in both records, including hard kills reconciled on startup.

**Independent Test**: Exception mid-train → marked failed with reason; hard-kill then restart → orphaned RUNNING run reconciled in both stores.

- [X] T035 [P] [US4] Write failing test `tests/unit/api/test_experiment_failure.py` asserting a training exception marks the run `failed` (local `Experiment` + MLflow `FAILED`) with the reason captured and statuses agreeing (FR-015/016)
- [X] T036 [US4] Wrap the training execution in `anvil/services/training.py` so exceptions trigger `TrackingService.fail_run(reason=...)` + an `error` SSE event, without swallowing the exception
- [X] T037 [P] [US4] Write failing test `tests/integration/test_orphan_reconciliation.py` asserting `TrackingService.reconcile_orphans()` marks orphaned RUNNING runs `KILLED`/`failed` (reason `"interrupted/terminated"`) in both stores and is idempotent (FR-028, SC-010)
- [X] T038 [US4] Implement `reconcile_orphans()` in `anvil/services/tracking.py` using `search_runs(filter_string="attributes.status = 'RUNNING'")` + repository `find_orphaned`, then `set_terminated(run_id, status="KILLED")` + `mark_failed`
- [X] T039 [US4] Write failing test `tests/integration/test_orphan_reconciliation.py` asserting the FastAPI `lifespan` invokes reconciliation on startup before serving (note: this is web-startup-driven; CLI-started orphans are reconciled at next web boot)
- [X] T040 [US4] Wire `reconcile_orphans()` into the `lifespan` in `anvil/api/app.py` (after engine init/`create_all` + MLflow server start, before `yield`)

**Checkpoint**: US1–US4 independent (SC-004, SC-010).

---

## Phase 7: User Story 5 - System resource utilization incl. MPS (Priority: P3)

**Goal**: Automatic CPU/memory plus accelerator metrics on ALL accelerators — CUDA via MLflow + custom MPS collector.

**Independent Test**: Any run → `system/cpu_*`/`system/memory_*`; CUDA host → `system/gpu_*`; MPS host → MPS utilization/memory via custom collector; no-accelerator host records CPU/mem without error.

- [X] T041 [P] [US5] Write failing test `tests/unit/services/test_system_metrics.py` asserting `mlflow.enable_system_metrics_logging()` is invoked exactly once at process start and that accelerator absence does not raise (CPU/mem still enabled) per research.md R9
- [X] T042 [US5] Add a one-time `enable_system_metrics_logging()` hook in `anvil/services/tracking.py` (idempotent guard)
- [X] T043 [P] [US5] Write failing test `tests/unit/services/test_metrics_collectors.py` for the custom MPS collector (monkeypatch the `ioreg` subprocess output): parses `AGXAccelerator → PerformanceStatistics → Device Utilization %` for utilization and `In use system memory`/`torch.mps` for memory, samples on a thread, logs `system/gpu_*`-style metrics; **degrades to no-op + no error** when MPS absent OR when `ioreg` is unavailable/unparsable (Article IX; FR-020/031)
- [X] T044 [US5] Implement `anvil/services/metrics_collectors.py` MPS sampler: utilization via `ioreg -r -c AGXAccelerator -d 2` parsing (`PerformanceStatistics → Device Utilization %`; stdlib `subprocess`, **no `sudo`, no new dep**), memory via `torch.mps`/`anvil/gpu.py._get_mps_memory`; uses `anvil/gpu.py` detection; capability-gated. NOTE: `psutil`/`torch.mps` do NOT expose GPU utilization (torch.mps is memory-only) — `ioreg` is the only non-privileged utilization source; `powermetrics` is rejected (requires `sudo`)
- [X] T045 [US5] Wire the enable hook + MPS collector into the web `lifespan` (`anvil/api/app.py`) and the CLI training entry (`anvil/cli.py`) so both paths capture system metrics (FR-020)

**Checkpoint**: US1–US5 independent (SC-006).

---

## Phase 8: User Story 6 - Reusable, curated evaluation sets (Priority: P3)

**Goal**: Named, persistent, growable managed evaluation datasets (first-class under 3.x), queryable by name; graceful fallback when unavailable.

**Independent Test**: Create a named eval set, append records, query by name across sessions; when capability is unavailable, the API reports it gracefully and runs still succeed.

- [X] T046 [P] [US6] Write failing test `tests/integration/test_managed_eval_datasets.py` for `TrackingService.create_eval_dataset`/`append_eval_records`/`get_eval_dataset` against a server-backed store (create → append → query-by-name persists) per contracts/tracking-service.md
- [X] T047 [US6] Implement the genai dataset methods in `anvil/services/tracking.py` using `mlflow.genai.create_dataset` + `EvaluationDataset.merge_records`/`to_df`/`search_datasets`; raise `CapabilityUnavailable` when `capabilities().genai_datasets` is False (FR-021)
- [X] T048 [P] [US6] Write failing test `tests/test_api/test_eval_datasets_routes.py` for `POST /v1/eval-datasets`, `POST /v1/eval-datasets/{name}/records`, `GET /v1/eval-datasets/{name}`, including the graceful `{ "available": false, ... }` response when capability missing (FR-022, SC-007)
- [X] T049 [US6] Implement `anvil/api/v1/eval_datasets.py` router delegating to `TrackingService`, translating `CapabilityUnavailable` into a graceful 200 response (never failing a run)
- [X] T050 [US6] Register the new router in `anvil/api/v1/router.py`
- [X] T051 [US6] Write failing test asserting a missing-capability scenario does NOT fail an in-progress training run, then verify in `tests/integration/test_managed_eval_datasets.py`

**Checkpoint**: All six stories independent (SC-007).

---

## Phase 9: Source-Keyed Model Registry Consolidation (Cross-Cutting — FR-017/018/019/025/027/029/030, SC-008/SC-011)

**Purpose**: Auto-register every successful run as a version of an input-source-keyed registered model; deprecate the local registry. (Not a numbered story; no story label.)

- [X] T052 [P] Write failing test `tests/test_api/test_registry_mlflow.py` asserting `TrackingService.register_source_model` derives the stable id-based source-keyed name (`dataset-<id>`/`corpus-<id>`/`default-source`, FR-029), creates-or-reuses the registered model, and adds a version via `create_model_version(source="runs:/<run_id>/model.json")` — with guards that it uses **no model flavor** (FR-025) and logs **no unintended default artifact** (FR-018), and creates NO local `RegisteredModel`/`ModelVersion` row (SC-008)
- [X] T053 Implement `register_source_model` in `anvil/services/tracking.py` (id-based slug per FR-029; idempotent `create_registered_model` + `create_model_version`, no flavor) per research.md R8
- [X] T054 Wire auto-registration on SUCCESS into the shared completion path used by both web (`anvil/api/v1/training.py`) and CLI (`anvil/cli.py`), replacing the `anvil-experiment-{id}` auto-register (training.py lines 139–155); failed runs MUST register nothing (FR-030)
- [X] T055 Write failing test `tests/test_api/test_registry_mlflow.py` asserting: N successful runs on one source → exactly one registered model with N versions; a failed run adds 0 versions; a new source → a new registered model (SC-011)
- [X] T056 Refactor `anvil/api/v1/registry.py` `POST /registry/models` to require `status="finished"` and delegate to the source-keyed `TrackingService.register_source_model`; remove the local-registry write path; deprecate writes in `anvil/services/models.py`
- [X] T057 Write failing test `tests/test_db/test_registry_transition.py` for the transition path: existing local `ModelVersion` rows are migrated into the MLflow registry (best-effort, pointing at `artifact_path`) or marked legacy — never silently orphaned/duplicated
- [X] T058 Implement the transition routine `migrate_local_registry_to_mlflow` in `anvil/services/models.py`, invoked from a CLI maintenance command in `anvil/cli.py`
- [X] T059 [P] Write ADRs `docs/vault/Decisions/ADR-004-mlflow-3x-and-canonical-uri.md` and `docs/vault/Decisions/ADR-005-source-keyed-registry-consolidation.md` (next available after existing ADR-001/002/003; AGENTS.md vault protocol)

**Checkpoint**: Registered models live only in MLflow, keyed per source (SC-008, SC-011).

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T060 [P] Update `README.md` MLflow section: canonical `MICROGPT_MLFLOW_URI` server URI, MLflow 3.x, source-keyed registry, deprecation of the local registry
- [X] T061 [P] Update `AGENTS.md` "Active Technologies"/"Recent Changes" (mlflow 3.x, nvidia-ml-py, custom MPS metrics)
- [X] T062 [P] Write a session log in `docs/vault/Sessions/` and ensure all vault wikilinks resolve
- [X] T063 Remove dead code from the deprecated local-registry write path in `anvil/services/models.py` and `anvil/api/v1/registry.py` once the transition (T058) is verified
- [X] T064 Run `make lint` and `make typecheck` (strict mypy) and resolve all findings
- [X] T065 Run `make test` and confirm **100% coverage** (`fail_under=100`) across all new modules
- [X] T066 Execute the `quickstart.md` walkthrough end-to-end and confirm each step maps to its success criterion (SC-001…SC-011)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**: none — start immediately
- **Foundational (P2)**: after Setup — **BLOCKS all stories**. The status-vocabulary migration + reader audit (T010, T013) must land with the schema change to avoid a mixed `completed`/`finished` state.
- **User Stories (P3–P8)**: after Foundational
  - US1/US2/US3 (P1) parallelizable after Foundational (coordinate shared `training.py`/`tracking.py` edits around the backbone)
  - US4 (P2) builds on the lifecycle backbone; US5/US6 (P3) are largely independent
- **Registry Consolidation (P9)**: after Foundational (needs `TrackingService` + finished-run artifacts) and after US1 (needs resolved input source for source-keying); independent of US5/US6
- **Polish (P10)**: after all desired stories + P9

### User Story Dependencies

- **US1 (P1)**: after Foundational. Independent. (Provides the input-source resolution that P9 reuses.)
- **US2 (P1)**: after Foundational. Shares `training.py` with backbone/US1 (sequence edits).
- **US3 (P1)**: after Foundational. Shares `training.py`/`tracking.py` (sequence edits).
- **US4 (P2)**: after Foundational. Reconciliation + lifespan wiring (web-startup-driven; CLI orphans reconciled at next web boot).
- **US5 (P3)**: after Foundational. Independent (lifespan + CLI enable hook + MPS collector).
- **US6 (P3)**: after Foundational. Independent (new router + genai service methods).

### Within Each User Story

- Test task(s) FIRST and MUST FAIL before implementation (TDD).
- Models/repositories → services → routes → CLI/lifespan wiring.

### Parallel Opportunities

- Setup: T003 [P] alongside T001/T002.
- Foundational: config track (T004–T007) ∥ DB track (T008–T013) ∥ capabilities (T014/T015 [P]); converge at T017/T019.
- After Foundational: US1/US2/US3 test-writing tasks [P] can be drafted together; US5 and US6 can be built in parallel by separate developers.
- P9: T052 [P] and T059 [P] (ADRs); P10: T060/T061/T062 [P] docs.

---

## Parallel Example: cross-story P1 staffing

```bash
# Developer A → US1 (provenance):   T020 → T021 → T022 → T023 → T024
# Developer B → US2 (destination):  T025 → T026 → T027 → T028 → T029 → T030
# Developer C → US3 (metrics):      T031 → T032 → T033 → T034
# Coordinate shared training.py / tracking.py edits via the backbone (T017/T019 land first)
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → Phase 2 Foundational (3.x bump, canonical HTTP-server URI, lifecycle schema + status migration, `TrackingService`, Experiment-at-start).
2. Phase 3 US1 (provenance lineage).
3. **STOP & VALIDATE**: reproducible dataset/corpus provenance — the highest-value gap. Demo.

### Incremental Delivery

1. Foundational → US1 → US2 (consistent destination + CLI) → US3 (metrics + device) — completes all P1 value.
2. US4 (failure/orphan integrity) → trustworthy run list.
3. US5 (system metrics incl. MPS) and US6 (managed eval sets) — additive P3.
4. Phase 9 source-keyed registry consolidation → single source of truth.
5. Phase 10 polish + 100% coverage gate.

### Parallel Team Strategy

After Foundational: A→US1, B→US2, C→US3 concurrently; then fan out US4/US5/US6 and P9. The backbone refactor (T017/T019) must land first.

---

## Notes

- [P] = different files, no incomplete dependencies. Same-file edits across stories are sequential.
- Every implementation task has a preceding failing test (TDD). Verify Red before Green.
- All MLflow/psutil/pynvml code stays in `services/`+`api/`; `anvil/core/` remains stdlib-only (torch backend already isolated in `core/torch_engine.py`).
- Blocking MLflow/pynvml calls run via `run_in_executor`; the MPS sampler runs on a background thread.
- Status vocabulary is `running`/`finished`/`failed`; the migration (T010) + reader audit (T013) eliminate the legacy `pending`/`completed` drift.
- Registration is source-keyed and automatic on **success** only (1 source → 1 registered model → N versions).
- Commit after each task or logical group; keep `make test` green and coverage at 100%.
- The local model-registry tables are NOT dropped in this feature — only deprecated and migrated; dropping is a verified follow-up.
- **Registry trigger correction (verified against code)**: today MLflow auto-registers on **every** completion (`anvil-experiment-{id}`), while the **local** registry is written **only** via manual `POST /v1/registry/models` — they are NOT both written on every run. T054 replaces the per-run MLflow auto-register with source-keyed registration; T056/T063 retire the manual local-registry write path.
- **MPS utilization source (verified)**: use `ioreg`/IOKit `AGXAccelerator → PerformanceStatistics` (stdlib `subprocess`, no `sudo`, no new dep). `psutil`/`torch.mps` cannot supply GPU utilization (torch.mps is memory-only); `powermetrics` is rejected (requires `sudo`). See T043/T044.
- **Single-process assumption**: `enable_system_metrics_logging` is process-global and startup orphan reconciliation has no PID/heartbeat liveness check — both assume a single training process. Concurrent multi-instance operation is out of scope (FR-028 liveness model); per-run params/metrics/inputs/artifacts remain run-scoped regardless.
