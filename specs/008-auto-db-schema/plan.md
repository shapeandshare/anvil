# Implementation Plan: Auto Database Schema Management

**Branch**: `008-auto-db-schema` | **Date**: 2026-06-18 | **Spec**: `specs/008-auto-db-schema/spec.md`
**Input**: Feature specification from specs/008-auto-db-schema/spec.md

## Summary

Replace the current `Base.metadata.create_all` approach in the FastAPI lifespan with a proper Alembic migration pipeline that runs on startup. Add a `anvil db` CLI subcommand group for manual migration management (upgrade, downgrade, current, history, revision, stamp). The startup behavior is controlled by `ANVIL_DB_AUTO_MIGRATE` (default: `true` = auto-migrate; `false` = strict verification). Cross-reference MLflow's approach: auto-migrate on startup (auth store model) with an explicit CLI escape hatch (tracking store model).

## Technical Context

**Language/Version**: Python 3.11+ (stdlib for migration service, async for web layer)
**Primary Dependencies**: Alembic >=1.13 (existing), SQLAlchemy[asyncio] >=2.0 (existing), aiosqlite >=0.20 (existing)
**Storage**: SQLite via async SQLAlchemy (`data/anvil-state.db`, configurable via `ANVIL_STATE_DB_PATH`)
**Testing**: pytest + pytest-asyncio (existing), test on in-memory SQLite or temp file
**Target Platform**: macOS (dev), Linux server (prod), Docker
**Project Type**: pip-installable Python package with web service (FastAPI) + CLI (argparse)
**Performance Goals**: 
- Cold start (no DB) with migrations: <2 seconds
- Cold start (all migrations applied): <1 second
- CLI commands: <1 second each
**Constraints**: 
- Must NOT modify existing Alembic config or migration files
- Must preserve backward compatibility with existing `make setup` flow
- Must pass `mypy --strict` on all new code
- Must maintain 100% test coverage
**Scale/Scope**: Single-file SQLite, local-first deployment model

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Assessment | Status |
|---------|-----------|--------|
| **I — Zero-Dependency Core** | Feature touches `anvil/db/` and `anvil/cli.py`, not `anvil/core/`. No impact on core engine. | ✅ PASS |
| **II — Educational Clarity** | Infrastructure feature (DB migrations). No training code or progressive walkthroughs affected. | ✅ PASS |
| **III — Seeded Reproducibility** | No impact on training determinism. | ✅ PASS |
| **IV — TDD Mandatory** | New migration service and CLI commands require tests before implementation. Must cover auto-migrate, strict-verify, error paths, and each CLI subcommand. | ✅ PASS (pending test implementation) |
| **V — Async-First** | Existing DB layer is async. New migration service can use `asyncio.run()` for Alembic (which is sync), consistent with existing patterns. The `migrations/env.py` already handles async engine setup. | ✅ PASS |
| **VI — Implicit Namespace** | Only modifying existing modules (`cli.py`, `session.py`, `app.py`), plus one new module (`migration.py`). No new packages. | ✅ PASS |
| **VII — Layered Architecture** | New functionality: `MigrationService` in `anvil/db/migration.py` (service layer). Called from lifespan handler (`app.py`) and CLI commands (`cli.py`). Consistent with layered architecture. | ✅ PASS |
| **VIII — iOS-Grade Polish** | Not a UI feature. | ✅ SKIP (N/A) |
| **IX — Pit of Success** | Auto-migrate on startup by default (`ANVIL_DB_AUTO_MIGRATE=true`). Just works. Strict verification mode available via env var for production operators. | ✅ PASS |
| **Schema via Alembic** | Feature IS about managing schema via Alembic migrations. All new migrations must be reversible. | ✅ PASS |
| **No type-error suppression** | `mypy --strict` must pass on all new code. | ✅ GATE (must enforce during implementation) |
| **Lean dependencies** | No new dependencies. Alembic, SQLAlchemy, aiosqlite all already declared. | ✅ PASS |

**Verdict**: All gates clear. Proceed to Phase 0.

**Post-Design Re-evaluation**: All gates still clear after Phase 0 (research) and Phase 1 (design). No new constitution violations introduced. The auto-migrate-on-startup pattern (Option C) aligns with Article IX (Pit of Success). The `MigrationService` wrapper follows the async-wrapping-sync pattern already established in the codebase. No new dependencies required — Alembic, SQLAlchemy, and aiosqlite are already declared in pyproject.toml.

## Project Structure

### Documentation (this feature)

```text
specs/008-auto-db-schema/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── cli-contract.md
│   └── startup-contract.md
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
# Project structure (anvil package - implicit namespace)
anvil/
├── db/
│   ├── __init__.py        # Public API exports (no change)
│   ├── base.py            # Declarative Base, TimestampMixin (no change)
│   ├── session.py         # async_engine, init_engine(), get_db() [MODIFY: replace create_all with upgrade]
│   ├── models/            # ORM models (no change)
│   ├── repositories/      # Repository layer (no change)
│   └── migration.py       # NEW: MigrationService wrapping Alembic programmatic API
├── api/
│   └── app.py             # FastAPI app + lifespan [MODIFY: call upgrade instead of create_all]
├── cli.py                 # CLI entry points [MODIFY: add db_main() with subcommands]
├── config.py              # Config [MODIFY: add ANVIL_DB_AUTO_MIGRATE]

migrations/
├── env.py                 # Alembic env (no change needed)
├── script.py.mako         # Migration template (no change)
├── versions/              # Existing migration chain (no change)

shared/
└── database.mk            # Makefile targets [MODIFY: wrap new CLI commands]

tests/
├── unit/db/
│   └── test_migration.py  # NEW: unit tests for MigrationService
├── unit/
│   └── test_cli.py        # MODIFY: add tests for db subcommands
└── e2e/
    └── test_db_migration.py # NEW: end-to-end auto-migration test
```

**Structure Decision**: Single project (Python package `anvil`). New module `anvil/db/migration.py` for the MigrationService. CLI commands added to existing `anvil/cli.py` with a `db_main()` function. Tests follow existing structure under `tests/unit/db/` and `tests/e2e/`.

## Complexity Tracking

No constitution violations to justify. Feature is additive and follows existing patterns.