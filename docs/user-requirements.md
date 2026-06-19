# Bootstrap LLM Workbench — User Requirements

**Date**: 2026-06-11  
**Scope**: All requirements specified during the `/speckit.specify` and `/speckit.clarify` sessions for the `001-bootstrap-llm-workbench` feature.

---

## Architecture & Patterns

- Constitution and vault infrastructure for governance and documentation knowledge base
- Layered architecture: **Repository → Service → God Class → Routes/CLI**
- Repository pattern with ACID transactions and Unit of Work — no DB primitives leak outside repositories
- Shared DB context per request context; commit/rollback managed at the context level, never in individual repositories
- God class (`AnvilWorkbench`) as single entry point exposing all service methods; instantiatable outside HTTP (CLI, tests, other agents)
- Services consume one or more repositories for business logic
- FastAPI dependency injection manages request-scoped DB context
- Circular imports must be fixed architecturally (restructure modules) — never with hacks or inline imports
- SOLID, KISS, YAGNI principles enforced throughout

## Web UI

- ALL functionality exposed through a web UI with multiple pages and paths
- Exceptions: only `make setup` and `make run` may lack web UI exposure
- Python server-side rendering with Jinja2 templates
- No page refreshes — SSE (Server-Sent Events) for real-time data streaming; WebSocket only if bidirectional communication needed
- LAN accessibility: web server binds to `0.0.0.0` (all network interfaces), not localhost-only
- SVG illustrations that animate on interaction; tasteful CSS animations for transitions and state changes
- Retro whimsical aesthetic: pixel art, ASCII/ANSI art in CLI and web UI headers, generous emoji use, unicorn mascot 🦄
- Visual assets use a mixed approach: functional UI icons from a library (e.g., Font Awesome), whimsical/custom assets AI-agent generated inline as code
- Amazing, descriptive, robust, feature-rich UX that does not take itself too seriously but remains rigorous
- Operations/service management page in the UI for background process lifecycle and log viewing
- FastAPI mounts static file directory for CSS, JS, icon library, SVG assets

## Tech Stack

- **Web framework**: FastAPI (not Flask) with async handlers
- **ORM**: SQLAlchemy 2.0+ with async support (`aiosqlite`)
- **Data validation**: Pydantic v2 with DTOs separating API contracts from ORM models
- **API design**: Versioned REST API (`/v1/`), CRUD endpoints, auto-generated Swagger/OpenAPI docs, Pydantic request/response contracts
- **Experiment tracking**: MLflow (not W&B) with SQLite backend; MLflow runs as a separate managed background process with its own sync connections
- **Database**: SQLite initially; if async SQLite proves problematic, another async-compatible DB (e.g., asyncpg + PostgreSQL) may be substituted
- **Migrations**: Alembic for all database schema changes
- **Storage abstraction**: Pluggable file storage (`FileStore`) with S3-ready interface — local filesystem implementation via `aiofiles` with atomic writes
- **Configuration**: All settings configurable via environment variables with sensible defaults, documented in `.env.example`
- **Linting**: ruff, black, isort, pylint — all configured in `pyproject.toml`, run via `make lint`
- **Type checking**: mypy or pyright enforced via `make typecheck`
- **CLI entry points**: Defined under `[project.scripts]` — `anvil-workbench`, `anvil-train`, `anvil-stop` delegating to the god class

## Code Style

- Implicit namespace packages (PEP 420) — authoritative namespace levels get bare `__init__.py` (docstring-only, no re-exports); data-only directories have no `__init__.py`
- Core logic implemented as classes (not loose functions); constants grouped together in dedicated modules
- No inline imports — all imports at the top of the file
- Internal imports use relative paths (`from .module import X`); third-party imports use absolute paths
- `__init__.py` files at authoritative namespace levels are bare (docstring-only) — no re-exports, no imports, no internal wiring. They assert ownership of that namespace level, not declare a public API surface
- Strict explicit typing on all function signatures (parameters and return types) and all class attributes
- PyPy compatibility preferred for the stdlib-only core; optional dependency layers gracefully report incompatibility rather than crashing

## Testing & Quality

- **TDD mandatory**: Tests written before implementation (Red-Green-Refactor) for every feature
- **100% unit test coverage** across all layers (repositories, services, god class, routes, API endpoints, CLI entry points)
- **Full end-to-end system tests**: start server → train model → verify output via API → stop server
- Coverage reports generated; CI enforces 100% coverage
- `make test` runs the full test suite (unit + e2e); `make test-watch` watches for changes
- pytest + pytest-asyncio + httpx (AsyncClient) for the test framework

## Versioning & Governance

- **Semantic versioning** (MAJOR.MINOR.PATCH) for all releases; version declared in `pyproject.toml` and accessible via `anvil.__version__`
- Version bumps follow conventional commit analysis
- **ADRs** (Architecture Decision Records) created for every significant architecture decision; stored in `docs/vault/Decisions/` with status, context, decision, consequences, and compliance notes
- Vault enriched with discoveries during and at end of each session

## Build & Distribution

- pip-installable Python package (`anvil-workbench`) with `pyproject.toml`
- Optional dependency groups for web, GPU, and dev extras
- Python dependency lock files required (e.g., `uv.lock` or `requirements.lock`)
- Python-first implementation — favor Python over bash scripts; Makefile acceptable for tooling wrappers
- ALL Makefile targets automatically detect, create (if missing), and activate the project virtual environment — user never manually activates a venv

## Platform

- **Primary target**: macOS ARM (Apple Silicon) bare metal
- **Future target**: Linux (Docker containerization for deployment anticipated)
- **GPU acceleration**: MPS on macOS ARM, CUDA on Linux — graceful CPU fallback
- **No Windows**: explicitly excluded

## Operations & Resilience

- All server processes (web server, MLflow, training runner) run as background subprocesses managed by a process supervisor
- Processes survive terminal exit via process group management (not Unix double-fork daemonization)
- Supervisor retains lifecycle control (start/stop/restart/status) from CLI and operations UI
- Service lifecycle management available from the operations page in the UI
- Logs for all processes written to `logs/` with per-service files; accessible through the operations page
- FastAPI startup auto-runs `alembic upgrade head`; fail-fast on migration errors
- Graceful shutdown on SIGTERM/SIGINT; health check endpoint at `/v1/health`
- System designed for ease of installation, restart, reconfiguration, stop, and deletion

## Project Management

- **Implementation order**: (1) Agentic harness setup and activation, (2) Project boilerplating, (3) Remainder — Phase 1 must complete before any code is written
- Vault enriched with discoveries as they are made during a session, and summarized at end of each session
- Pit-of-success design for agentic implementation — defaults lead to correct behavior
- Agentic implementation assumed throughout — clear module boundaries, self-documenting code, comprehensive logging with correlation IDs, pattern-matchable error types