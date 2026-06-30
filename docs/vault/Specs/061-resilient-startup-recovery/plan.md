# Implementation Plan: 061 Resilient Startup & Data-Safe Database Recovery

**Branch**: `061-resilient-startup-recovery` | **Date**: 2026-06-30 | **Spec**: `docs/vault/Specs/061-resilient-startup-recovery/spec.md`
**Input**: Feature specification from `docs/vault/Specs/061-resilient-startup-recovery/spec.md`

## Summary

Replace the current hard-fail `sys.exit(1)` on DB schema mismatch with a pit-of-success recovery model: detect, classify, preserve, and surface a reachable maintenance-mode recovery surface. On a bad/desynced DB, the server binds the port and serves a recovery UI instead of crashing. Composes with the existing 027 backup/restore engine and Alembic auto-migration infrastructure.

**Technical approach**: Introduce a `StartupClassifier` that runs read-only checks before any migration or startup step, producing one of five `DbState` values. On `fresh`/`healthy`, proceed normally. On `desynced`/`corrupt`, snapshot the suspect DB to `data/backups/quarantine/<timestamp>/`, enter maintenance mode (skip normal routes, serve recovery surface), and gate destructive recovery actions behind an `ANVIL_RECOVERY_KEY` bearer token. Split `GET /v1/health` (liveness, stays 200 in maintenance) from `GET /v1/ready` (readiness, 503 until writable).

## Technical Context

**Language/Version**: Python 3.11+ (PEP 604, `StrEnum`, `from __future__ import annotations`)
**Primary Dependencies**: FastAPI, async SQLAlchemy + aiosqlite, Alembic, Jinja2, stdlib (`sqlite3`, `hashlib`, `shutil`, `tarfile`, `pathlib`). **No new runtime dependencies** — per spec constraints and Constitution Article I/XI.
**Storage**: SQLite (WAL mode) via async SQLAlchemy; filesystem for backup/quarantine artifacts at `data/backups/`; `LocalFileStore` for blobs
**Testing**: pytest, pytest-asyncio, httpx `AsyncClient` (existing), `sqlite3` stdlib for fixture setup
**Target Platform**: macOS + Linux (server, Docker)
**Project Type**: web-service (Python package, FastAPI)
**Performance Goals**: Maintenance-mode recovery surface responds within 2s (no spec'd startup-time target)
**Constraints**:
- No new runtime dependencies (stdlib only additions)
- Must compose with existing 027 backup/restore (`BackupService`, `RestoreJournal`, `SnapshotPlanner`)
- Must compose with existing `MigrationService` (`verify_table_integrity`, `get_schema_version`, `ensure_migrated`)
- Must follow Constitution Article XI (Simplicity First / Boring Technology)
- Must follow existing layered architecture: Repository → Service → God Class → Routes
- All new code MUST use enums over magic strings (Principle 11)
- No type-error suppression; `mypy --strict` enforced
**Scale/Scope**: Single-tenant local deployment; multi-workspace with per-workspace DB isolation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable (§11.1)** — The chosen approach (classify → snapshot → maintenance mode) is the simplest that satisfies the data-safety invariant. The spec explicitly rejected destructive auto-fix and auto-restore as complex/dangerous defaults.
- [x] **Boring over novel (§11.2)** — All technology choices are existing: SQLite `PRAGMA quick_check`, stdlib `sqlite3`, existing `BackupService` for archives, existing `SnapshotPlanner` for space checks, existing `MigrationService` for table integrity. No novel dependencies or patterns introduced.
- [x] **YAGNI (§11.3)** — Only building what the five-state classifier needs. No speculative "future recovery strategy" abstractions. The maintenance-mode route isolation is a simple middleware flag, not a plugin system.
- [x] **Reuse first (§11.4)** — Reuses existing `MigrationService.verify_table_integrity()`, `BackupService.recover_interrupted_restore()`, `SnapshotPlanner.plan()`, `RestoreJournal`, Alembic auto-migration, existing health endpoint infrastructure.
- [x] **Testable (§11.6)** — Every acceptance scenario is independently testable via fixtures (corrupt DB, desynced DB, zero-byte DB, fresh DB) and HTTP client assertions against health/ready endpoints and recovery surface.

> Any deviation from the simplest viable solution MUST be recorded in the Complexity Tracking table below (§11.5), or this gate fails.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/061-resilient-startup-recovery/
├── plan.md              # This file
├── research.md          # Phase 0 output — resolved unknowns
├── data-model.md        # Phase 1 output — entity definitions
├── quickstart.md        # Phase 1 output — operator guide
├── contracts/           # Phase 1 output — recovery API contracts
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
# Web application (DEFAULT) — anvil project structure

anvil/
├── db/                            # DB classifier additions
│   ├── db_state.py                #   DbState enum + StartupClassifier class (NEW)
│   └── migration.py               #   MV: verify_table_integrity promoted to startup gate
├── api/
│   ├── app.py                     #   Lifespan: reorder to classify before migrate; replace sys.exit with maintenance mode
│   ├── deps.py                    #   Add maintenance-mode route gating dependency
│   ├── v1/
│   │   ├── router.py              #   Add recovery_router + ready_router
│   │   ├── health_ops.py          #   Split health → liveness (existing) + readiness (new /v1/ready)
│   │   └── recovery.py            #   NEW: recovery surface API + maintenance mode routes
│   ├── static/                    #   Recovery page CSS (minor additions using existing tokens)
│   └── templates/
│       └── recovery.html          #   NEW: Jinja2 recovery page template
├── services/
│   ├── backup/                    #   Existing — composed with for snapshot/quarantine
│   └── recovery/                  #   NEW domain sub-package: RecoveryService
│       ├── __init__.py            #   Bare docstring
│       ├── recovery_service.py    #   RecoveryService: snapshot, quarantine, restore orchestrator
│       ├── snapshot.py            #   DbSnapshot: direct DB-trio snapshot (stdlib tarfile, no BackupService dependency)
│       └── quarantine.py          #   Quarantine: move suspect DB to data/backups/quarantine/

tests/
├── unit/
│   └── test_startup_classifier.py  #   Classifier unit tests (five states + zero-byte edge case)
├── e2e/
│   ├── test_recovery_endpoints.py  #   Health/ready split + recovery surface API tests
│   └── test_maintenance_mode.py    #   Maintenance mode: route isolation, snapshot, recovery actions
└── conftest.py                     #   Fixtures: corrupt_db, desynced_db, fresh_db, zero_byte_db
```

**Structure Decision**: Single-project anvil package with new `anvil/services/recovery/` domain sub-package and a new `anvil/db/db_state.py` module. The recovery HTML template goes in existing `anvil/api/templates/`. No new top-level directories. Follows existing domain-decomposition pattern (Article X).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. All approaches are the simplest viable solution.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

