# Research Report: Bootstrap LLM Workbench

**Phase**: Phase 0 — Technology & Pattern Research  
**Date**: 2026-06-10  
**Spec**: `specs/001-bootstrap-llm-workbench/spec.md`

## Overview

All technical decisions were pre-resolved by the feature specification and user clarifications. This research confirms and documents best practices for each chosen technology.

---

## 1. FastAPI + Async SQLAlchemy + aiosqlite

### Decision
Use `create_async_engine` with `sqlite+aiosqlite:///` driver, `async_sessionmaker` for session factory, FastAPI dependency injection for request-scoped sessions.

### Rationale
Async SQLAlchemy 2.0 provides mature async support. `aiosqlite` is the standard async SQLite driver. FastAPI's `Depends()` system cleanly manages session lifecycle per-request.

### Best Practices
- `expire_on_commit=False` to avoid lazy-load issues after commit
- `autoflush=False`, `autocommit=False` for explicit UoW control
- Use `async_scoped_session` with `request` scope if concurrent requests share sessions
- Session per request: create in dependency, commit on success, rollback on exception

### References
- SQLAlchemy 2.0 AsyncIO docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- fastcrud (1.5k stars) — async CRUD with SQLAlchemy 2.0 + Pydantic V2

---

## 2. FastAPI SSE for Real-Time Streaming

### Decision
Use Starlette's `StreamingResponse` with `text/event-stream` media type. No external SSE library — FastAPI/Starlette built-in support is sufficient. `asyncio.Queue` for pub/sub between training processes and SSE endpoints.

### Rationale
SSE is simpler and more appropriate than WebSocket for unidirectional server-to-client streaming (loss charts, log tailing). Training metrics flow one direction. No bidirectional communication needed.

### Best Practices
- Heartbeat every 15-30s to prevent proxy timeout
- `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no` headers
- Client reconnection via `Last-Event-ID`
- Stream `data:` lines in `data: {json}\n\n` format

### Alternatives Considered
- WebSocket: over-engineered for unidirectional metrics streaming
- Polling: user explicitly rejected; SSE is the mandate
- sse-starlette library: not needed; Starlette's StreamingResponse is sufficient

### References
- realtime-streaming-api — production SSE with topic subscriptions, 10k+ events/sec
- FastAPI SSE guide: https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse

---

## 3. Jinja2 + FastAPI SSR with HTMX for Dynamic Updates

### Decision
Use Jinja2 with async environment (`enable_async=True`). HTMX for partial page updates triggered by SSE events or hx-trigger polling. No heavy JS framework.

### Rationale
Server-side rendering keeps logic in Python (agentic-aligned). HTMX provides dynamic updates without a JS framework or build step. SSE from the server triggers HTMX swaps for loss charts and log tables.

### Best Practices
- Pass `Request` to templates for `url_for()` generation
- HTMX `hx-trigger="every 2s"` for polling fallback; SSE events for real-time data
- Template fragments for partial swaps: `#loss-chart`, `#log-viewer`
- CSS transitions on HTMX swap classes for smooth animations

### References
- HTMX + FastAPI examples: https://github.com/Boadzie/sensor-dashboard
- FastAPI Jinja2 docs: https://fastapi.tiangolo.com/advanced/templates/

---

## 4. SQLAlchemy Repository Pattern + Unit of Work (Async)

### Decision
Repositories receive `AsyncSession` as constructor parameter. Unit of Work at the god class/service layer: commit/rollback at request boundary, never in individual repositories. Base repository class with generic CRUD. Concrete repos per entity.

### Rationale
Repository pattern ensures no DB primitives leak beyond the data layer. Unit of Work ensures ACID transactions span multiple repository operations within a single request. Async throughout.

### Best Practices
- `BaseRepository[ModelType]` generic with `get`, `get_all`, `add`, `update`, `delete`
- UoW exposes repos as properties: `uow.datasets`, `uow.experiments`
- `flush()` for partial persistence within a transaction, `commit()` at the end
- No `session.commit()` or `session.rollback()` outside the UoW boundary

### Alternatives Considered
- Direct SQLAlchemy in services: violates layer isolation (FR-040)
- Active Record pattern: couples data access to business logic

### References
- fastapi-clean-layered-arch-example — Repository + UoW + layered architecture
- AstralMortem/sqlalchemy-repository — async-first, Django-like QuerySet API

---

## 5. Alembic with Async SQLAlchemy

### Decision
Standard `alembic.ini` at project root. Migrations in `migrations/versions/`. `env.py` uses `async_engine_from_config` with async driver. Batch mode enabled for SQLite.

### Rationale
Alembic fully supports async engines via `run_async()`. Async `env.py` is well-documented in the Alembic cookbook. Batch mode required for SQLite ALTER TABLE support.

### Best Practices
- `alembic.ini`: `sqlalchemy.url = sqlite+aiosqlite:///./data/microgpt.db`
- `env.py`: use `async_engine_from_config` + `run_async()`
- Auto-migration on startup via FastAPI lifespan (FR-041)
- `make setup` runs `alembic upgrade head` (FR-047)

### References
- Alembic async cookbook: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic

---

## 6. Pydantic DTOs for Versioned API Contracts

### Decision
Separate DTO classes (Pydantic `BaseModel`) per operation: `Create*`, `Update*`, `Response*`, `ListResponse*`. API versioned via `/v1/` prefix router. Auto-generated OpenAPI/Swagger docs.

### Rationale
Pydantic v2 provides validation, serialization, and OpenAPI schema generation. Separate DTOs prevent coupling between API contract and internal model structure. Version prefix allows non-breaking evolution.

### Best Practices
- `model_config = ConfigDict(from_attributes=True)` for ORM → DTO mapping
- `Annotated` types for rich validation (`Field(gt=0, le=1.0)`)
- Pydantic `model_validate` and `model_dump` for conversion
- FastAPI `response_model` for automatic response filtering

### References
- FastAPI Pydantic docs: https://fastapi.tiangolo.com/tutorial/response-model/
- fastcrud pattern: auto-generated CRUD schemas from SQLAlchemy models

---

## 7. Ruff + Black + isort + pylint Configuration

### Decision
Ruff handles fast linting and can replace black/isort formatting. pylint runs as a separate deep-analysis pass. All configured in `pyproject.toml`. `make lint` runs sequentially: ruff → black --check → isort --check → pylint. `make format` applies ruff format + isort.

### Rationale
Ruff is orders of magnitude faster than flake8/black and covers most rules. pylint provides deeper analysis (duplicate code, design issues) that ruff doesn't cover. Keeping both maximizes code quality.

### Best Practices
- Ruff: `target-version = "py311"`, `line-length = 88`
- Black/isort compatible config (isort `profile = "black"`)
- Per-file ignores for `__init__.py` and `tests/`
- mypy/pyright for static type checking in separate `make typecheck` target

### References
- Ruff docs: https://docs.astral.sh/ruff/
- pyproject.toml configuration for all tools (specified in plan.md `[tool.*]` sections)

---

## 8. MLflow as Managed Subprocess with SQLite

### Decision
MLflow runs as a separate background subprocess managed by the process supervisor. Uses its own sync SQLAlchemy connections to its SQLite tracking store (`./mlruns/`). Independent of the app's async SQLAlchemy. Communicated via `MLFLOW_TRACKING_URI` env var.

### Rationale
MLflow's tracking server uses sync SQLAlchemy internally — this is fine because it runs as a separate process. The async mandate applies only to the main application. The process supervisor (Python `subprocess.Popen` + `os.setsid`) manages MLflow's lifecycle from the operations page.

### Best Practices
- `mlflow server --backend-store-uri sqlite:///mlruns/mlflow.db --host 127.0.0.1`
- `preexec_fn=os.setsid` for process group management (survives terminal exit)
- PID file in `./logs/` for status tracking
- Graceful shutdown via SIGTERM → process group; SIGKILL fallback after timeout

### Alternatives Considered
- W&B: rejected by user in favor of MLflow
- MLflow embedded in-process: not supported with async — MLflow blocks on DB writes

### References
- MLflow tracking docs: https://mlflow.org/docs/latest/tracking.html
- nfo-maker (retro CLI packaging — useful for ASCII/ANSI art in CLI output)