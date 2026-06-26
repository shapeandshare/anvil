---
title: ADR-001 — Architecture Decisions for Bootstrap LLM Workbench
type: decision
tags:
- type/decision
- domain/governance
created: 2026-06-10
updated: 2026-06-10
aliases:
- ADR-001 — Architecture Decisions for Bootstrap LLM Workbench
source: agent
related:
  - '[[Design/Design]]'
code-refs:
  - pyproject.toml
  - AGENTS.md
  - .specify/memory/constitution.md
  - anvil/api/
---

# ADR-001: Bootstrap Implementation Architecture

**Status**: Accepted

## Context
Initial bootstrapping of the anvil required decisions on technology stack, architecture patterns, and implementation approach.

## Decisions

### 1. Tech Stack
- **Language**: Python 3.11+
- **Web Framework**: FastAPI (async) with Jinja2 templates and SSE streaming
- **ORM**: SQLAlchemy 2.0 async with aiosqlite
- **Migrations**: Alembic
- **Validation**: Pydantic v2
- **Experiment Tracking**: MLflow with SQLite backend
- **Testing**: pytest + pytest-asyncio + httpx + coverage.py
- **Linting**: ruff + black + isort + pylint + mypy

### 2. Architecture
- **Layered**: Repository → Service → God Class → Routes/CLI
- **Patterns**: Repository, Unit of Work, Dependency Injection
- **Async**: Fully async web/db/storage layers; sync core engine
- **Namespace**: PEP 420 implicit namespace packages

### 3. Distribution
- `pyproject.toml` with `[project.scripts]` entry points
- Optional dependency groups for web, GPU, dev

### 4. UI Philosophy
- Server-side rendering with Jinja2 + HTMX
- SSE for real-time updates (no WebSocket)
- Retro aesthetic: pixel art, ASCII, SVG, unicorn mascot 🦄

## Consequences
- Easy pip installation with zero-config setup
- Async complexity with SQLite (may need PostgreSQL if scaling)
- MLflow runs as separate process (cannot be fully async)
- Educational clarity maintained for core algorithm

## Compliance
- Verified by architecture audit in `make lint` and CI pipeline
- ADRs required for any deviation

## See Also

- [[Decisions/README|Decisions]]
