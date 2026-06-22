---
title: 011 Auto DB Schema - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/011 Auto DB Schema/
related:
  - '[[011 Auto DB Schema]]'
created: ~
updated: ~
---
# Feature Specification: Auto Database Schema Management

**Feature Branch**: `011-auto-db-schema`  
**Created**: 2026-06-18  
**Status**: Draft  
**Input**: User description: "Make the app create its database schema on startup instead of requiring make setup first. Also provide CLI commands for manual database management (upgrade, downgrade, history, etc.). Cross-reference MLflow server's approach to Alembic and database management."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-Run: Schema Created Automatically (Priority: P1)

A developer clones the repo, installs dependencies, and runs `anvil` (the web server) without first running `make setup`. The database file doesn't exist yet. The app should detect this, create the database, and apply all pending Alembic migrations so the server starts successfully.

**Why this priority**: This is the primary motivation for the feature — eliminating the manual `make setup` step for developers who just want to run the app. It reduces friction from day one.

**Independent Test**: Can be fully tested by removing `data/anvil-state.db`, running `anvil`, and verifying all web UI routes load without database errors. Delivers a zero-friction first-run experience.

**Acceptance Scenarios**:

1. **Given** no database file exists at the configured `ANVIL_STATE_DB_PATH`, **When** the server starts, **Then** the database file is created, all Alembic migrations are applied, and the server starts successfully on the first attempt
2. **Given** a database file exists with all migrations already applied, **When** the server starts, **Then** no migration action is taken and the server starts immediately

---

### User Story 2 - Schema Upgrade on Version Update (Priority: P1)

A developer upgrades the `anvil` package to a newer version that includes a new Alembic migration (e.g., adding a column to the experiments table). When they restart the server, the migration should be applied automatically so the app continues to function without manual intervention.

**Why this priority**: This makes the upgrade path seamless — users don't need to remember to run migration commands after every update. It's critical for the pip-installable UX.

**Independent Test**: Can be tested by starting the server against a database at an older migration revision, then restarting with a new migration version in the migrations directory. The database should be upgraded automatically.

**Acceptance Scenarios**:

1. **Given** a database at revision `abc123` (one revision behind `HEAD`), **When** the server starts, **Then** the pending migration is applied and the database reaches revision `HEAD`
2. **Given** a database that is ahead of the current code's migrations (e.g., downgraded code), **When** the server starts, **Then** a clear warning is logged and the server refuses to start with an informative error message

---

### User Story 3 - Manual CLI Migration Management (Priority: P2)

A power user or operator needs to manage the database schema explicitly — checking the current migration revision, viewing migration history, creating a new migration, or rolling back a problematic migration. They run `anvil db status` to see the current state, and `anvil db upgrade` to apply pending migrations manually.

**Why this priority**: CLI commands are essential for operations, debugging, and development workflows. They provide an escape hatch when auto-migration is undesirable (e.g., staging/production deployments where manual verification is required before upgrading).

**Independent Test**: Can be tested by running each CLI command against a test database and verifying the output matches Alembic's behavior for the equivalent command.

**Acceptance Scenarios**:

1. **Given** a database with pending migrations, **When** the user runs `anvil db upgrade`, **Then** all pending migrations are applied and the database revision matches `HEAD`
2. **Given** a database at the latest migration, **When** the user runs `anvil db current`, **Then** the current revision hash is displayed
3. **Given** multiple migration revisions in history, **When** the user runs `anvil db history`, **Then** the full migration chain is displayed

---

### User Story 4 - New Migration Generation for Developers (Priority: P3)

A developer has modified an ORM model (added a field, changed a relationship) and needs to generate a new Alembic migration. They run `anvil db revision "add user preferences table"` and an auto-generated migration file is created in the migrations directory.

**Why this priority**: This is a developer workflow that accelerates iteration but is not needed by regular users. The existing `make db-revision` already covers this, so it's lower priority.

**Independent Test**: Can be tested by modifying an ORM model, running the migration generation command, and verifying the generated file contains the expected operations.

**Acceptance Scenarios**:

1. **Given** the user has modified an ORM model, **When** they run `anvil db revision "description"`, **Then** a new auto-generated migration file is created in the `migrations/versions/` directory

---

### Edge Cases

- What happens when the database file path's parent directory doesn't exist? The app should create it.
- What happens when a migration fails (e.g., constraint violation)? The error should be logged, the transaction rolled back, and the server should refuse to start with a clear message directing the user to run `anvil db upgrade` manually or consult logs.
- What happens when two server instances race to migrate the same database? SQLite WAL mode handles concurrent access gracefully — one migration succeeds, the other encounters `database is locked` and fails with a clear error. Single-process server model means this is a theoretical edge case; no dedicated concurrency test is required.
- What happens when the database schema is newer than the application code? Log a warning and fail to start, preventing data loss from a downgrade.
- What happens during the first-ever migration on an empty database? The initial migration should create all tables from `Base.metadata` without errors.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST apply all pending Alembic migrations to the application database during server startup, before the web server begins accepting requests.
- **FR-002**: If the database file does not exist at startup, the app MUST create the file, create the containing directory if necessary, then apply all migrations.
- **FR-003**: If an Alembic migration fails during auto-upgrade, the app MUST log the full error, roll back the failed transaction, and exit with a non-zero status code.
- **FR-004**: If the database schema revision is AHEAD of the application code's expected revision, the app MUST refuse to start, log a warning, and suggest the user downgrade or install a matching version. This behaves identically regardless of the `ANVIL_DB_AUTO_MIGRATE` setting.
- **FR-005**: When `ANVIL_DB_AUTO_MIGRATE=false` and the database schema is BEHIND the expected revision, the app MUST refuse to start, log the mismatch, and print the exact command to run (`anvil db upgrade`). This is strict verification mode — same as MLflow's tracking store.
- **FR-006**: The app MUST expose the following CLI commands under an `anvil db` subcommand group for manual database management:
  - `anvil db upgrade` — Apply all pending migrations
  - `anvil db downgrade [-1|revision]` — Roll back one or more migrations
  - `anvil db current` — Show current revision
  - `anvil db history` — Show migration history
  - `anvil db revision "message"` — Generate a new auto-generated migration
  - `anvil db stamp <revision>` — Stamp the database at a specific revision without running migrations
- **FR-007**: Each CLI command MUST delegate to the equivalent Alembic operation and preserve its exit codes and output formatting.
- **FR-008**: The startup behavior MUST be controlled by an `ANVIL_DB_AUTO_MIGRATE` environment variable (default: `true`):
  - When `true` (default): auto-migrate on startup — apply all pending migrations before the server starts
  - When `false`: strict verification mode — verify schema version matches, refuse to start if out of date, print `anvil db upgrade` command
- **FR-009**: The app MUST log the before-and-after revision hash when auto-migration runs, including a summary of which migrations were applied.
- **FR-010**: The `ANVIL_STATE_DB_PATH` environment variable MUST continue to control the database location, as it does today.

### Key Entities *(include if feature involves data)*

- **Alembic Migration**: A versioned, sequential database schema change. Each migration has a unique revision hash, a down-revision pointer to its parent, and upgrade/downgrade functions.
- **Alembic Version Table** (`alembic_version`): The internal SQLite table Alembic uses to track which revision the database is currently at. Not a business entity — purely internal infrastructure.
- **Application Database** (`anvil-state.db`): The SQLite file containing all application state (training configs, corpora, datasets, experiments, models). Managed by Alembic migrations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can go from `git clone` to a running server with database accessible in under 30 seconds, without running any manual database commands.
- **SC-002**: The server starts in under 1 second when no migrations are pending (cold start, all migrations already applied).
- **SC-003**: A server with a single pending migration starts in under 2 seconds (cold start, applies one migration).
- **SC-004**: An operator can disable auto-migration and manage the database entirely via CLI commands, with each CLI command completing in under 1 second.
- **SC-005**: All existing Alembic migrations (14 versions) apply correctly in sequence on a fresh database, producing a schema identical to running `make setup`.
- **SC-006**: Zero application code changes required beyond the database layer — all ORM models, services, and API routes remain unchanged.

## Assumptions

- The project will continue using SQLite via async SQLAlchemy as its primary database backend (no migration to PostgreSQL in scope).
- Existing `make`-based targets for database management (`db-upgrade`, `db-downgrade`, etc.) will remain as convenience wrappers around the new CLI commands.
- The existing Alembic configuration (`alembic.ini`, `migrations/env.py`) is correct and does not need restructuring — only the invocation mechanism changes.
- The existing `Base.metadata.create_all` call in the lifespan handler will be REPLACED by `alembic upgrade head`, removing the risky dual-path schema management.
- MLflow's own database (in `mlruns/mlflow.db`) is managed independently by the MLflow server subprocess and is out of scope.
- The feature targets both local development and Docker deployment scenarios equally.

## Design Decision: Auto-Migrate vs. Strict Verification

**Decision**: Option C — Hybrid approach.
`ANVIL_DB_AUTO_MIGRATE=true` (default) auto-migrates on startup. `ANVIL_DB_AUTO_MIGRATE=false` switches to strict verification mode (MLflow tracking store model — refuse to start, print `anvil db upgrade` command).

This is reflected in FR-005 (strict verification mode) and FR-008 (`ANVIL_DB_AUTO_MIGRATE` behavior).

**Rationale**: Auto-migrate by default matches the user's goal of eliminating `make setup`. The env var escape hatch covers production/staging deployments where explicit migration control is required.