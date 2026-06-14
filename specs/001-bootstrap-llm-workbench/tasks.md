---

description: "Task list for Bootstrap LLM Workbench"
---

# Tasks: Bootstrap LLM Workbench

**Input**: Design documents from `specs/001-bootstrap-llm-workbench/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-v1.md

**Tests**: Tests are REQUIRED for ALL user stories (TDD mandate — 100% unit coverage + full e2e).

**Organization**: Tasks are grouped per the spec's mandatory implementation order: Agentic Harness → Project Boilerplating → Remainder.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US0–US7)
- Include exact file paths in descriptions

## Path Conventions

All paths relative to repository root. Package root: `anvil/`. Tests root: `tests/`.

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Initialize the project skeleton (no code logic yet)

- [X] T001 Create directory structure per plan.md: `anvil/core/`, `anvil/db/`, `anvil/services/`, `anvil/api/`, `anvil/storage/`, `anvil/supervisor/`, `migrations/`, `tests/unit/`, `tests/e2e/`, `data/`, `logs/`
- [X] T002 [P] Create `pyproject.toml` with package metadata (`name="anvil"`, version `0.1.0`, Python >=3.11, dependencies, optional-dependency groups, entry points)
- [X] T003 [P] Create `.gitignore` excluding `__pycache__/`, `.venv/`, `.env`, `logs/`, `data/`, `mlruns/`, IDE files
- [X] T004 [P] Create `.env.example` documenting all config vars: `MICROGPT_PORT`, `MICROGPT_DB_PATH`, `MICROGPT_LOG_DIR`, `MICROGPT_MLFLOW_URI`, `MICROGPT_STORAGE_BACKEND`
- [X] T005 Create dependency lock file (`requirements.lock` or `uv.lock`) from pyproject.toml dependencies
- [X] T114 Create `README.md` at repo root — project overview, prerequisites, quick-start (`pip install && make run`), architecture explanation, hyperparameter guide, web UI route reference, LAN access instructions

---

## Phase 2: User Story 0 — Agentic Harness & Governance (Priority: P0) ⚠️ MUST COMPLETE BEFORE ANY CODE

**Goal**: AI agents can read constitution, discover vault, execute specs, enrich vault with discoveries and ADRs.

**Independent Test**: Start new OpenCode session → agent reads constitution → discovers ADRs in vault → runs `/speckit.plan` without errors.

### Implementation for User Story 0

- [X] T006 [US0] Create `CONSTITUTION.md` at repo root — define non-negotiable principles: zero-dependency core, educational clarity, seeded reproducibility, TDD, async-first, implicit namespace, layered architecture, agentic design
- [X] T007 [US0] [P] Create `docs/vault/` directory structure: `Governance/`, `Decisions/`, `Reference/`, `Sessions/`
- [X] T008 [US0] [P] Create `docs/vault/index.md` — vault entry point with navigation links to Governance, Reference, Decisions, Sessions
- [X] T009 [US0] [P] Create `docs/vault/Governance/Constitution.md` — copy of CONSTITUTION.md in vault format with YAML frontmatter
- [X] T010 [US0] [P] Create `docs/vault/Decisions/` with initial ADR template note and first ADR documenting the architecture decisions in this spec
- [X] T011 [US0] [P] Create `docs/vault/Reference/Glossary.md` — canonical project terms (microgpt, god class, FileStore, etc.)
- [X] T012 [US0] Create `AGENTS.md` — agent behavioral guidelines: project structure, available commands, vault enrichment protocol (discoveries during session, summary at end), ADR creation workflow, coding conventions
- [X] T013 [US0] Configure `.specify/` tooling per oldgrowth patterns (already partially exists — verify and add any missing extensions/config)

**Checkpoint**: Agentic harness complete. Agents can now work autonomously.

---

## Phase 3: Foundational — Project Boilerplating & Infrastructure

**Purpose**: Build system, tooling configs, database layer, package structure — blocks ALL user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T014 Create `Makefile` with targets: `setup` (venv + lock install + db init), `run` (start all services via venv), `stop` (stop all services), `train` (CLI training), `test` (run all tests), `lint` (ruff → black --check → isort --check → pylint), `format` (black + isort), `typecheck` (mypy/pyright), `vault` (open docs), `progressive` (run all train0-5 files), `clean` (remove artifacts), `install` (pip install -e .), `help`. All targets auto-detect/create venv.
- [X] T015 [P] Configure `[tool.ruff]`, `[tool.black]`, `[tool.isort]`, `[tool.pylint]`, `[tool.mypy]` sections in `pyproject.toml` per research.md patterns
- [X] T016 [P] Create `anvil/__init__.py` — package exports: god class, version, public API surface
- [X] T017 [P] Create `anvil/db/__init__.py` — export all repository and model classes
- [X] T018 [P] Create `anvil/db/session.py` — async engine creation, `AsyncSessionLocal` factory, `get_db` async context manager for request-scoped sessions
- [X] T019 [P] Create `anvil/db/base.py` — SQLAlchemy `DeclarativeBase` with common mixins (timestamp columns, etc.)
- [X] T020 Create `alembic.ini` at repo root — configure async SQLAlchemy URL, migration directory
- [X] T021 [P] Create `migrations/env.py` — async Alembic environment using `async_engine_from_config`
- [X] T022 [P] Create `migrations/script.py.mako` — migration template
- [X] T023 Create initial migration in `migrations/versions/` — create all tables (Dataset, TrainingConfig, Experiment) from data-model.md
- [X] T024 [P] Create `anvil/storage/__init__.py` — export FileStore interface and factory
- [X] T025 [P] Create `anvil/storage/interface.py` — `FileStore` abstract base: `get()`, `put()`, `delete()`, `list()`, `FileInfo` Pydantic model
- [X] T026 [P] Create `anvil/storage/local.py` — `LocalFileStore` with `aiofiles`, temp-file-rename atomic writes
- [X] T027 [P] Create `anvil/api/__init__.py` — export FastAPI app factory
- [X] T028 [P] Create `anvil/api/app.py` — FastAPI app with lifespan (auto `alembic upgrade head` on startup, graceful shutdown), static file mount, template engine setup, CORS for LAN access
- [X] T029 [P] Create `anvil/api/deps.py` — FastAPI dependencies: `get_db_session`, `get_god_class`, `get_file_store`
- [X] T030 [P] Create `tests/conftest.py` — pytest-asyncio fixtures: async test DB (`aiosqlite` in-memory), test client (httpx.AsyncClient), test session override
- [X] T031 Create initial e2e test in `tests/e2e/test_setup.py` — verify `make setup` creates venv, installs deps, runs migrations
- [X] T115 [P] Create `anvil/config.py` — env var reading with `python-dotenv` and sensible defaults per FR-046 (`MICROGPT_PORT=8080`, `MICROGPT_DB_PATH=./data/microgpt.db`, `MICROGPT_LOG_DIR=./logs/`, `MICROGPT_MLFLOW_URI=sqlite:///./mlruns/mlflow.db`, `MICROGPT_STORAGE_BACKEND=local`)
- [X] T116 [P] Create `anvil/cli.py` — CLI entry point functions: `serve()` (starts web server via uvicorn), `train()` (runs training via god class), `stop()` (stops services via supervisor). Registered via `[project.scripts]` in pyproject.toml
- [X] T117 [P] Update `anvil/db/session.py` to enable SQLite WAL mode via `pragma journal_mode=WAL` and `pragma foreign_keys=ON` on engine creation per FR-043

**Checkpoint**: Foundation ready. Database, storage, web server skeleton, and test infrastructure are all functional.

---

## Phase 4: User Story 1 — Train Models via Web UI (Priority: P1) 🎯 MVP

**Goal**: User can start the server, train a model from the browser, see loss in real-time (SSE), and view generated samples — all without CLI.

**Independent Test**: Start workbench on machine A, navigate from machine B's browser, click "start training", see SSE-updating loss chart and final samples.

### Tests for User Story 1 (TDD — write before implementation)

- [X] T032 [US1] [P] Unit test for core engine forward pass in `tests/unit/core/test_engine.py`
- [X] T033 [US1] [P] Unit test for core engine backward pass (gradients match expected) in `tests/unit/core/test_engine.py`
- [X] T034 [US1] [P] Unit test for training a single step and verifying loss decreases in `tests/unit/core/test_training.py`
- [X] T035 [US1] [P] Unit test for god class `MicroGPTWorkbench.create_training_run()` in `tests/unit/test_god_class.py`
- [X] T036 [US1] [P] API contract test for `POST /v1/training/start` in `tests/unit/api/test_training.py`
- [X] T037 [US1] [P] SSE stream test — verify `GET /v1/training/stream/{id}` yields `data:` lines in `tests/unit/api/test_training.py`

### Implementation for User Story 1

- [X] T038 [US1] [P] Create `anvil/core/__init__.py` — export core engine classes
- [X] T039 [US1] [P] Create `anvil/core/autograd.py` — Value class with operations (+/\*, log, exp, relu, pow, backward), as-is from Karpathy's microgpt.py
- [X] T040 [US1] [P] Create `anvil/core/tokenizer.py` — character-level tokenizer: `encode(text)`, `decode(ids)`, vocabulary build from dataset
- [X] T041 [US1] Create `anvil/core/engine.py` — GPT model: parameter init, RMSNorm, softmax, linear, multi-head attention, MLP, `gpt()` forward function, inference `generate()`
- [X] T042 [US1] Write training orchestrator in `anvil/core/engine.py` — `train()`: Adam optimizer loop, loss tracking, sample generation, progress callback for SSE
- [X] T043 [US1] [P] Create `anvil/db/models/training_config.py` — TrainingConfig ORM model per data-model.md
- [X] T044 [US1] [P] Create `anvil/db/repositories/training_configs.py` — `TrainingConfigRepository` with async CRUD
- [X] T045 [P] [US1] Create `anvil/api/v1/__init__.py` — export v1 router
- [X] T046 [P] [US1] Create `anvil/api/v1/router.py` — FastAPI APIRouter with `/v1/` prefix
- [X] T047 [US1] Create `anvil/services/training.py` — `TrainingService`: orchestrates engine training in background asyncio task, publishes loss metrics to SSE queue, logs to MLflow stub
- [X] T048 [US1] Create `anvil/api/v1/training.py` — training endpoints: `POST /v1/training/start` (spawns background task), `GET /v1/training/stream/{id}` (SSE), `POST /v1/training/{id}/stop`
- [X] T049 [US1] [P] Create `anvil/api/templates/base.html` — Jinja2 base template: nav bar, unicorn header (SVG + ASCII art), emoji touches, retro CSS
- [X] T050 [US1] [P] Create `anvil/api/templates/training.html` — training dashboard: hyperparameter form, SSE-connected loss chart (Chart.js or canvas), generated samples display
- [X] T051 [US1] [P] Create `anvil/api/static/style.css` — retro CSS: pixel-art-inspired borders, bright colors, emoji-styled buttons, responsive layout
- [X] T052 [US1] [P] Create `anvil/api/static/unicorn.svg` — inline SVG unicorn mascot (agent-generated whimsy)
- [X] T053 [US1] Create `anvil/__init__.py` god class — `MicroGPTWorkbench` with `create_training_run()`, `get_training_status()`, delegates to `TrainingService`
- [X] T054 [US1] Wire SSE event stream in `anvil/api/v1/training.py` — `asyncio.Queue` pub/sub, Starlette `StreamingResponse`, heartbeat every 15s, `Last-Event-ID` for reconnection
- [X] T055 [US1] Add `make train` CLI target in Makefile — delegates to `anvil.cli:train` entry point, which instantiates god class and runs training synchronously (same service logic, no HTTP needed)

**Checkpoint**: User Story 1 is fully functional. Training works from both web UI (SSE streaming) and CLI.

---

## Phase 5: User Story 2 — Experiment Tracking & Comparison via Web UI (Priority: P1)

**Goal**: Training runs are automatically tracked (MLflow). User can browse past experiments, compare two runs side-by-side with overlaid loss curves.

**Independent Test**: Run two training sessions with different learning rates via web UI → navigate to experiments page → see both runs listed with loss curves overlaid.

### Tests for User Story 2 (TDD)

- [X] T056 [US2] [P] Unit test for `ExperimentRepository` CRUD in `tests/unit/db/test_experiments.py`
- [X] T057 [US2] [P] Unit test for MLflow integration: verify `mlflow.log_params` and `mlflow.log_metrics` called with correct values in `tests/unit/services/test_experiments.py`
- [X] T058 [US2] [P] API contract test for `GET /v1/experiments` and `GET /v1/experiments/compare` in `tests/unit/api/test_experiments.py`

### Implementation for User Story 2

- [X] T059 [US2] [P] Create `anvil/db/models/experiment.py` — Experiment ORM model per data-model.md
- [X] T060 [US2] [P] Create `anvil/db/repositories/experiments.py` — `ExperimentRepository` with async CRUD + comparison query
- [X] T061 [US2] [P] Create `anvil/services/experiments.py` — `ExperimentService`: list, get, compare, delete experiments
- [X] T062 [US2] Create `anvil/supervisor/__init__.py` — export supervisor classes
- [X] T063 [US2] Create `anvil/supervisor/services.py` — `MLflowService` class: start/stop/restart MLflow subprocess with `preexec_fn=os.setsid`, PID file, log capture, health check
- [X] T064 [US2] Create `anvil/supervisor/supervisor.py` — `ProcessSupervisor`: manages all background services (web, MLflow, training runner), lifecycle controls (start/stop/restart/status), per-service log capture
- [X] T065 [US2] Integrate MLflow tracking into `TrainingService` — on training start: `mlflow.start_run()`, log params, per-step metrics, final artifact (samples), store `mlflow_run_id` on Experiment model
- [X] T066 [US2] Create `anvil/api/v1/experiments.py` — experiment endpoints: `GET /v1/experiments` (list with pagination), `GET /v1/experiments/{id}`, `DELETE /v1/experiments/{id}`, `GET /v1/experiments/compare?id=1&id=2`
- [X] T067 [US2] [P] Create `anvil/api/templates/experiments.html` — experiment history list + comparison view: two-column loss curve overlay, side-by-side samples, hyperparameter table
- [X] T068 [US2] Add MLflow native UI link in operations page and embed MLflow server start in `make run` lifecycle

**Checkpoint**: Experiment tracking end-to-end: training → MLflow logging → browse/compare in web UI.

---

## Phase 6: User Story 3 — Service Management & Operations Dashboard (Priority: P2)

**Goal**: User can manage all background services (web, MLflow, training) from the web UI — start, stop, restart, view logs in real-time.

**Independent Test**: Start the workbench → navigate to operations page from another LAN device → stop MLflow → verify it stops → start it again → see logs update in real-time via SSE.

### Tests for User Story 3 (TDD)

- [X] T069 [US3] [P] Unit test for `ProcessSupervisor` lifecycle (start, status, stop) in `tests/unit/supervisor/test_supervisor.py`
- [X] T070 [US3] [P] API contract test for `GET /v1/operations/services` and `POST /v1/operations/services/{name}/start` in `tests/unit/api/test_operations.py`

### Implementation for User Story 3

- [X] T071 [US3] [P] Create `anvil/api/v1/health.py` — `GET /v1/health`: service status, DB connectivity, version, uptime
- [X] T072 [US3] Create `anvil/api/v1/router.py` additions — operations endpoints: `GET /v1/operations/services`, `POST /v1/operations/services/{name}/start`, `POST .../stop`, `POST .../restart`, `GET .../logs?tail=N`, `GET .../logs/stream` (SSE)
- [X] T073 [US3] [P] Create `anvil/api/templates/operations.html` — service management dashboard: service cards with status indicators (🟢🔴🟡), start/stop/restart buttons, real-time log viewer (SSE-streamed), uptime/memory widgets
- [X] T074 [US3] [P] Add `GET /v1/operations/services/{name}/logs/stream` SSE endpoint — tails log file via async file reading, yields new lines as SSE events
- [X] T075 [US3] Wire supervisor into god class — `MicroGPTWorkbench` exposes `get_supervisor()`, `get_services()`, `start_service()`, `stop_service()`

**Checkpoint**: Full ops dashboard — manage all services, view logs, health monitoring from browser.

---

## Phase 7: User Story 4 — Dataset Management via Web UI (Priority: P2)

**Goal**: User can upload custom datasets, view vocabulary stats, select dataset for training from the web UI.

**Independent Test**: Upload a custom `.txt` file → see vocabulary stats → select it on training page → train → model generates samples matching the new dataset.

### Tests for User Story 4 (TDD)

- [X] T076 [US4] [P] Unit test for `DatasetRepository` CRUD in `tests/unit/db/test_datasets.py`
- [X] T077 [US4] [P] Unit test for `DatasetService` — file upload, vocabulary computation, document counting in `tests/unit/services/test_datasets.py`
- [X] T078 [US4] [P] API contract test for `POST /v1/datasets` (multipart upload) and `GET /v1/datasets` in `tests/unit/api/test_datasets.py`

### Implementation for User Story 4

- [X] T079 [US4] [P] Create `anvil/db/models/dataset.py` — Dataset ORM model per data-model.md
- [X] T080 [US4] [P] Create `anvil/db/repositories/datasets.py` — `DatasetRepository` with async CRUD, default dataset detection
- [X] T081 [US4] Create `anvil/services/datasets.py` — `DatasetService`: upload file to FileStore, compute vocabulary/document_count, list/delete datasets, seed default names dataset
- [X] T082 [US4] Create `anvil/api/v1/datasets.py` — dataset endpoints: `POST /v1/datasets` (multipart), `GET /v1/datasets`, `GET /v1/datasets/{id}`, `DELETE /v1/datasets/{id}`, `PUT /v1/datasets/{id}`
- [X] T083 [US4] [P] Create `anvil/api/templates/datasets.html` — dataset manager: upload form with drag-and-drop, dataset cards with vocab size/docs count, delete confirmation with unicorn animation 🦄
- [X] T084 [US4] Seed default names dataset — bundle `input.txt` in package (`anvil/core/data/input.txt`), auto-ingest on first `make run` or `make setup`
- [X] T085 [US4] Update TrainingService to accept `dataset_id` parameter — load dataset content from FileStore, build vocabulary, feed to engine

**Checkpoint**: Dataset management complete — upload, browse, select, train on custom data.

---

## Phase 8: User Stories 5, 6, 7 (Priority: P2/P3)

**Goal**: Structured experimentation forms, governance/knowledge base UI, and progressive code walkthrough files.

**Independent Test (US5)**: Change hyperparameters in web UI form, start run, observe different convergence.  
**Independent Test (US6)**: Open vault in Obsidian, verify navigation and note integrity.  
**Independent Test (US7)**: Run `python train0.py` through `python train5.py` sequentially, all produce output.

### Implementation for User Story 5 (Structured Experimentation via Web UI — P2)

- [X] T086 [US5] [P] Improve training page hyperparameter form with presets, validation tooltips, and "save as template" button
- [X] T087 [US5] Add `POST /v1/training/configs` endpoint — save/load training config templates
- [X] T088 [US5] [P] Create config template management in training page — saved configs dropdown, load/delete

### Implementation for User Story 6 (Governance & Knowledge Base — P3)

- [X] T089 [US6] [P] Create `docs/vault/Reference/OpenQuestions.md` — tracking unresolved design questions
- [X] T090 [US6] [P] Create `docs/vault/Reference/DecisionLog.md` — chronological index of all ADRs
- [X] T091 [US6] [P] Create initial ADRs in `docs/vault/Decisions/` documenting key architecture decisions from this spec (async-first, FastAPI, repository pattern, MLflow, implicit namespace)

### Implementation for User Story 7 (Progressive Code Walkthrough — P3)

- [X] T092 [US7] [P] Create `train0.py` at repo root — bigram count table, no neural net, no gradients
- [X] T093 [US7] [P] Create `train1.py` — MLP + manual gradients (numerical & analytic) + SGD
- [X] T094 [US7] [P] Create `train2.py` — Autograd (Value class) replaces manual gradients
- [X] T095 [US7] [P] Create `train3.py` — Position embeddings + single-head attention + RMSNorm + residuals
- [X] T096 [US7] [P] Create `train4.py` — Multi-head attention + layer loop — full GPT architecture
- [X] T097 [US7] [P] Create `train5.py` (aka `train.py`) — Adam optimizer, full training loop, inference sampler (mirrors `anvil/core/engine.py`)
- [X] T098 [US7] [P] Create `diff_stages.py` — CLI script to print diff between any two stage files

**Checkpoint**: All user stories complete.

---

## Phase 9: GPU Support (FR-031)

**Goal**: Optional GPU acceleration — MPS on macOS ARM, CUDA on Linux.

- [X] T099 Create GPU detection in `anvil/core/engine.py` — `detect_gpu()`: try `torch.backends.mps.is_available()`, try `torch.cuda.is_available()`, fall back to CPU
- [X] T100 [P] Create `make train-gpu` Makefile target — sets `USE_GPU=true`, delegates to god class
- [X] T101 Add `use_gpu` parameter to TrainingConfig, god class, and training service — dispatch to MPS or CUDA if available

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final quality, documentation, and completeness tasks.

- [X] T102 Run full lint suite (`make lint`) across entire codebase — fix all ruff, black, isort, pylint issues
- [X] T103 Run full type check (`make typecheck`) — fix all mypy/pyright errors
- [X] T104 [P] Create `CONTRIBUTING.md` — contribution guidelines, commit message conventions (conventional commits), PR workflow
- [X] T105 [P] Run full test suite (`make test`) — confirm 100% coverage across all modules
- [X] T106 [P] Add SSE reconnection handling in `training.html` — client-side `EventSource` auto-reconnect with `Last-Event-ID`
- [X] T107 [P] Add loading/empty/error states to all Jinja2 templates — no blank pages
- [X] T108 [P] Add confirmation dialogs for destructive actions (delete dataset, stop training, delete experiment)
- [X] T109 [P] Add self-diagnosis page at `/v1/health` — web UI health check display
- [X] T110 Run e2e test suite (`make test-e2e`) — verify full lifecycle: start server → train → verify via API → compare experiments → stop server
- [X] T111 Verify all `__init__.py` files contain ONLY public API exports (no side-effect imports or internal wiring)
- [X] T112 Run import checker to verify zero circular imports across the codebase
- [X] T113 Final `README.md` review — ensure quickstart, all features, and architecture overview are documented
- [X] T118 [P] Add graceful degradation test in `tests/e2e/test_graceful_degradation.py` — verify UI loads when MLflow/CUDA unavailable, feature shows as disabled not crashed
- [X] T119 [P] Add PyPy smoke test in `tests/e2e/test_pypy.py` — verify core microgpt engine runs under PyPy (stdlib-only path); optional deps gracefully report incompatibility
- [X] T120 [P] Add migration failure test in `tests/e2e/test_migrations.py` — verify server refuses to start with descriptive error when Alembic detects schema drift
- [X] T121 [P] Add CSS animations and SVG interactions to templates — loading spinners, loss chart entry animations, hover effects on service cards, unicorn idle animation in header
- [X] T122 [P] Add CLI entry point smoke tests in `tests/unit/test_cli.py` — verify `anvil-workbench --help`, `anvil-train --help`, `anvil-stop --help` print usage without errors
- [X] T123 Add optional benchmark in `Makefile` (`make benchmark`) — runs training and measures time against SC-001 (should complete in under 60s on Apple Silicon)

**Checkpoint**: Project is production-ready for educational/experimental use.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately
- **Phase 2 (US0 — Harness)**: Depends on Phase 1 — MUST complete before any code is written
- **Phase 3 (Foundational)**: Depends on Phase 1 + Phase 2 — BLOCKS all user stories
- **Phase 4 (US1) → Phase 10**: All depend on Phase 3 being complete
- **Phase 9 (GPU)**: Depends on Phase 4 (US1) — GPU is an enhancement to training

### User Story Dependencies

- **US0**: No code dependencies — pure documentation and configuration
- **US1**: Needs Phase 3 complete (DB, storage, API skeleton, god class)
- **US2**: Needs US1 training service + Phase 3 foundational (DB, supervisor)
- **US3**: Needs Phase 3 foundational (supervisor, API skeleton)
- **US4**: Needs Phase 3 foundational (DB, storage, FileStore)
- **US5**: Needs US1 web UI + training service
- **US6**: No code dependencies — pure documentation
- **US7**: No code dependencies — standalone educational scripts

### Parallel Opportunities

- All `[P]` tasks within a phase can run in parallel
- US3, US4, US6, US7 can run in parallel after Phase 3 completes (they don't depend on each other)
- US2 must wait for US1 (needs training service)
- US5 must wait for US1 (needs training page)
- Within each user story: models `[P]` → repos `[P]` → services → endpoints → templates `[P]`

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests in parallel (TDD):
Task: "Core engine forward pass in tests/unit/core/test_engine.py"
Task: "Core engine backward pass in tests/unit/core/test_engine.py"
Task: "Training step in tests/unit/core/test_training.py"
Task: "God class training run in tests/unit/test_god_class.py"
Task: "API contract for POST /v1/training/start in tests/unit/api/test_training.py"
Task: "SSE stream in tests/unit/api/test_training.py"

# After tests pass, launch all US1 models in parallel:
Task: "TrainingConfig ORM model in microgpt/db/models/training_config.py"
Task: "Core autograd in microgpt/core/autograd.py"
Task: "Core tokenizer in microgpt/core/tokenizer.py"
Task: "Base template in microgpt/api/templates/base.html"
Task: "Training template in microgpt/api/templates/training.html"
Task: "CSS in microgpt/api/static/style.css"
Task: "Unicorn SVG in microgpt/api/static/unicorn.svg"
```

---

## Implementation Strategy

### MVP First (Phase 1 → 2 → 3 → 4 Only)

1. Complete Phase 1: Setup (project skeleton)
2. Complete Phase 2: Agentic Harness (US0)
3. Complete Phase 3: Foundational (DB, storage, API skeleton, linting)
4. Complete Phase 4: User Story 1 (Training via Web UI)
5. **STOP and VALIDATE**: Can train a model from browser with SSE loss chart? → MVP done!
6. Deploy/demo the MVP

### Incremental Delivery

1. Phase 1 + 2 + 3 → Foundation ready (can run `make setup` and `make test`)
2. Add Phase 4 (US1) → Train via web UI → MVP
3. Add Phase 5 (US2) → Experiment tracking → Compare runs
4. Add Phase 6 (US3) → Operations dashboard → Manage services
5. Add Phase 7 (US4) → Dataset management → Upload custom data
6. Add Phase 8 (US5-7) → Templates, governance docs, progressive walkthrough
7. Add Phase 9 → GPU acceleration
8. Phase 10 → Polish, docs, final validation

---

## Summary

| Phase | Description | Tasks | Parallel [P] |
|-------|-------------|-------|-------------|
| 1 | Setup | 6 (5+1) | 4 |
| 2 | US0 — Agentic Harness (P0) | 8 | 4 |
| 3 | Foundational (Blocking) | 21 (18+3) | 13 |
| 4 | US1 — Train Models via Web UI (P1) 🎯 | 24 | 12 |
| 5 | US2 — Experiment Tracking (P1) | 13 | 5 |
| 6 | US3 — Operations Dashboard (P2) | 7 | 3 |
| 7 | US4 — Dataset Management (P2) | 10 | 4 |
| 8 | US5 + US6 + US7 (P2/P3) | 13 | 9 |
| 9 | GPU Support | 3 | 1 |
| 10 | Polish & Cross-Cutting | 18 (12+6) | 12 |
| **Total** | | **123** | **67** |

**Total tasks**: 123 (67 parallelizable)
**Suggested MVP scope**: Phases 1-4 (59 tasks, 33 parallel)
**Format validation**: ✅ All tasks follow `- [ ] TNNN [P] [USX] Description with file path` format