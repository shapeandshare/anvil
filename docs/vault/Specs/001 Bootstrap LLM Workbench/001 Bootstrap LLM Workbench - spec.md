---
title: 001 Bootstrap LLM Workbench - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/001 Bootstrap LLM Workbench/
related:
  - '[[001 Bootstrap LLM Workbench]]'
created: ~
updated: ~
---
# Feature Specification: Bootstrap LLM Workbench

**Feature Branch**: `001-bootstrap-llm-workbench`  
**Created**: 2026-06-10  
**Status**: Draft  
**Input**: User description: "bootstrap boilerplating for this repo using patterns from ../oldgrowth -- this repo will contain a small workbench for creating llms using Karpathy's microgpt.py"

## Clarifications

### Session 2026-06-10

- Q: What feature scope should the bootstrap cover? → A: Broad — include optional web dashboard, GPU training path, and alternative dataset support alongside core training and boilerplate.
- Q: What level of experiment tracking and checkpointing? → A: MLflow (not W&B) with SQLite backend — external experiment management tool integration (adds pip dependencies).
- Q: How should the 5-stage progression be organized? → A: Separate standalone files (`train0.py` through `train5.py`) with a `diff_stages.py` helper to show what changed between versions.
- Q: Where should the constitution and specs live? → A: Default locations — `.specify/memory/constitution.md` (canonical), specs in `specs/` directory.
- User clarified: ALL functionality (including experiment tracking) must be exposed through a web UI using Python server-side rendering with Jinja templates, with exceptions only for `make setup` and `make run`. Multiple UI pages/paths are expected. All Python code uses implicit namespace packages by default — `__init__.py` files allowed only for package public API exports.
- User clarified: Web UI must be accessible on the local network (bind to `0.0.0.0`, not localhost-only). All server processes (web server, MLflow, training jobs) run in the background as daemons with lifecycle management (start/stop/restart) from the UI. An operations/service management page in the UI provides process status, log tailing, and service controls. Logs for all processes must be easily accessible through the UI.
- User clarified: Core logic components MUST use implicit namespace packaging. The entire system MUST be redistributable as a Python package (`pip install`). Python implementation is favored over bash scripts (Makefile and related tooling is acceptable). Favor MLflow for experiment tracking over alternatives; SQLite is acceptable for persistent storage.
- User clarified: Primary target platform is macOS ARM (Apple Silicon) bare metal. Linux support must be planned for (Docker containerization for Linux deployment anticipated). Windows is explicitly excluded.
- User clarified: Implementation order: (1) Agentic harness setup and activation first, (2) project boilerplating second, (3) remainder third. Vault MUST be enriched with discoveries as they are made and at end of each session. TDD, semantic versioning, SOLID, KISS, YAGNI, and ADRs (Architecture Decision Records) are mandatory. ORM required for storage where supported (SQLAlchemy or equivalent for SQLite). Use FastAPI (not Flask) with Pydantic, CRUD, Swagger/OpenAPI docs, versioned API (`/v1/`), API contracts, and DTOs. Always use classes; group constants together. No inline imports — all imports at top of file. Circular import issues MUST be fixed architecturally (restructure modules), never with hacks. Linting: ruff, black, isort, pylint. Support PyPy. Enforce strict explicit typing everywhere. Use Alembic for database migrations.
- User clarified: All database access uses the Repository pattern with ACID transactions. Session/context is shared across repositories within a request boundary — no DB primitives leak beyond the repository layer. Services consume one or more repositories and implement business logic. All services are exposed through a single god class (the workbench entry point). Routes call the god class; the god class can also be instantiated outside HTTP (CLI, tests, other agents). FastAPI dependency injection manages request context. Startup auto-runs Alembic migrations. The user experience must be amazing, descriptive, robust, feature-rich, and easy to install/restart/reconfigure/stop/delete. The entire system is designed for agentic implementation — pit of success for AI agents.
- User clarified: The UI should be whimsical and fun — retro aesthetic with pixel art, ASCII art, ANSI art, SVG illustrations, and CSS animations. It should not take itself too seriously but still be rigorous and complete. Unicorns recommended. Lots of emojis to kick things up a notch. The web UI must really be cool, pop, and be easy to use while looking amazing doing it.
- User clarified: File content storage must use the same repository pattern abstraction as the database — a storage abstraction layer for reading/writing files (datasets, model checkpoints, logs) with a pluggable backend interface. S3 support must be planned for (the abstraction should be S3-ready from day one).
- Q: How should visual assets (pixel art, SVGs, unicorn) be created? → A: Mixed — use an icon library (Font Awesome or similar) for functional UI icons, and AI-agent generated inline SVGs, ASCII art, and pixel art for whimsical/custom assets (unicorn mascot, headers, decorative elements).
- Q: Async vs sync architecture? → A: Fully async — all FastAPI handlers, SQLAlchemy (async via aiosqlite or similar), FileStore I/O, and service layer. If async SQLite proves problematic, swapping to another DB (e.g., asyncpg with PostgreSQL) is acceptable.
- User clarified: Web UI must update without page refresh. Prefer SSE (Server-Sent Events) for real-time streaming (loss charts, log tailing, training progress). Consider WebSocket only if bidirectional communication is needed; SSE is the default for server-to-client streaming.
- User clarified: 100% unit test coverage required across all layers (repositories, services, god class, routes, CLI). Full end-to-end system tests required — start server, train model, verify output via API, stop server.
- User clarified: Use relative imports for all internal package imports. Third-party imports use absolute imports. `__init__.py` files SHALL ONLY exist to declare package exports (e.g., `__all__`, explicit re-exports of the public API surface). They MUST NOT be used for internal wiring, side-effect imports, or namespace initialization. Implicit namespace packages (no `__init__.py`) remains the default everywhere else.
- User clarified: Python dependency lock files are required (e.g., `uv.lock` or `requirements.lock`). All Makefile targets MUST automatically handle virtual environment management — the user MUST NOT need to manually activate, deactivate, or reason about virtual environments when using `make` commands or related CLI tooling.

---

### Implementation Order

The following execution order is mandatory:

1. **Phase 1 — Agentic Harness Setup**: `.specify/memory/constitution.md`, AGENTS.md, vault initialization, ADR framework, `.specify/` tooling, `opencode.json`, session management, vault population with initial discoveries. This phase MUST complete before any code is written.
2. **Phase 2 — Project Boilerplating**: `pyproject.toml`, Makefile, linting configs (ruff, black, isort, pylint), `.gitignore`, package structure with implicit namespace, CI pipeline, `CONTRIBUTING.md`.
3. **Phase 3 — Remainder**: Core training (`anvil.py`, progressive files), FastAPI web server, MLflow integration, operations dashboard, dataset management, experiment tracking UI, GPU support, Alembic migrations, all CRUD endpoints, versioned API.

---

### User Story 0 - Agentic Harness & Governance (Priority: P0)

An AI agent begins a session, reads the constitution and AGENTS.md to understand project rules, discovers the vault with ADRs, prior discoveries, and reference materials, and can autonomously execute specs using the `.specify/` tooling. At session end, the agent enriches the vault with new discoveries and ADRs.

**Why this priority**: All subsequent work is done by AI agents. The harness (constitution, vault, AGENTS.md, opencode.json, .specify/) must exist and be activated before any other work begins, or agents will lack guidance and consistency.

**Independent Test**: Can be verified by starting a new OpenCode session and confirming the agent can read the constitution, discover existing ADRs in the vault, and execute `/speckit.plan` without errors.

**Acceptance Scenarios**:

1. **Given** the harness is initialized, **When** an AI agent begins a session, **Then** it can read `.specify/memory/constitution.md` and `AGENTS.md` to determine project rules before writing code
2. **Given** the vault exists with ADRs, **When** the agent makes an architecture decision, **Then** it records it as an ADR in `docs/vault/Decisions/` following the vault's note conventions
3. **Given** a discovery is made during implementation, **When** the session ends, **Then** the vault is enriched with a discovery note
4. **Given** the `.specify/` tooling is configured, **When** the user runs `/speckit.plan`, **Then** a plan is generated from the active spec

---

### User Story 1 - Train Models via Web UI (Priority: P1)

A developer starts the workbench via `make run`, which launches all background processes (FastAPI web server, process manager, MLflow). They open a browser from any device on the local network and can initiate training, monitor loss in real-time, and see generated samples — all through the browser. The god class orchestrates the entire workflow: routes delegate to the god class, which coordinates services and repositories with ACID safety.

**Why this priority**: The web UI is the primary interaction surface for all functionality. LAN accessibility means team members and other devices can use the workbench without SSH. The layered architecture (repository → service → god class → routes) ensures testability and agentic clarity.

**Independent Test**: Can be tested by starting the workbench on machine A, navigating to `http://<machine-a-ip>:PORT` from machine B's browser, clicking "start training", and seeing loss values update in real-time with generated samples appearing upon completion.

**Acceptance Scenarios**:

1. **Given** the web server is running (`make run`), **When** a user navigates to the training page in a browser, **Then** they can configure hyperparameters (model size, steps, learning rate, temperature) and initiate training
2. **Given** training is running, **When** the user views the training page, **Then** loss values update in real-time and generated samples appear as they are produced
3. **Given** the user environment has only Python 3 standard library, **When** `make setup` completes successfully, **Then** the web server starts and the training UI works (core paths only; GPU/MLflow may be unavailable without their deps)
4. **Given** the god class is called from a test or CLI context (outside HTTP), **When** a training request is made, **Then** it executes with the same service and repository logic as the HTTP path

---

### User Story 2 - Experiment Tracking & Comparison via Web UI (Priority: P1)

A developer runs multiple training experiments with different hyperparameters through the web UI, and can browse, compare, and analyze past runs — loss curves side-by-side, generated samples, and configuration snapshots — all in the browser. All experiment data is stored via MLflow with a SQLite backend, accessible both through the workbench UI and the MLflow native UI.

**Why this priority**: Experiment iteration is core to the educational value. MLflow provides a mature tracking server, and SQLite keeps storage simple and portable.

**Independent Test**: Can be tested by running two training sessions with different learning rates via the web UI, then navigating to the experiments page to see both runs listed with their loss curves overlaid.

**Acceptance Scenarios**:

1. **Given** two training runs have been completed, **When** the user navigates to the experiments page, **Then** both runs are listed with their hyperparameters and final loss values
2. **Given** the user selects two experiments for comparison, **When** the comparison view loads, **Then** loss curves are overlaid and generated samples from both runs are displayed side-by-side
3. **Given** MLflow tracking is enabled, **When** training completes, **Then** the experiment data is logged to MLflow automatically and displayed in the web UI's experiment comparison view

---

### User Story 3 - Service Management & Operations Dashboard (Priority: P2)

A developer accesses the operations page in the web UI and sees the status of all background services — the web server, MLflow tracker, any running training jobs. They can start, stop, or restart services, tail logs in real-time, and browse historical logs — all from the browser. Any device on the local network can reach the UI.

**Why this priority**: With multiple background processes (web server, MLflow, training runs) and LAN accessibility, operators need a single pane of glass to manage the workbench without SSH or terminal access.

**Independent Test**: Can be tested by starting the workbench, navigating to the operations page from another device on the same LAN, viewing the MLflow service status, stopping it via the UI, and confirming the service is no longer running.

**Acceptance Scenarios**:

1. **Given** the workbench is running, **When** a user on another LAN device navigates to `http://<host-ip>:PORT`, **Then** the web UI loads and all functionality is accessible
2. **Given** the operations page is open, **When** the user views the services list, **Then** each service (web server, MLflow, training runner) shows its status (running/stopped/error), PID, uptime, and memory usage
3. **Given** MLflow is stopped, **When** the user clicks "Start" next to it on the operations page, **Then** MLflow starts and its status updates to "running" with live log output
4. **Given** any service is running, **When** the user views its logs in the operations page, **Then** recent log lines are displayed with timestamps and auto-refresh; historical logs are browsable

---

### User Story 4 - Dataset Management via Web UI (Priority: P2)

A developer can upload, select, and manage training datasets through the web UI — upload a custom text file, preview its contents, see vocabulary stats, and select which dataset to use for the next training run.

**Why this priority**: Alternative dataset support was confirmed in the broad scope, and managing datasets through the web UI makes it accessible without CLI flags.

**Independent Test**: Can be tested by uploading a custom text file through the dataset management page, selecting it for training, and verifying the model trains on the new vocabulary and generates matching samples.

**Acceptance Scenarios**:

1. **Given** the user is on the datasets page, **When** they upload a `.txt` file, **Then** the file is stored, its vocabulary size is displayed, and it becomes selectable for training
2. **Given** a custom dataset is selected, **When** training starts, **Then** the model adapts to the new dataset's character vocabulary automatically
3. **Given** no custom dataset has been uploaded, **When** the datasets page loads, **Then** the default names dataset is shown with its stats (32K documents, 27-token vocabulary)

---

### User Story 5 - Structured Experimentation via Web UI (Priority: P2)

A developer modifies hyperparameters through the web UI (model size, training steps, learning rate, temperature), starts a training run from the browser, and watches the loss curve update in real-time. All experimentation happens through the web UI — no CLI flags needed.

**Why this priority**: The workbench's educational value comes from tweaking knobs and seeing what changes. The web UI makes this immediate and visual.

**Independent Test**: Can be tested by changing hyperparameters in the web UI training form, starting a run, and observing the real-time loss chart update with different convergence behavior.

**Acceptance Scenarios**:

1. **Given** the source is organized as modular files, **When** a user modifies `n_embd` from 16 to 32, **Then** the model trains with the larger embedding dimension and the parameter count increases accordingly
2. **Given** the user changes `num_steps` from 1000 to 500, **When** training runs, **Then** it completes in approximately half the time

---

### User Story 6 - Governance and Knowledge Base (Priority: P3)

A developer or AI agent can consult the project constitution to understand non-negotiable principles (zero-dependency core, educational clarity, reproducibility) and browse the documentation vault for architecture decisions, experiment logs, and reference materials.

**Why this priority**: Following oldgrowth's pattern, a constitution and vault provide the governance backbone that keeps AI agents aligned with project values and gives humans a browsable knowledge graph. This enables AI-assisted development at scale.

**Independent Test**: Can be verified by checking that `.specify/memory/constitution.md` exists with at least 3 articles defining core principles, and that `docs/vault/` contains an `index.md` with navigation and at least one governance note.

**Acceptance Scenarios**:

1. **Given** the constitution exists, **When** an AI agent begins a session, **Then** it can read the constitution to understand project principles (zero-dependency, educational clarity, deterministic training) before writing code
2. **Given** the vault exists at `docs/vault/`, **When** a user opens it in Obsidian, **Then** they see an index page with navigation to Governance, Reference, and Decisions sections
3. **Given** an architecture decision is made during implementation, **When** the session ends, **Then** a decision note is recorded in the vault following the vault's note conventions

---

### User Story 7 - Progressive Code Walkthrough (Priority: P3)

A learner can step through the 5-stage progression (bigram → MLP → autograd → attention → full GPT with Adam) to understand how each component is built.

**Why this priority**: Educational progression from simple to complex makes the workbench a teaching tool, following Karpathy's recommended `build_microgpt.py` progression.

**Independent Test**: Can be verified by checking that each numbered stage file exists and can be run independently.

**Acceptance Scenarios**:

1. **Given** the progression files exist (`train0.py` through `train5.py`), **When** a learner runs each in order, **Then** each successive file adds a new capability and runs without errors
2. **Given** the learner reads a file, **When** they compare the diff between stages, **Then** comments explain what each new component adds

---

### Edge Cases

- What happens when `input.txt` already exists (e.g., from a prior run)? It should be used as-is rather than re-downloaded.
- What happens when the dataset is empty or malformed? The model should exit with a clear error message.
- How does the system handle training interruption mid-step? The user should be able to re-run from scratch without stale state.
- What happens when running on a machine without internet access? The included example dataset should be bundled with the repo.
- What happens when a vault note has a broken wikilink? The vault conventions should flag this as something to fix, not block work.
- What happens when the constitution conflicts with a user's explicit instruction? The user's instruction takes precedence, but the conflict should be noted in the relevant spec or session log.
- What happens when Obsidian is not installed? The vault remains readable as plain Markdown files; Obsidian is optional.
- How does the vault stay in sync with the codebase? Decision records are written during sessions; stale notes are flagged with a `stale` field in frontmatter.
- What happens when the web server port is already in use? The server should print a clear error with the port number and suggest an alternative.
- What happens when a user uploads a non-text file as a dataset? The UI should reject it with a message about accepted formats (.txt, .csv).
- How does the web UI handle a training process that crashes? The UI should detect the process exit, display the last loss value, and enable starting a new run.
- What if an `__init__.py` is added to a directory that shouldn't export anything (e.g., a utils module)? CI linting (`pylint`) SHOULD flag unexpected `__init__.py` files. Only directories with a public API surface should have them.
- What happens when a service (e.g., MLflow) crashes unexpectedly? The operations page should show its status as "error" with the last log lines visible. The process supervisor may auto-restart it or leave it stopped based on configuration.
- What happens when `make run` is called twice? The process supervisor should detect that services are already running and print a message rather than starting duplicate processes.
- What happens when the system is shut down without `make stop`? The `logs/` directory retains all logs from the previous session. On next `make run`, the supervisor cleans stale PID files.
- How does the UI handle a very large log file? The operations page should show the last N lines (e.g., 100) by default with a "load more" option, not attempt to render the entire file.
- What happens when a log file is deleted while a service is running? The service should continue writing; the log viewer should handle the missing file gracefully.
- What happens when an environment variable is not set? The system should use its documented default value and log a debug-level message indicating which default is being used.
- What happens when the database file is corrupted? The server should refuse to start and print instructions for recovery (restore from backup or run `alembic downgrade` then `upgrade`).
- What happens when Alembic migration history has drifted from the database schema? The server should refuse to start and print the divergence detected by `alembic check`.
- What happens when the static file directory (`/static`) has missing assets? The UI should gracefully degrade (missing icons show alt text, missing CSS falls back to browser defaults) rather than rendering a blank page.
- What happens when MLflow's SQLite database is in a different location than the app's database? This is expected — MLflow manages its own SQLite file in `./mlruns/`, independent of the app's database in `./data/`.

## Requirements

### Functional Requirements

- **FR-001**: Repository MUST include Karpathy's `anvil.py` as the core training and inference script, with zero third-party Python dependencies (stdlib only).
- **FR-002**: Repository MUST include `input.txt` (the names dataset) or auto-download it on first run, with a fallback bundled copy.
- **FR-003**: Repository MUST provide a `Makefile` with targets for: `setup` (prerequisite check, create venv, install deps from lock file), `run` (start ALL background services: web server, process manager, MLflow), `train` (run default training from CLI), `stop` (gracefully stop all background services), `install` (pip install the package in editable mode), `clean` (remove artifacts), and `help` (list all targets). ALL `make` targets MUST automatically detect, create (if missing), and activate the project virtual environment — the user MUST NOT need to manually run `source venv/bin/activate` or be aware of virtual environment state. Implementation logic MUST be in Python; Makefile targets should delegate to Python scripts where possible.
- **FR-004**: Repository MUST include a `README.md` with: project overview, prerequisites, quick-start instructions (`pip install` and `make run`), explanation of the model architecture, hyperparameter tuning guide, web UI route reference, and instructions for accessing the UI from other LAN devices.
- **FR-005**: Repository MUST include a `.gitignore` that excludes: `__pycache__/`, `.venv/`, `.env`, `logs/`, IDE directories, and OS files.
- **FR-006**: Repository MUST include an `AGENTS.md` file documenting agent behavioral guidelines, project structure, available commands, vault enrichment protocol (discoveries recorded as they are made, vault enriched at end of each session), and ADR creation workflow (pattern from oldgrowth).
- **FR-007**: Repository MUST include the 5-stage progressive training files (`train0.py` through `train4.py`) plus the final `train.py` (`train5.py` equivalent), each a standalone runnable file building on the previous. Repository MUST also include a `diff_stages.py` helper that prints the code diff between any two stages. All files MUST use strict explicit typing and classes where appropriate.
- **FR-008**: Repository MUST configure `.specify/` tooling with the same spec kit structure used by oldgrowth (templates, extensions, scripts) for ongoing feature management.
- **FR-009**: Repository MUST include an `opencode.json` configuration file for OpenCode integration (AI-assisted development).
- **FR-010**: Repository MUST support a `make lint` target that runs ruff (fast linting/formatting), black (formatting check), isort (import sorting check), and pylint (deep analysis) sequentially. All MUST pass for CI. Formatting is auto-applied via `make format` (black + isort).
- **FR-011**: Repository SHOULD include a `CONTRIBUTING.md` with contribution guidelines, commit message conventions, and development workflow.
- **FR-012**: Repository SHOULD include a `Makefile` target `make progressive` that runs all 5 progressive training scripts sequentially to validate they work.
- **FR-013**: Repository MUST include a `.specify/memory/constitution.md` defining the project's non-negotiable principles: zero-dependency core, educational clarity over optimization, seeded reproducibility, and progressive disclosure. A reference SHOULD exist in the vault's Governance section.
- **FR-014**: Repository MUST include an Obsidian-compatible documentation vault at `docs/vault/` with at minimum: `index.md` (entry point with navigation), `Governance/Constitution.md` (governance principles), `Decisions/` (architecture decision records), and `Reference/` (glossary, open questions).
- **FR-015**: The vault MUST use Obsidian-compatible Markdown with YAML frontmatter (`title`, `type`, `tags`, `created`, `updated`) on every note, following oldgrowth's vault conventions.
- **FR-016**: Repository MUST include a `Makefile` target `make vault` that opens or serves the vault documentation (e.g., `make vault-serve` for local preview, or instructions for opening in Obsidian).
- **FR-017**: Repository MUST use MLflow as the primary experiment tracking system (not W&B), with SQLite as the MLflow backend store. MLflow is managed as a background service by the process supervisor with lifecycle controls in the operations page. MLflow manages its own database connections (sync SQLAlchemy to its SQLite tracking store); this is independent of the application's async SQLAlchemy — MLflow runs as a separate process and is not subject to the async mandate.
- **FR-018**: Repository MUST include an alternative dataset mechanism — users SHOULD be able to upload or select a custom dataset through the web UI, with the model adapting to the new vocabulary automatically. Dataset metadata MAY be stored in SQLite.
- **FR-019**: Repository MUST include a FastAPI web server (async handlers, not Flask) using Jinja2 templates for server-side rendered pages and Pydantic models for all data validation and serialization. The server MUST support SSE (Server-Sent Events) for real-time streaming to the UI — loss chart updates, log tailing, and training progress notifications — eliminating page refreshes. Server binds to `0.0.0.0` (all network interfaces) for LAN accessibility, with configurable port. Exposes ALL functionality through: (a) a versioned JSON API at `/v1/` with auto-generated Swagger/OpenAPI docs, CRUD endpoints, request/response DTOs, and API contracts; (b) multiple server-side rendered UI pages that update dynamically via SSE: training dashboard, experiment history/comparison, dataset management, inference/sampling, and operations/service management. The web server MUST be pip-installable as part of the package (`anvil-workbench`).
- **FR-020**: All optional features (GPU, MLflow, custom datasets) MUST degrade gracefully — if a prerequisite (CUDA, MLflow SDK, etc.) is missing, the UI still loads and the feature shows as unavailable rather than crashing.
- **FR-021**: Experiment tracking data (MLflow with SQLite backend) MUST be accessible and comparable through the web UI — displayed alongside locally tracked runs in a unified experiment history view. MLflow's native UI MUST also be accessible through the operations page.
- **FR-022**: The core `anvil.py` script MUST remain zero-dependency (stdlib only); all web UI code, experiment tracking via MLflow, and GPU acceleration MUST be opt-in layers that import their respective dependencies only when activated.
- **FR-023**: ALL core logic components MUST use implicit namespace packages by default — no `__init__.py` files except where explicitly needed for package exports. An `__init__.py` SHALL ONLY exist to declare a package's public API surface (`__all__`, explicit re-exports). It MUST NOT be used for internal wiring, side-effect imports, or namespace initialization. Internal imports MUST use relative imports (e.g., `from .module import X`); third-party imports use absolute imports. Core logic MUST be implemented as classes (not loose functions). Constants MUST be grouped together in dedicated modules, not scattered. All imports MUST be at the top of the file — no inline imports.
- **FR-024**: Repository MUST include a process manager / daemon supervisor (implemented in Python as a class, not loose functions) that manages all background services (web server, MLflow, training runner) — each service runs as a background subprocess with lifecycle controls (start, stop, restart, status) accessible from both the CLI (`make run`, `make stop`) and the operations page in the web UI.
- **FR-025**: The operations page in the web UI MUST display: list of all managed services with status (running/stopped/error), PID, uptime, and resource usage; per-service start/stop/restart buttons; real-time log tailing; and access to historical log files. MLflow's native UI MUST be linked or embedded from the operations page. The operations API MUST be versioned under `/v1/`.
- **FR-026**: All service logs MUST be written to a `logs/` directory (gitignored) with per-service log files, timestamped, and accessible from the operations page in the web UI. Log writing MUST be handled by Python (not shell redirection). Log viewing MUST be available through a versioned API endpoint.
- **FR-027**: Training runs started from the web UI MUST execute as background processes managed by the process supervisor, with their output streamed to logs visible in real-time on the training page. Each run MUST be logged to MLflow (SQLite backend via SQLAlchemy ORM) automatically. Killing a training run from the UI MUST terminate the process gracefully.
- **FR-028**: All managed services (web server, MLflow, training runner) MUST run as background subprocesses managed by the process supervisor — they survive terminal exit via the supervisor's process group management (e.g., `nohup` equivalent, daemonized process groups), not via traditional Unix double-fork daemonization. The process supervisor retains lifecycle control (start/stop/restart/status) and can terminate them on `make stop` or via the operations page.
- **FR-029**: Repository MUST include a `pyproject.toml` with package metadata (`name="anvil"`, version using semantic versioning, dependencies, optional dependency groups, entry points) so the entire system is installable via `pip install .` or `pip install -e .`. The `anvil` core training module MUST be importable as a namespace package after installation. Repository MUST include a dependency lock file (e.g., `uv.lock`, `requirements.lock`) that pins all transitive dependency versions for reproducible installs. The `make setup` target MUST install from the lock file.
- **FR-030**: All implementation logic (service management, log handling, process supervision, configuration) MUST be written in Python. Shell scripts SHOULD be avoided except for thin Makefile wrappers that invoke Python. Critical operations like `make run`, `make stop`, and service management MUST delegate to Python entry points defined in `pyproject.toml`. The project SHOULD prefer PyPy compatibility where practical (stdlib-only core already is; optional dependencies like FastAPI, async SQLAlchemy, and MLflow may have limited PyPy support — these are CPython-only and that is acceptable).
- **FR-031**: Repository MUST support optional GPU acceleration — on macOS ARM via Metal (MPS backend), on Linux via CUDA. Falls back gracefully to CPU if no GPU is available. GPU detection and dispatch MUST be implemented in Python.
- **FR-032**: TDD (Test-Driven Development) is mandatory — tests MUST be written before implementation code for every feature. Unit test coverage MUST be 100% across all layers (repositories, services, god class, routes, API endpoints, CLI entry points). Full end-to-end system tests MUST exist — starting the server, training a model, verifying output via API, stopping the server. A `make test` target MUST run the full test suite (unit + e2e). Coverage reports MUST be generated; CI MUST enforce 100% coverage. A `make test-watch` target SHOULD watch for changes and re-run tests automatically.
- **FR-033**: Semantic versioning (MAJOR.MINOR.PATCH) MUST be used for all releases. The current version MUST be declared in `pyproject.toml` and accessible via `anvil.__version__`. Version bumps MUST follow conventional commit analysis.
- **FR-034**: Architecture Decision Records (ADRs) MUST be created for every significant architecture decision. ADRs live in `docs/vault/Decisions/` following the vault's YAML frontmatter conventions. Each ADR MUST document: title, status (proposed/accepted/deprecated/superseded), context, decision, consequences, and compliance notes.
- **FR-035**: Repository MUST use an async-compatible ORM (SQLAlchemy async with aiosqlite, or equivalent) for all database access. If async SQLite proves problematic, any async-compatible database (e.g., asyncpg with PostgreSQL) MAY be substituted. The Repository pattern MUST be used for all data access — repositories encapsulate all DB operations (CRUD for datasets, experiments, training configs, and any supporting entities like categories or labels for classifying experiments). No SQLAlchemy session, connection, or query primitives may leak outside the repository layer. All operations within a single request context MUST share a single DB session — commit/rollback is managed at the context level (Unit of Work), never by individual repositories. Alembic MUST be used for all database schema migrations. All ORM models MUST be Pydantic-validated at the API layer with DTOs mapping between ORM models and API contracts.
- **FR-036**: The API MUST be versioned with a `/v1/` prefix on all endpoints. Each endpoint MUST have request/response DTOs defined as Pydantic models, Swagger/OpenAPI documentation auto-generated by FastAPI, and CRUD operations for all persistent entities (datasets, experiments, training configs).
- **FR-037**: Repository MUST enforce strict explicit typing — all function signatures MUST have type annotations for all parameters and return types. All class attributes MUST be typed. Mypy or pyright MUST be configured in `pyproject.toml` and run as part of `make lint`.
- **FR-038**: Circular imports MUST be resolved architecturally — by restructuring modules, extracting shared dependencies, or using late-binding patterns within the architecture (never via inline imports, `TYPE_CHECKING` blocks only for type annotation forwarding, never for runtime logic).
- **FR-039**: The AGENTS.md MUST document the vault enrichment protocol: agents record discoveries as they are made during a session, and at session end they enrich the vault with a summary of new discoveries, decisions, and any updates to existing notes.
- **FR-040**: Repository MUST implement a layered architecture: **Repository Layer** (async data access, ACID, Unit of Work with shared DB context per request — no DB primitives leak out) → **Service Layer** (async business logic, consumes one or more repositories, operates within the shared context) → **God Class** (`MicroGPTWorkbench` or equivalent, exposes all async service methods as a single entry point) → **Routes / CLI / Tests** (call the god class). The god class MUST be instantiable outside HTTP routes (CLI, tests, other agent runtimes). FastAPI dependency injection MUST manage request-scoped DB context and inject it into repositories.
- **FR-041**: The FastAPI application lifespan MUST auto-run `alembic upgrade head` on startup before the first request is accepted. Migration failures MUST log a descriptive error and prevent the server from starting (fail-fast).
- **FR-042**: The user experience MUST be amazing, descriptive, robust, and whimsically delightful: clear error messages (not raw Python tracebacks in the UI), descriptive loading/empty/error states on every page, confirmation dialogs for destructive actions, undo support where practical, and a self-diagnosis page showing system health. All real-time data (loss charts, logs, service status) MUST stream via SSE without page refreshes. The `make install` / `make run` flow MUST involve zero manual configuration steps. The visual design MUST use a retro aesthetic — pixel art flourishes, ASCII/ANSI art in the CLI and web UI headers, SVG illustrations that animate on interaction, tasteful CSS animations for transitions and state changes, generous use of emojis throughout 🦄✨, and a unicorn mascot as the workbench's spirit animal. Visual assets use a mixed approach: functional UI icons from a library (e.g., Font Awesome), while whimsical/custom assets (unicorn, ASCII banners, decorative SVGs) are AI-agent generated inline as code. Static assets (CSS, JS, icon library) are served by FastAPI's static file mounting. The UI should not take itself too seriously but must remain functionally rigorous and complete. Every page should have at least one delightful micro-interaction or visual treat.
- **FR-043**: The system MUST be resilient: graceful shutdown on SIGTERM/SIGINT (running training jobs receive a signal and may complete their current step before terminating), automatic service restart on unexpected crash (configurable via ops page), database WAL mode for SQLite concurrency, health check endpoint at `/v1/health`, and self-healing startup that cleans stale PID files and lock files.
- **FR-044**: The entire architecture MUST be designed for agentic implementation — clear module boundaries, self-documenting code, comprehensive logging with correlation IDs, descriptive error types that agents can pattern-match, and a "pit of success" design where the default choices lead to correct behavior.
- **FR-045**: Repository MUST include a file storage abstraction layer (analogous to the DB repository pattern) for all file content — datasets, model checkpoints, experiment artifacts, uploaded files. The abstraction MUST define a pluggable async backend interface with at minimum a local filesystem implementation (using `aiofiles` or equivalent async file I/O). The interface MUST be S3-compatible by design (paths as keys, stream-based I/O, content-type metadata, etags for caching) so that swapping from local storage to S3 requires zero changes to calling code. The abstraction MUST support the same ACID-like guarantees as DB repositories where applicable (write atomicity via temp-file-rename pattern for local, conditional PUT for S3).
- **FR-046**: All configuration (port, database path, log directory, MLflow tracking URI, storage backend) MUST be configurable via environment variables with sensible defaults. Defaults: port `8080`, database at `./data/microgpt.db`, logs at `./logs/`, MLflow tracking at `./mlruns/`. A `.env.example` file MUST document all available variables.
- **FR-047**: Alembic configuration MUST live in the project root (either `alembic.ini` or inline in `pyproject.toml`) with migrations in a `migrations/` directory. The `make setup` target MUST run `alembic upgrade head` to initialize the database schema.
- **FR-048**: The `pyproject.toml` MUST define CLI entry points under `[project.scripts]` for all major operations: `anvil-workbench` (starts the web server), `anvil-train` (runs training from CLI), `anvil-stop` (stops services). These entry points delegate to the god class.

### Explicit Out-of-Scope (v1)

The following features are intentionally excluded from this bootstrapping effort:
- Windows support of any kind
- Distributed/multi-GPU training
- Public REST/gRPC API (the web UI is a private network tool, not a public service)
- Persistent model registry or versioning beyond MLflow's built-in tracking
- Reinforcement learning or fine-tuning workflows
- Mobile or embedded model inference
- Multi-modal training (vision, audio)
- BPE/WordPiece tokenization — character-level is the educational starting point
- User authentication/authorization — the web UI is a local-network development tool

### Key Entities

- **microgpt.py**: The core 200-line GPT implementation in pure Python. Contains: Value class (autograd), GPT architecture (embeddings, attention, MLP, RMSNorm), Adam optimizer, training loop, and inference sampler.
- **Progressive Training Files (train0.py through train5.py)**: Incremental implementations that build from bigram counting to the full GPT. Each file is independently runnable and demonstrates one new concept.
- **Makefile**: Build system with targets for setup, training, linting, cleaning, and progressive validation. Follows oldgrowth conventions.
- **AGENTS.md**: Agent behavioral guidelines document defining how AI agents should operate in this repo, what commands are available, and project conventions.
- **`.specify/memory/constitution.md`** (canonical; root `CONSTITUTION.md` and `docs/vault/Governance/Constitution.md` redirect here): The project constitution — defines non-negotiable principles (zero-dependency, educational clarity, reproducibility, progressive disclosure) that all specs, plans, and implementations must comply with.
- **docs/vault/**: Obsidian-compatible documentation vault. Contains governance notes, architecture decision records (Decisions/), reference materials (Reference/), and experiment session logs. Uses YAML frontmatter and Obsidian wikilinks for cross-referencing.
- **input.txt**: Training dataset of ~32,000 names (one per line). Bundled as a fallback; also auto-downloadable from the makemore repository.
- **Web Server (app.py)**: FastAPI web server (async handlers) with Jinja2 templates for SSR UI pages. Binds to `0.0.0.0` for LAN access. Serves versioned REST API at `/v1/` with auto-generated Swagger/OpenAPI docs. Uses Pydantic DTOs for all request/response contracts. Runs as a background daemon managed by the process supervisor.
- **Jinja2 Templates (`templates/`)**: Server-side rendered HTML templates for all web UI pages: base layout, training, experiment comparison, dataset manager, inference, and operations.
- **ORM + Alembic**: Async SQLAlchemy ORM for all database access (aiosqlite initially). Alembic manages schema migrations. Pydantic models provide API-layer validation and DTOs bridging ORM models and API contracts.
- **Versioned REST API (`/v1/`)**: FastAPI router with CRUD endpoints for datasets, training configurations, experiments. Auto-generated Swagger docs. All endpoints use Pydantic DTOs for request/response contracts.
- **Process Manager / Daemon Supervisor**: Async Python class managing all background services — web server, MLflow tracker, training jobs. Provides lifecycle controls (start/stop/restart/status) via CLI and web UI. Writes per-service logs to `logs/`. Uses managed subprocess groups (not Unix daemonization) so the supervisor retains lifecycle control.
- **Operations Page (`/ops`)**: Web UI page for service management. Shows service health dashboard, per-service lifecycle buttons, real-time log viewers, and historical log browsing.
- **Log Store (`logs/`)**: Directory of per-service log files with timestamps. Gitignored. Each service writes its own log file (e.g., `logs/web.log`, `logs/mlflow.log`, `logs/train-001.log`). Accessible through the operations page.
- **GPU Training Path**: Optional GPU acceleration — MPS on macOS ARM, CUDA on Linux. Falls back to CPU automatically.
- **MLflow + SQLite**: Primary experiment tracking system (runs as a separate managed background process with its own sync SQLAlchemy connections — independent of the app's async ORM). MLflow Tracking Server manages its own SQLite database in `./mlruns/`. All training runs log metrics, params, and artifacts to MLflow automatically.
- **pyproject.toml**: Python package configuration declaring the `anvil-workbench` package with semver, dependencies, optional extras, flake8/ruff/black/isort config, mypy/pyright config, and entry points. Enables `pip install .` distribution.
- **Repository Layer**: Data access classes (DatasetRepository, ExperimentRepository, TrainingConfigRepository) encapsulating all CRUD operations via SQLAlchemy. No DB session or query primitives leak outside — repositories accept a shared context and execute within it. Unit of Work pattern: commit/rollback at the context level, never in individual repositories.
- **Service Layer**: Business logic classes (TrainingService, DatasetService, ExperimentService) that consume one or more repositories. Services operate within the shared DB context provided by the calling layer. No direct database access — all data goes through repositories.
- **God Class (`MicroGPTWorkbench`)**: Single async entry point exposing all service methods as a unified interface. Routes call this class. It is instantiatable outside HTTP (CLI, tests, agent runtimes). FastAPI dependency injection provides the request-scoped DB context.
- **FastAPI Lifespan & Startup**: Application startup auto-runs `alembic upgrade head` before serving requests. Fail-fast on migration errors. Graceful shutdown on SIGTERM/SIGINT. Health check endpoint at `/v1/health`.
- **Shared DB Context**: A request-scoped SQLAlchemy session managed by FastAPI dependencies. Repositories receive this context and execute within it. Commit occurs on successful response; rollback on exception. No DB primitive leaks beyond the repository boundary.
- **Storage Repository (FileStore)**: Pluggable async file storage abstraction implementing the same repository pattern as the DB layer. Interface: `get(path)`, `put(path, stream)`, `delete(path)`, `list(prefix)`. Local filesystem implementation uses `aiofiles` for async I/O with temp-file-rename for atomic writes. S3 backend interface is designed but not implemented in v1 (configuration-ready). Used for datasets, model checkpoints, experiment artifacts, and uploaded files.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A first-time developer can clone the repo, run `make setup && make train`, and see the loss decrease from ~3.3 to below ~2.5 within 60 seconds on a modern laptop.
- **SC-002**: All progressive training scripts (`train0.py` through `train5.py`) run without errors when executed sequentially.
- **SC-003**: The repo passes a basic structure audit: Makefile, README.md, AGENTS.md, .gitignore, .specify/, and at least one training script exist at the root.
- **SC-004**: A developer unfamiliar with transformers can understand the full GPT algorithm by reading the progressive files and comments, without external references.
- **SC-005**: The project constitution exists at `.specify/memory/constitution.md` with at least 3 articles defining non-negotiable principles, and an AI agent can read it to determine project rules.
- **SC-006**: The documentation vault at `docs/vault/` contains an index page with navigation links, at least one Governance note, one Decision record, and one Reference note — all with valid YAML frontmatter.
- **SC-007**: The web UI is accessible from any device on the local network at `http://<host-ip>:PORT`, serving multiple pages (training dashboard, experiment history, dataset management, inference, operations) server-side rendered with Jinja2 templates.
- **SC-008**: Starting a training run from the web UI updates the loss chart in real-time via SSE (Server-Sent Events), and generated samples appear on the page upon completion without a page refresh. The training process runs in the background and survives terminal exit.
- **SC-009**: Uploading a custom dataset through the web UI makes it available for selection in the training page, and training with it produces samples matching the new dataset's patterns.
- **SC-010**: The experiment history page lists all past runs with hyperparameters, final loss, and generated samples; selecting two runs shows their loss curves overlaid for comparison. All run data is stored via MLflow SQLite backend.
- **SC-011**: The core `anvil.py` script imports zero third-party packages — running `python microgpt.py` with only stdlib installed works without errors.
- **SC-012**: Implicit namespace packages are the default — `__init__.py` files exist ONLY where needed for package public API exports. No `__init__.py` exists for internal wiring or namespace initialization. All internal imports use relative paths.
- **SC-013**: Running `pip install .` from the repo root installs the `anvil-workbench` package; `python -c "import microgpt"` succeeds. Running `make setup` creates a venv (if missing), installs all dependencies from the lock file, and prints success. `make run` starts all background services via the venv's Python; navigating to `http://<host-ip>:PORT` from any LAN device shows the workbench UI. Running `make stop` stops all services gracefully. No manual venv activation is ever required.
- **SC-014**: The operations page lists all managed services with correct status (running/stopped/error); clicking "Stop" on a service changes its status to "stopped" within 5 seconds; clicking "Start" resumes it. MLflow's native UI is accessible from the operations page.
- **SC-015**: Each service's logs are viewable from the operations page with timestamps and auto-refresh; historical logs are accessible per-service in the `logs/` directory. All log I/O is handled by Python.
- **SC-016**: A training job started from the web UI continues running after the browser tab is closed or the launching terminal is exited. All training metrics are logged to MLflow automatically.
- **SC-017**: Running `make run` or service management from the operations page invokes Python entry points (not shell scripts) for all service lifecycle operations.
- **SC-018**: All linting targets pass (`make lint`): ruff, black --check, isort --check, pylint — all exit with code 0 on clean code. `make format` auto-applies black + isort.
- **SC-019**: All function signatures and class attributes have complete type annotations. Running mypy or pyright on the codebase produces zero type errors.
- **SC-020**: All database schema changes are managed via Alembic migrations. Running `alembic upgrade head` applies all pending migrations without error. Running `alembic downgrade -1` rolls back cleanly.
- **SC-021**: The versioned API at `/v1/` serves Swagger docs at `/v1/docs`; all CRUD endpoints for datasets, experiments, and training configs return correct Pydantic-validated DTOs.
- **SC-022**: Tests exist for all features and pass (`make test`). Unit test coverage is 100% across all layers. End-to-end system tests cover the full lifecycle (start → train → verify → stop). Coverage report shows 100%. New features require tests written before implementation code (TDD).
- **SC-023**: ADRs exist in `docs/vault/Decisions/` documenting all significant architecture decisions with status, context, decision, and consequences. Vault is enriched with discoveries after each session.
- **SC-024**: The package version follows semantic versioning in `pyproject.toml`; `anvil.__version__` is accessible at runtime.
- **SC-025**: No circular imports exist in the codebase — verified by running `make lint` (includes import cycle detection via pylint).
- **SC-026**: The core `anvil.py` runs correctly under PyPy. Optional dependency layers (FastAPI, async SQLAlchemy, MLflow) gracefully detect CPython vs PyPy and report incompatibility rather than crashing.
- **SC-027**: The god class (`MicroGPTWorkbench`) can be instantiated, called with training parameters, and produce results identically from HTTP route, CLI, and test contexts.
- **SC-028**: No SQLAlchemy session, connection, or query primitives appear outside the repository layer — verified by module boundary audit (linter rule or explicit test).
- **SC-029**: Server startup runs `alembic upgrade head` automatically; if a migration fails, the server refuses to start with a descriptive error.
- **SC-030**: SIGTERM/SIGINT stops all background services gracefully within 5 seconds; no orphaned processes remain. Health check endpoint returns 200 when services are healthy.
- **SC-031**: All UI pages display descriptive loading states, human-readable error messages (no raw tracebacks), confirmation dialogs for destructive actions, and at least one whimsical visual element (pixel art, emoji, SVG animation, or ASCII art header). The CLI output includes ANSI art or a unicorn 🦄 in the welcome banner.
- **SC-032**: The file storage abstraction layer supports local filesystem reads and writes. A mock S3 backend can be swapped in via configuration with zero changes to service-layer code. Dataset upload and model checkpoint save go through the same abstraction.
- **SC-033**: All configurable settings (port, database path, log dir, MLflow URI) have documented defaults via `.env.example`. Changing `MICROGPT_PORT=9090` in `.env` and running `make run` starts the server on port 9090.
- **SC-034**: Running `anvil-workbench` CLI entry point (after `pip install`) starts the web server identically to `make run`. Running `anvil-train --help` prints usage without errors.

## Assumptions

- The primary development language is Python 3, with zero external dependencies for the **core** training logic (stdlib only). Web UI, MLflow, and GPU support add pip dependencies conditionally.
- The target audience is developers and learners exploring LLM fundamentals, not production deployment.
- Prerequisites assume macOS ARM (Apple Silicon) as the primary development platform. Linux support is planned but not required for v1. Windows is explicitly excluded.
- The `input.txt` names dataset from makemore is acceptable for educational purposes.
- The 5-stage progression follows Karpathy's recommended ordering: bigram → MLP + gradients → autograd → attention → full GPT + Adam.
- Since the core training has zero dependencies, optional extras (web, mlflow, gpu) are declared as optional `[project.optional-dependencies]` in `pyproject.toml`.
- No GPU or specialized hardware is required — all training runs on CPU.
- The `.specify/` tooling and `opencode.json` configuration are included for AI-assisted development but are optional for the core user experience.
- The web UI is implemented using FastAPI (async handlers) with Jinja2 templates for SSR pages and Pydantic models for all API data validation. The server binds to `0.0.0.0` for LAN accessibility. No authentication — it is a private network tool.
- All server processes (web server, MLflow, training runner) run as background daemons managed by a Python-based process supervisor. They survive terminal exit and are controlled via the web UI or CLI (`make run`/`make stop`).
- MLflow is the exclusive experiment tracking system, using SQLite as its backend store via async SQLAlchemy ORM. Training runs log all metrics, params, and artifacts to MLflow automatically.
- GPU acceleration targets Apple Silicon MPS on macOS ARM and CUDA on Linux, with graceful CPU fallback on both. The `make train-gpu` target follows the same pattern.
- Alternative datasets are managed through the web UI; the model rebuilds its vocabulary on the fly — no dataset registry needed.
- ALL Python code uses implicit namespace packages by default — `__init__.py` files exist ONLY for package public API exports. Core logic is implemented as classes with grouped constants. All imports are at the top of files (no inline imports). Circular deps are resolved architecturally.
- Service logs are written to `logs/` with per-service files, handled entirely by Python. Log rotation is not required for v1.
- The core `anvil.py` remains a standalone script runnable without the web server. The web server imports and orchestrates it.
- The entire system is distributable as a pip package (`pyproject.toml` with `anvil-workbench`). `make` targets delegate to Python entry points. Docker containerization for Linux deployment is anticipated but not required for v1.
- TDD is mandatory: tests are written before implementation for every feature. The project uses pytest (or equivalent) with a `make test` target.
- Linting is enforced via ruff, black, isort, and pylint. Strict typing is enforced via mypy or pyright. All run via `make lint`.
- ADRs are created for every significant architecture decision and stored in `docs/vault/Decisions/`. The vault is enriched with discoveries during and at the end of each session.
- PyPy compatibility is preferred for the stdlib-only core (which works natively). Optional dependency layers (FastAPI, async SQLAlchemy, MLflow) are CPython-only — they gracefully detect and report incompatibility rather than crashing.
- The API follows contract-first design: Pydantic DTOs define the contract, FastAPI auto-generates OpenAPI/Swagger docs, and all endpoints are versioned under `/v1/`.
- Database access follows the Repository pattern with ACID transactions and Unit of Work. A shared async SQLAlchemy session is managed per-request via FastAPI dependency injection. No DB primitives leak outside repositories. If async SQLite proves problematic, another async-compatible DB (e.g., asyncpg + PostgreSQL) may be substituted.
- A god class (`MicroGPTWorkbench`) exposes all service methods as a single entry point consumed by routes, CLI, and tests. Services consume repositories; repositories never access services.
- FastAPI lifespan auto-runs Alembic migrations on startup. The system fails fast on migration errors. Graceful shutdown handles SIGTERM/SIGINT.
- The user experience is designed for clarity and resilience: descriptive states for every UI view, confirmation dialogs for destructive actions, human-readable errors, zero-config setup, and self-healing on crash.
- The entire codebase assumes agentic implementation — modular boundaries, clear contracts, comprehensive logging with correlation IDs, and a pit-of-success design where defaults lead to correct behavior.
- The UI embraces whimsy and retro aesthetics: pixel art, ASCII/ANSI art, SVG illustrations, CSS animations, a unicorn mascot 🦄, and generous emoji use. Fun and rigorous are not mutually exclusive — whimsy never undermines correctness or completeness.
- File storage uses the same repository pattern as the database — a pluggable `FileStore` abstraction with a local filesystem backend. The interface is S3-compatible by design for future backend swaps with zero service-layer changes.
- The constitution follows oldgrowth's pattern of defining non-negotiable principles (articles) that constrain all implementation decisions, adapted to this project's scope.
- The vault is designed for Obsidian but readable as plain Markdown; it is a documentation surface, not a runtime requirement.
- The vault structure mirrors oldgrowth's key directories (Governance, Decisions, Reference, Sessions) but scaled proportionally to a smaller project.
- Constitution amendments follow the same governance process: documented, approved, and versioned.
