# microgpt-workbench — Agent Guidelines

**Last updated**: 2026-06-12

## Project Overview

microgpt-workbench is a pip-installable Python package wrapping Karpathy's microgpt.py with a FastAPI web server, MLflow experiment tracking, and a retro whimsical UI. The system follows a layered architecture: Repository → Service → God Class → Routes/CLI.

## Quick Reference

### Commands

| Command | Purpose |
|---------|---------|
| `make setup` | Create venv, install deps from lock file, init DB |
| `make run` | Start all background services (web + MLflow) |
| `make stop` | Stop all background services |
| `make train` | Run training from CLI |
| `make test` | Run full test suite |
| `make lint` | Run ruff → black --check → isort --check → pylint |
| `make format` | Auto-format (black + isort) |
| `make typecheck` | Run mypy/pyright |
| `make clean` | Remove artifacts |

### Project Structure

```
microgpt/          # Python package (implicit namespace)
├── core/          # Stdlib-only training engine
├── db/            # async SQLAlchemy + repositories
├── services/      # Business logic
├── api/           # FastAPI + Jinja2 + SSE
├── storage/       # FileStore abstraction
└── supervisor/    # Process manager
```

## Agent Behavioral Principles

1. **Constitution First** — Read `CONSTITUTION.md` before writing any code. All work must comply.
2. **TDD Always** — Write tests before implementation (Red-Green-Refactor). 100% coverage required.
3. **Vault Enrichment** — Record discoveries in `docs/vault/` during sessions. Enrich vault at session end.
4. **ADR for Decisions** — Every significant architecture decision gets an ADR in `docs/vault/Decisions/`.
5. **Layer Discipline** — Repositories access DB only. Services consume repositories. God class exposes services. Routes call god class. No shortcuts.
6. **Implicit Namespace** — No `__init__.py` except for public API exports. All internal imports relative.
7. **Async Throughout** — Web, DB, storage layers are async. Core engine is sync (exception).
8. **No Circular Imports** — Restructure modules architecturally if circular deps appear.

## Vault Enrichment Protocol

### During a session:
- When you discover a non-obvious constraint, write a discovery note to `docs/vault/`
- When you make an architecture decision, write or update an ADR in `docs/vault/Decisions/`

### At session end:
- Update `docs/vault/Sessions/` with a session log
- Update any notes that are stale
- Ensure all wikilinks resolve

## Architecture Rules

- Core engine (`microgpt/core/`) has ZERO pip dependencies
- All file paths use relative imports within the package
- Constants grouped together in dedicated modules
- Imports at top of file only (no inline imports)
- Classes for all logic (no loose functions)
- Strict explicit typing on all function signatures

## Active Technologies
## Active Technologies
- Python 3.11+ + Existing project deps (FastAPI, SQLAlchemy, aiofiles) + `pathspec` (lightweight gitignore pattern matching, pure Python, no binary deps) (002-directory-corpus-ingestion)
- SQLite via async SQLAlchemy for corpus metadata; filesystem via existing `LocalFileStore` or reference to original directory paths (002-directory-corpus-ingestion)
- FastAPI, SQLAlchemy (async), MLflow, Jinja2, pytest (all existing — no new deps) (002-model-registry-tracking)
- SQLite (async SQLAlchemy) for metadata, local filesystem (`data/models/`) for model artifacts (002-model-registry-tracking)
- Python 3.11+ + FastAPI, SQLAlchemy (async), aiofiles, pathspec (all existing) (003-dataset-curation)
- SQLite via async SQLAlchemy (metadata); local filesystem via existing `LocalFileStore` (sample content, curation artifacts) (003-dataset-curation)

## Recent Changes
- 002-directory-corpus-ingestion: Added Python 3.11+ + Existing project deps (FastAPI, SQLAlchemy, aiofiles) + `pathspec` (lightweight gitignore pattern matching, pure Python, no binary deps)
- 002-model-registry-tracking: Added FastAPI, SQLAlchemy (async), MLflow, Jinja2, pytest (all existing — no new deps)
