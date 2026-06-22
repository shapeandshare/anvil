# Tasks: Auto Database Schema Management

**Input**: Design documents from `specs/011-auto-db-schema/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test tasks ARE included per constitutional requirement (Article IV — TDD Mandatory).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project at repository root. Source in `anvil/`, tests in `tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new config key for ANVIL_DB_AUTO_MIGRATE and ensure migration directory is accessible

- [X] T001 Add `db_auto_migrate` config key to `anvil/config.py` in `get_config()` — parse `ANVIL_DB_AUTO_MIGRATE` env var (default `true`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core MigrationService that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational

- [X] T002 [P] Write unit tests for `MigrationService.__init__()` — test default DB URL resolution, explicit URL override, and config loading from `alembic.ini` in `tests/unit/db/test_migration.py`
- [X] T003 [P] Write unit tests for `MigrationService.upgrade()` — test running upgrade on fresh DB, running upgrade on up-to-date DB (no-op), and upgrade failure handling in `tests/unit/db/test_migration.py`
- [X] T004 [P] Write unit tests for `MigrationService.verify_schema()` — test passes when schema matches HEAD, raises when schema is behind, raises when schema is ahead in `tests/unit/db/test_migration.py`
- [X] T005 [P] Write unit tests for `MigrationService.current()`, `.history()`, `.downgrade()`, `.stamp()` — test each delegates to correct `alembic.command.*` function in `tests/unit/db/test_migration.py`
- [X] T006 [P] Write unit tests for `MigrationService.create_revision()` — test autogenerate creates migration file with correct message in `tests/unit/db/test_migration.py`

### Implementation for Foundational

- [X] T007 Create `anvil/db/migration.py` with `MigrationService` class:
  - Constructor accepts optional `db_url` and `alembic_ini_path`, defaults to env config
  - `_get_alembic_config()` — loads Alembic config, overrides `sqlalchemy.url` at runtime
  - `upgrade()` — calls `alembic.command.upgrade(config, "heads")` wrapped in `run_in_executor`, returns `(before, after)` revision tuple
  - `verify_schema()` — compares current vs HEAD revision, raises `MigrationError` on mismatch
  - `current()` — calls `alembic.command.current(config)`
  - `history()` — calls `alembic.command.history(config)`, returns structured list
  - `downgrade(revision)` — calls `alembic.command.downgrade(config, revision)`
  - `stamp(revision)` — calls `alembic.command.stamp(config, revision)`
  - `create_revision(message)` — calls `alembic.command.revision(config, autogenerate=True, message=message)`
  - `ensure_migrated()` — reads `ANVIL_DB_AUTO_MIGRATE`, calls `upgrade()` or `verify_schema()`
  - Ensure DB file + parent dirs are created if they don't exist (using `pathlib.Path.mkdir(parents=True, exist_ok=True)`)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - First-Run Auto-Schema-Creation (Priority: P1) 🎯 MVP

**Goal**: A developer can run `anvil` (web server) without `make setup` and the app creates the DB + applies all migrations automatically.

**Independent Test**: Remove `data/anvil-state.db`, start the server, verify all web UI routes load without database errors.

### Implementation for User Story 1

- [X] T008 [P] [US1] Replace `Base.metadata.create_all` call in FastAPI lifespan handler in `anvil/api/app.py` with `MigrationService.ensure_migrated()` — imports and delegates to the new service, removes the direct `conn.run_sync(Base.metadata.create_all)` call
- [X] T009 [P] [US1] Add INFO-level logging to the lifespan handler in `anvil/api/app.py` — log before/after revision hash when auto-migration runs, log "Database already at HEAD — no action needed" when no-op
- [X] T010 [US1] Write end-to-end test for first-run auto-create in `tests/e2e/test_db_migration.py` — removes any existing DB, patches `ANVIL_STATE_DB_PATH` to temp path, starts app lifespan, verifies all tables exist and revision matches HEAD

**Checkpoint**: At this point, User Story 1 should be fully functional — running the server automatically creates and migrates the database

---

## Phase 4: User Story 2 - Schema Upgrade on Version Update (Priority: P1)

**Goal**: When anvil is upgraded and a new Alembic migration exists, restarting the server applies the pending migration automatically.

**Independent Test**: Start server against a DB at an older revision, verify the pending migration is applied on restart.

### Implementation for User Story 2

- [X] T011 [P] [US2] Implement `ANVIL_DB_AUTO_MIGRATE=false` strict verification path in `anvil/db/migration.py` — `verify_schema()` method that:
  - Gets current DB revision via `alembic.command.current()`
  - Gets HEAD revision via Alembic script directory
  - If DB ahead → raise `MigrationError("Schema ahead of code")`
  - If DB behind → raise `MigrationError("Schema behind — run 'anvil db upgrade'")`
  - If match → return silently (success)
- [X] T012 [P] [US2] Add migration failure handling to `anvil/db/migration.py` — wrap `alembic.command.upgrade()` in try/except, log full traceback, raise `MigrationError` with user-friendly message directing operator to run `anvil db upgrade` manually
- [X] T013 [US2] Write end-to-end test for auto-upgrade on version update in `tests/e2e/test_db_migration.py` — creates DB at older revision, runs `ensure_migrated()`, verifies it upgraded to HEAD. Also tests strict mode: sets `ANVIL_DB_AUTO_MIGRATE=false`, verifies `verify_schema()` raises when DB is behind

**Checkpoint**: Auto-migration works for both first-run and upgrade scenarios. Strict verification mode prevents startup when operator has disabled auto-migrate but DB is out of date.

---

## Phase 5: User Story 3 - Manual CLI Migration Management (Priority: P2)

**Goal**: Power users can manage the database schema explicitly via `anvil db` subcommands (upgrade, downgrade, current, history, revision, stamp).

**Independent Test**: Run each CLI command against a test database and verify output matches expected Alembic behavior.

### Implementation for User Story 3

- [X] T014 [P] [US3] Add `db_main()` function to `anvil/cli.py` with argparse subparsers for all 6 CLI commands (upgrade, downgrade, current, history, revision, stamp) — matches existing `corpus_main()` pattern
- [X] T015 [P] [US3] Wire each CLI subcommand to its `MigrationService` method in `anvil/cli.py` — `upgrade` → `svc.upgrade()`, `downgrade` → `svc.downgrade()`, `current` → `svc.current()`, `history` → `svc.history()`, `revision` → `svc.create_revision()`, `stamp` → `svc.stamp()`
- [X] T016 [P] [US3] Add `anvil-db` entry point to `pyproject.toml` `[project.scripts]` — `anvil-db = "anvil.cli:db_main"`
- [X] T017 [US3] Update `shared/database.mk` Make targets to delegate to `anvil.cli:db_main` — all 6 existing targets (`db-upgrade`, `db-downgrade`, `db-current`, `db-history`, `db-revision`, `db-stamp`) call the new CLI instead of raw `alembic` commands
- [X] T018 [US3] Write unit tests for each CLI subcommand in `tests/unit/test_cli.py` — patch `MigrationService` methods and verify argparse correctly dispatches each subcommand and passes expected arguments

**Checkpoint**: All CLI commands work. Makefile targets still function. Users can manage DB explicitly without auto-migration.

---

## Phase 6: User Story 4 - New Migration Generation (Priority: P3)

**Goal**: Developers can generate new Alembic migrations from ORM model changes via `anvil db revision -m "message"`.

**Independent Test**: Modify an ORM model field, run the generation command, verify the generated migration file contains the expected schema change.

### Implementation for User Story 4

- [X] T019 [P] [US4] Add `ANVIL_DB_AUTO_MIGRATE` to `.env.example` documentation in project root — document the default (`true` / auto-migrate) and how to disable for production
- [X] T020 [US4] Update `README.md` — document the new auto-migration startup behavior in the Quick Start section (remove the "init DB" step as it's now automatic), add a "Database Management" section documenting the CLI commands

**Checkpoint**: Developer workflow for generating new migrations is unified under `anvil db revision`. Documentation reflects new behavior.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T021 [P] Add `MigrationError` custom exception class in `anvil/db/migration.py` — base class for migration failures, includes both user-facing message and revision details
- [X] T022 [P] Verify `mypy --strict` passes on all new and modified files — `anvil/db/migration.py`, `anvil/cli.py`, `anvil/config.py`, `anvil/api/app.py`
- [X] T023 [P] Verify `make lint` passes with no new issues
- [X] T024 [P] Verify `make test` passes with 100% coverage threshold
- [X] T025 Update `CONSTITUTION.md` / `.specify/memory/constitution.md` if needed — no changes expected, this feature aligns with all articles

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — no dependencies on other stories
- **US2 (Phase 4)**: Depends on Foundational — can proceed in parallel with US1
- **US3 (Phase 5)**: Depends on Foundational — can proceed in parallel with US1/US2
- **US4 (Phase 6)**: Depends on Foundational + US3 (generation uses CLI from US3)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1) + User Story 2 (P1)**: Both start after Foundational. US1 and US2 share the same `MigrationService` — US2 adds the strict-verify path and error handling. Can be implemented in parallel.
- **User Story 3 (P2)**: Pure CLI layer on top of services. Fully testable with mocks.
- **User Story 4 (P3)**: Depends on US3 (CLI entry point for revision command). Documentation only.

### Within Each User Story

- Tests MUST be written and FAIL before implementation (per Constitution Article IV)
- Services before endpoints
- Core implementation before integration

### Parallel Opportunities

- T002-T006 (Foundational tests): Can all run in parallel (different test functions, same file)
- T008-T009 (US1): Can run in parallel (app.py edit + logging)
- T011-T012 (US2): Can run in parallel (verify_schema + error handling)
- T014-T016 (US3): Can run in parallel (CLI function, wiring, pyproject.toml)
- T019-T020 (US4): Can run in parallel (documentation)

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch all unit tests in parallel:
Task: "Write unit tests for MigrationService.__init__ in tests/unit/db/test_migration.py"
Task: "Write unit tests for MigrationService.upgrade in tests/unit/db/test_migration.py"
Task: "Write unit tests for MigrationService.verify_schema in tests/unit/db/test_migration.py"
Task: "Write unit tests for MigrationService.current/downgrade/stamp in tests/unit/db/test_migration.py"
Task: "Write unit tests for MigrationService.create_revision in tests/unit/db/test_migration.py"
```

## Parallel Example: Phase 3/4/5 (US1 + US2 + US3)

```bash
# Once Foundational is complete, all P1/P2 stories can proceed in parallel:

# US1: Lifespan auto-migration
Task: "Replace create_all with ensure_migrated in anvil/api/app.py"
Task: "Add auto-migration logging to anvil/api/app.py"
Task: "Write e2e test for first-run auto-create in tests/e2e/test_db_migration.py"

# US2: Strict verification + error handling  
Task: "Implement verify_schema strict mode in anvil/db/migration.py"
Task: "Add migration failure handling in anvil/db/migration.py"
Task: "Write e2e test for auto-upgrade in tests/e2e/test_db_migration.py"

# US3: CLI subcommands
Task: "Add db_main function in anvil/cli.py"
Task: "Wire CLI subcommands to MigrationService in anvil/cli.py"
Task: "Add anvil-db entry point in pyproject.toml"
Task: "Update shared/database.mk targets"
Task: "Write CLI unit tests in tests/unit/test_cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (ANVIL_DB_AUTO_MIGRATE config)
2. Complete Phase 2: Foundational (MigrationService + tests) — CRITICAL
3. Complete Phase 3: User Story 1 (first-run auto-create)
4. **STOP and VALIDATE**: Test User Story 1 independently — remove DB, start server, verify it works
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (migration service exists but not wired yet)
2. Add User Story 1 (P1) → Auto-schema creation on first run → Deploy/Demo (MVP!)
3. Add User Story 2 (P1) → Auto-upgrade on version update + strict verify → Deploy/Demo
4. Add User Story 3 (P2) → CLI commands for manual management → Deploy/Demo
5. Add User Story 4 (P3) → Migration generation + docs → Deploy/Demo
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Developer A: Foundational (Phase 2) — the critical path
2. Once Foundational is done:
   - Developer A: User Story 1 + User Story 2 (P1 — core startup behavior)
   - Developer B: User Story 3 (P2 — CLI commands)
3. Developer A + B together: User Story 4 (P3 — documentation)
4. Developer A or B: Polish phase

---

## Summary

| Metric | Value |
|--------|-------|
| **Total tasks** | 25 |
| **Phase 1 (Setup)** | 1 task |
| **Phase 2 (Foundational)** | 6 tasks (5 tests, 1 implementation) |
| **Phase 3 (US1 — P1)** | 3 tasks |
| **Phase 4 (US2 — P1)** | 3 tasks |
| **Phase 5 (US3 — P2)** | 5 tasks |
| **Phase 6 (US4 — P3)** | 2 tasks |
| **Phase 7 (Polish)** | 5 tasks |
| **Parallelizable tasks** | 13 (marked [P]) |
| **MVP scope** | Phases 1-3 (9 tasks) — auto-create on first run |
| **Files modified** | `config.py`, `app.py`, `cli.py`, `pyproject.toml`, `database.mk`, `.env.example`, `README.md` |
| **Files created** | `anvil/db/migration.py`, `tests/unit/db/test_migration.py`, `tests/e2e/test_db_migration.py` |

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD per Constitution Article IV)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently