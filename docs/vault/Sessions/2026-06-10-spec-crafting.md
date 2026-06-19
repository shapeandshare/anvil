---
title: Spec Crafting Session — 2026-06-10
type: session
tags: [type/session-log, domain/governance]
created: 2026-06-10
updated: 2026-06-11
---

# Session: Spec Crafting & Implementation

## Summary
Complete bootstrap of the anvil repository through iterative spec crafting and full implementation. The feature specification was refined through extensive user clarifications covering architecture, UI philosophy, tech stack, operations, testing, and deployment. All 125 implementation tasks completed and verified.

## Key Decisions Made During Spec Crafting

### Architecture
- **Layered pattern**: Repository → Service → God Class → Routes/CLI with ACID and Unit of Work
- **Repository pattern**: No DB primitives leak outside repositories; shared context per request
- **God class**: `MicroGPTWorkbench` as single entry point, instantiatable outside HTTP
- **Async-first**: Fully async throughout (FastAPI, SQLAlchemy, FileStore, service layer)

### Web UI & UX
- **SSE over WebSocket**: Server-Sent Events for real-time streaming (loss charts, logs)
- **Jinja2 SSR**: All UI pages server-side rendered (no JS framework)
- **LAN access**: Server binds to `0.0.0.0` for multi-device accessibility
- **Visual assets**: Icon library for functional icons; AI-generated inline SVGs/ASCII for whimsy
- **Retro whimsy**: Pixel art, ASCII/ANSI headers, unicorn mascot 🦄, CSS animations, SVG illustrations

### Tech Stack
- **FastAPI** over Flask (async handlers)
- **MLflow** over W&B (SQLite backend, runs as separate managed process)
- **SQLite** initially; asyncpg/PostgreSQL if async SQLite proves problematic
- **Pydantic v2** for all DTOs and API contracts with versioned `/v1/` API
- **Ruff + black + isort + pylint** for linting; mypy for type checking

### Code Style
- **Implicit namespace** (PEP 420) — `__init__.py` only for public API exports
- **Relative imports** for internal code; absolute for third-party
- **Strict explicit typing** everywhere (mypy or pyright enforced)
- **Classes not functions** for core logic; constants grouped

### Operations
- **Process supervisor**: Python-based, manages background services as subprocess groups
- **Auto-venv**: Makefile creates/activates `.venv` automatically — never manual
- **Lock files**: `requirements.lock` for reproducible installs
- **Environment config**: `.env.example` documents all variables with sensible defaults

## Discoveries
- Python 3.9 is the default on macOS (Xcode CLT) — project requires 3.11 via Homebrew
- setuptools fails on flat-layout with multiple top-level dirs — requires explicit `[tool.setuptools.packages.find]`
- Base.metadata.create_all creates zero tables if ORM models are not imported first — models must be registered with metadata
- SSE via Starlette `StreamingResponse` works without external `sse-starlette` library
- `run_id` must be reserved before async task starts so SSE stream can find the queue immediately

## Artifacts Created
- `specs/001-bootstrap-llm-workbench/spec.md` — full feature specification
- `anvil/` — complete Python package (22 modules)
- `.specify/memory/constitution.md`, `AGENTS.md`, `docs/vault/` — governance and agentic harness
- 10 passing tests (unit + e2e HTTP + DB CRUD + training)
- `docs/user-requirements.md` — consolidated user requirements reference