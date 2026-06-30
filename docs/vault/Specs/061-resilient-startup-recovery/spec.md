# Feature Specification: Resilient Startup & Data-Safe Database Recovery

**Feature Directory**: `docs/vault/Specs/061-resilient-startup-recovery`
**Created**: 2026-06-29
**Status**: Draft
**Input**: User description: "I want pit-of-success recovery here — we need to be recoverable without losing data. What are the options, pros/cons?" (following a `make run` failure where the app DB was schema-desynced — `alembic_version` stamped at head but all application tables missing — and the server crashed at startup with exit code 3 and no UI feedback; the only documented fix was `rm data/anvil-state.db`, which destroys user data.)

## Context & Motivation

On `make run` the FastAPI lifespan startup aborted with exit code 3 and bound no port, so the web UI, the operations dashboard, and every health endpoint were unreachable. Root cause: the SQLite app DB (`data/anvil-state.db`) was in a **schema/migration desync** — the `alembic_version` table reported revision `007` (fully migrated) while every application table (`license_catalog`, `datasets`, `corpora`, …) was missing; only `alembic_version` and `run_id_seq` existed. Alembic therefore applied no migrations (it believed it was at head), and a later best-effort startup step (`_seed_license_catalog()`) issued `SELECT … FROM license_catalog`, raising `sqlite3.OperationalError`. That exception was not caught by the step's `except (ValueError, RuntimeError)` clause (SQLAlchemy errors derive from `Exception`, not `RuntimeError`), so it propagated and uvicorn exited.

The remediation given at the time — `rm data/anvil-state.db && make run` — **destroys data**. This spec defines a *pit-of-success* recovery model where the **default, easy path is also the data-safe path**: the system detects a bad DB, preserves it, and surfaces a reachable recovery surface instead of crashing.

This spec is **distinct from** [[Specs/057-degraded-mode-recovery/spec|057 Degraded Mode Recovery]] (which covers the *MLflow tracking sidecar* degraded mode) and **composes with** [[Specs/027 Deployment Backup Restore/spec|027 Deployment Backup Restore]] (the existing stdlib backup/restore engine + `RestoreJournal`) and [[Specs/011 Auto DB Schema/011 Auto DB Schema|011 Auto DB Schema]] (the Alembic auto-migration infrastructure).

## Data-Safety Invariant *(governing principle)*

> **The system never intentionally deletes or overwrites the only known copy of user state. Worst case, it quarantines the suspect database and requires operator-directed recovery from preserved artifacts or backups.**

Every requirement below is subordinate to this invariant. Any behavior that could violate it (auto-restore, reset, in-place repair) MUST be operator-gated and MUST be preceded by a preserving snapshot.

## Clarifications

### Session 2026-06-30

- Q: How does the recovery surface handle auth when the app DB (which backs auth) is itself broken? → A: **Auth-exempt read-only surface + recovery token for actions.** The recovery page and read-only endpoints (backup listing, DB state display) are auth-exempt. All state-altering recovery actions (restore, quarantine+reset, retry-migrations) require a pre-configured bearer token from `ANVIL_RECOVERY_KEY` env var. This prevents the DB-deadlock while gating destructive operations.
- Q: Where should snapshot/quarantine artifacts be stored on the filesystem? → A: **`data/backups/quarantine/`** — alongside the existing 027 backup directory tree, keeping all recovery artifacts in one discoverable location and simplifying space accounting.

### Session 2026-06-29

- Q: How should "fresh DB" be distinguished from "existing but broken DB" so we never reinitialize real data? → A: **Provenance, not contents.** A state is `fresh` ONLY if the DB file did not exist before this startup AND no `-wal`/`-shm` sidecars exist. Any pre-existing DB artifact — even a zero-byte file — is treated as existing user state and is never auto-reinitialized.
- Q: What is the default behavior when the DB is desynced or corrupt? → A: **Snapshot, then boot into a read-only maintenance/recovery mode** that binds the port and serves a recovery surface. Do NOT `sys.exit`.
- Q: Which actions are automatic vs. require explicit operator confirmation? → A: Automatic only for non-destructive/clearly-reversible actions (restore-journal rollback, fresh-DB init, normal migration on a healthy DB, taking a safety snapshot). Everything that rolls back, replaces, or reinterprets user state (restore-from-backup, quarantine+reset, retry-migration/stamp, salvage) requires explicit confirmation.
- Q: Should auto-restore from the latest backup be the default? → A: **No.** Auto-restore is a rollback to backup time and can silently mask a recurring defect. It is an opt-in policy (`ANVIL_AUTO_RESTORE_ON_CORRUPTION`, default off), not the universal default.
- Q: Should the bare `GET /v1/health` start probing the DB? → A: Split liveness from readiness. `GET /v1/health` (liveness) stays 200 even in maintenance mode so the recovery UI stays reachable in Docker; add `GET /v1/ready` (readiness) that returns 503 when the DB is not writable / startup did not fully complete.
- Q: SQLite-level salvage (`.recover`, WAL surgery)? → A: Out of automatic scope. Provided only as an operator-invoked CLI tool that operates on a **copy**, never the live artifacts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Server Never Dies Silently on a Bad Database (Priority: P1)

An operator runs `make run` (or starts the container) with a database that is corrupt or schema-desynced. Instead of the process exiting with no feedback, the server boots into a **maintenance/recovery mode**: it binds the port, the bare health/liveness check passes, and navigating to the app shows a recovery page explaining what is wrong and what actions are available.

**Why this priority**: This is the core pit-of-success requirement. A silent `sys.exit(3)` strands the operator with no reachable surface and an instinct to `rm` the DB. A reachable recovery UI converts a data-loss cliff into a guided, safe recovery.

**Independent Test**: Corrupt or desync a test DB (e.g. stamp `alembic_version` at head but drop all tables), start the app, and verify (a) the process stays alive, (b) `GET /v1/health` returns 200, (c) `GET /v1/ready` returns 503, and (d) the recovery page renders with the detected fault and available actions.

**Acceptance Scenarios**:

1. **Given** a schema-desynced DB (revision stamped but tables missing), **When** the app starts, **Then** it enters maintenance mode, binds the port, and does not exit.
2. **Given** a corrupt DB file (`PRAGMA integrity_check` fails), **When** the app starts, **Then** it enters maintenance mode and reports `corrupt` as the cause.
3. **Given** maintenance mode is active, **When** the operator opens the app in a browser, **Then** a recovery page describes the fault and lists operator-gated recovery actions.
4. **Given** maintenance mode is active, **When** normal application routes (e.g. datasets, training) are requested, **Then** they are unavailable/return a clear "recovery mode" response and never touch the suspect DB for writes.

---

### User Story 2 — The Suspect Database Is Always Preserved (Priority: P1)

When the system detects a bad DB or before performing any operator-approved repair, it **always** preserves the current on-disk state (the `.db`, `-wal`, and `-shm` trio) to a timestamped, clearly-labeled location. The system never issues a destructive `rm`/overwrite of the only copy.

**Why this priority**: This is the concrete enforcement of the data-safety invariant. Preserving bytes first means every later decision (restore, reset, salvage, forensics) remains possible.

**Independent Test**: Trigger detection on a populated-but-corrupt DB, then verify the original bytes exist intact at a quarantine/snapshot path with a recorded manifest (size, sha256, timestamp), and that the original path was copied (not moved-then-lost) before any further action.

**Acceptance Scenarios**:

1. **Given** a bad DB is detected, **When** the system prepares to remediate, **Then** the full DB trio is snapshotted to a timestamped artifact before any other action.
2. **Given** an operator confirms quarantine+reset, **When** the action runs, **Then** the suspect DB is moved to a timestamped quarantine path (never deleted) and a fresh DB is initialized.
3. **Given** the backup volume lacks space for a snapshot, **When** preservation is attempted, **Then** the system refuses the destructive action and reports the space shortfall rather than proceeding unsafely.
4. **Given** any preservation has occurred, **When** the operator inspects the recovery UI/logs, **Then** the exact preserved-artifact location is shown.

---

### User Story 3 — Startup Classifies the Database Before Touching It (Priority: P2)

Before running migrations or any DB-dependent startup step, the app classifies the DB into one of five explicit states — `fresh`, `healthy`, `desynced`, `corrupt`, `restore_in_progress` — using read-only checks and filesystem provenance. The classification drives all subsequent startup behavior.

**Why this priority**: Correct, conservative detection is the precondition for every safe action. The dangerous failure to avoid is treating broken existing state as "empty / safe to reset."

**Independent Test**: Construct fixtures for each of the five states and assert the classifier returns the correct state and that `fresh` is decided by provenance (file/sidecar absence), never by table emptiness.

**Acceptance Scenarios**:

1. **Given** no DB file and no `-wal`/`-shm` existed before startup, **When** the classifier runs, **Then** it returns `fresh` and the app initializes + migrates automatically.
2. **Given** a readable DB whose integrity check passes, expected tables are all present, and the Alembic revision is known, **When** the classifier runs, **Then** it returns `healthy` and normal migration proceeds.
3. **Given** a readable DB where `verify_table_integrity()` reports missing expected tables, **When** the classifier runs, **Then** it returns `desynced`.
4. **Given** a DB whose `PRAGMA integrity_check`/`quick_check` fails or that cannot be opened, **When** the classifier runs, **Then** it returns `corrupt`.
5. **Given** a `RestoreJournal` marker exists, **When** the classifier runs, **Then** it returns `restore_in_progress` and journal recovery runs first.
6. **Given** a pre-existing but zero-byte DB file, **When** the classifier runs, **Then** it is NOT classified `fresh` (provenance rule) and is treated as existing state requiring operator decision.

---

### User Story 4 — Best-Effort Startup Steps Can Never Crash the Boot (Priority: P2)

The optional, "best-effort" startup steps (license-catalog seeding, demo-data bootstrap, demo-model warmup, tracking reconcile) run only after the DB is declared writable, and a failure in any of them degrades that feature without aborting process startup.

**Why this priority**: This is the direct fix for the incident. A missing table during seeding must never take down the whole server. It also corrects the lifespan ordering so recovery runs before any DB-dependent optional step.

**Independent Test**: Inject a failure into each best-effort step (raise a `SQLAlchemyError`, `OSError`, and a generic `Exception`) and verify the server still completes startup, becomes ready, and logs the degraded step.

**Acceptance Scenarios**:

1. **Given** the license-catalog seeding step raises any exception, **When** startup runs on an otherwise-healthy DB, **Then** the server still starts, becomes ready, and logs the failure at WARN.
2. **Given** the DB is classified `desynced`/`corrupt`, **When** startup runs, **Then** best-effort steps are skipped entirely (not attempted against a suspect DB).
3. **Given** the lifespan sequence, **When** it executes, **Then** restore-journal recovery and DB classification occur before MLflow start, seeding, bootstrap, and warmup.

---

### User Story 5 — Operator-Gated Recovery Actions From the Recovery Surface (Priority: P3)

From the maintenance-mode recovery surface (UI + API), the operator can choose an explicit recovery action — restore from a verified backup, quarantine+reset to a fresh DB, or retry migrations — each requiring explicit confirmation and each preceded by a preserving snapshot. After a successful action the app transitions to normal mode (or instructs a restart).

**Why this priority**: Completes the loop: detection + preservation give safety; gated actions give the operator a guided way back to a working system without shell access or destructive commands.

**Independent Test**: From maintenance mode, exercise each action against fixtures and verify confirmation is required, a snapshot precedes the action, and the resulting state is correct (restored data / fresh DB / re-migrated schema).

**Acceptance Scenarios**:

1. **Given** maintenance mode and ≥1 verified backup, **When** the operator confirms "restore from backup", **Then** a safety snapshot is taken, the backup is restored via the existing restore engine (journal-protected), and the app returns to a usable state.
2. **Given** maintenance mode, **When** the operator confirms "quarantine + reset", **Then** the suspect DB is quarantined and a fresh migrated DB is created.
3. **Given** a `desynced` DB, **When** the operator confirms "retry migrations", **Then** a snapshot is taken first and migrations are re-attempted; if it still fails, the app remains in maintenance mode with the new error surfaced.
4. **Given** any recovery action, **When** it is requested without the explicit confirmation token, **Then** it is rejected.

---

### User Story 6 — Honest Health Signal (Liveness vs Readiness) (Priority: P3)

Orchestrators and operators can distinguish "the process is alive" from "the app is fully usable." Liveness stays green in maintenance mode (so the recovery UI is reachable); readiness is red until the DB is writable and startup completed.

**Why this priority**: Today the bare `/v1/health` returns `{"status":"healthy"}` unconditionally, so Docker/orchestrators get false positives even when the DB is unreachable. Splitting the signals makes health honest without killing the recovery surface.

**Independent Test**: In maintenance mode, assert `GET /v1/health` → 200 and `GET /v1/ready` → 503 with a body describing the detected fault; in normal mode assert both are 200.

**Acceptance Scenarios**:

1. **Given** maintenance mode, **When** `GET /v1/health` is called, **Then** it returns 200 (process is alive).
2. **Given** maintenance mode, **When** `GET /v1/ready` is called, **Then** it returns 503 with the DB state and detected cause.
3. **Given** normal mode with a writable DB, **When** either endpoint is called, **Then** it returns 200.
4. **Given** the deployment uses a container healthcheck, **When** maintenance mode is active, **Then** the healthcheck (pointed at liveness) keeps the container alive so the operator can recover via the UI.

---

### Edge Cases

- **Fresh vs broken ambiguity**: A pre-existing zero-byte DB or a DB with only `alembic_version` present is NOT fresh (provenance rule) and must require an operator decision rather than silent reinit.
- **WAL/SHM mismatch**: A `.db` present with an orphaned/incompatible `-wal` or `-shm` is treated as suspect; the trio is snapshotted together before any checkpoint or repair.
- **`get_schema_version()` masking**: The existing helper returns `0` on *any* read error, conflating "fresh" with "corrupt". The classifier MUST distinguish `unknown/error` from `fresh` and never decide `fresh` from a read error.
- **Backup is itself incompatible**: When the only available backup's `schema_revision`/`deployment_version` is incompatible with the running code, restore preview must warn and the action must require explicit override.
- **Multi-instance / workspace mode**: Classification and quarantine are per-workspace; one bad workspace DB must not trigger destructive handling of other instances' DBs.
- **Snapshot fails for lack of space**: Any destructive remediation is refused if the preserving snapshot cannot be written.
- **Crash mid-restore**: Handled by the existing `RestoreJournal` rollback, which now runs first in the lifespan.
- **Recurring corruption masking a bug**: If auto-restore opt-in is enabled and corruption recurs, the system must log loudly and (recommended) stop auto-restoring after a threshold rather than silently rolling back on every boot.

## Requirements *(mandatory)*

### Functional Requirements

#### Detection & Classification

- **FR-001 (Startup DB classifier)**: Before running migrations or any DB-dependent startup step, the system MUST classify the app DB into exactly one of: `fresh`, `healthy`, `desynced`, `corrupt`, `restore_in_progress`. Classification MUST use read-only access where possible.
- **FR-002 (Provenance-based freshness)**: `fresh` MUST be determined solely by filesystem provenance — the DB file did not exist before this startup AND no `-wal`/`-shm` sidecars exist. Table emptiness MUST NOT be used to infer `fresh`. Any pre-existing DB artifact MUST be treated as existing user state.
- **FR-003 (Integrity probe)**: The classifier MUST run a SQLite integrity probe (`PRAGMA quick_check`, escalating to `integrity_check` on failure or on a detected mismatch). A failed probe MUST classify the DB as `corrupt`.
- **FR-004 (Schema-desync detection)**: The classifier MUST treat a DB as `desynced` when integrity passes but the expected ORM table set (via `verify_table_integrity()`) is incomplete or the Alembic revision is otherwise inconsistent with the present schema. `verify_table_integrity()` MUST be promoted from CLI-only to a startup gate.
- **FR-005 (No error→fresh collapse)**: Schema/version reads MUST distinguish `unknown`/`error` from `0`/`fresh`. The current behavior of returning `0` on any read error MUST NOT be used for recovery decisions.

#### Preservation (Data-Safety Invariant)

- **FR-006 (Snapshot before remediation)**: Before any remediation that could alter, replace, reset, or reinterpret the DB, the system MUST snapshot the full DB trio (`.db`, `-wal`, `-shm`) plus metadata (size, sha256, timestamp, detected state) to `data/backups/quarantine/<timestamp>/` alongside the existing 027 backup tree.
- **FR-007 (Never delete the only copy)**: The system MUST NEVER `rm`/truncate/overwrite the only copy of the app DB as an automatic action. Resets MUST move the suspect DB to a timestamped quarantine path (copy/rename that preserves bytes), never delete it.
- **FR-008 (Refuse-unsafe-on-no-space)**: If a required preserving snapshot cannot be written (e.g. insufficient space), the system MUST refuse the destructive action and report the shortfall rather than proceeding.
- **FR-009 (Preserved-artifact visibility)**: The location of every preserved/quarantined artifact MUST be surfaced in logs and in the recovery UI/API.

#### Maintenance / Recovery Mode

- **FR-010 (Boot into maintenance mode, never exit)**: On `desynced` or `corrupt` classification, the system MUST NOT call `sys.exit`. It MUST bind the configured port and enter a maintenance/recovery mode.
- **FR-010a (Auth-exempt recovery surface)**: The recovery page, state display, backup listing, liveness, and readiness endpoints MUST be auth-exempt so they remain reachable when the app DB (which backs auth) is broken. State-altering recovery actions MUST require a bearer token from `ANVIL_RECOVERY_KEY` env var; if unset, such actions are rejected with a clear message.
- **FR-011 (Read-only safety in maintenance mode)**: In maintenance mode the system MUST NOT perform writes against the suspect app DB except via an explicit, operator-confirmed recovery action.
- **FR-012 (Route isolation)**: In maintenance mode, normal application routes MUST be disabled or return a clear "recovery mode" response; only the recovery surface, liveness, readiness, static assets, and (read-only) backup listing are served.
- **FR-013 (Recovery surface)**: The system MUST serve a recovery page (and a backing API) that displays the detected DB state, the cause, the preserved-artifact location(s), the available backups, and the operator-gated recovery actions.

#### Operator-Gated Recovery Actions

- **FR-014 (Explicit confirmation)**: Each state-altering recovery action — restore-from-backup, quarantine+reset, retry-migrations, advanced-salvage — MUST require an explicit confirmation token and MUST be preceded by a preserving snapshot (FR-006).
- **FR-015 (Restore composition)**: "Restore from backup" MUST reuse the existing 027 restore engine (schema-compatibility check, pre-restore safety snapshot, `RestoreJournal` swap protection) rather than introducing a parallel mechanism.
- **FR-016 (Quarantine + reset)**: "Quarantine + reset" MUST move the suspect DB to quarantine (FR-007) and initialize a fresh, fully-migrated DB.
- **FR-017 (Retry migrations)**: "Retry migrations" MUST snapshot first, then re-attempt migrations; on continued failure the system MUST remain in maintenance mode and surface the new error.
- **FR-018 (Auto-restore is opt-in)**: Automatic restore-from-latest-verified-backup on detected corruption MUST be gated behind an explicit, default-off policy flag (e.g. `ANVIL_AUTO_RESTORE_ON_CORRUPTION`). When enabled it MUST still snapshot the corrupt state first and MUST log the rollback prominently.

#### Sequencing

- **FR-019 (Recovery-first lifespan order)**: The startup lifespan MUST execute in this order: (1) minimal filesystem bootstrap, (2) `RestoreJournal` recovery, (3) DB classification, (4) state-driven branch (init+migrate for `fresh`, migrate/verify for `healthy`, snapshot+maintenance for `desynced`/`corrupt`), (5) only then MLflow start, tracking reconcile, license seeding, demo bootstrap, and model warmup.
- **FR-020 (Best-effort steps cannot abort boot)**: Optional/best-effort startup steps MUST catch a broad exception set, MUST run only after the DB is declared writable, and a failure MUST degrade only that feature (logged at WARN) without aborting process startup or readiness.

#### Health Signal

- **FR-021 (Liveness/readiness split)**: The system MUST expose liveness (`GET /v1/health`, returns 200 while the process is alive, including in maintenance mode) separately from readiness (`GET /v1/ready`, returns 503 until the DB is writable and startup completed). Readiness responses MUST include the DB state and detected cause when not ready.
- **FR-022 (Healthcheck guidance)**: Deployment healthchecks (Docker/orchestrator) MUST be documented to target liveness for container survival and readiness for traffic gating, so a maintenance-mode container is kept alive for recovery rather than crash-looped.

#### Tooling (non-startup)

- **FR-023 (Salvage is copy-only CLI)**: SQLite-level salvage (`.recover`, WAL surgery) MUST NOT be an automatic startup behavior. If provided, it MUST be an operator-invoked CLI that operates on a copy of the artifacts, never the live files.

### Key Entities *(include if feature involves data)*

- **DbState**: Enumeration of the startup classification — `fresh`, `healthy`, `desynced`, `corrupt`, `restore_in_progress`. Drives all startup branching.
- **StartupClassifier**: Read-only component that inspects filesystem provenance, runs the integrity probe, and compares expected vs. actual tables/revision to produce a `DbState`.
- **DbSnapshot / Quarantine artifact**: A preserved, timestamped copy of the DB trio (`.db`, `-wal`, `-shm`) plus a small manifest (size, sha256, timestamp, detected state, cause). Quarantine is the move-aside variant used by reset.
- **MaintenanceMode**: A runtime mode flag (on `app.state`) that gates route availability, write access, and readiness. Carries the detected `DbState`, cause, preserved-artifact paths, and available actions.
- **RecoveryAction**: An operator-gated, confirmation-required operation (`restore`, `quarantine_reset`, `retry_migrations`, `salvage`) that always snapshots before mutating.
- **RestoreJournal** *(existing, 027)*: Crash-safe marker enabling rollback of an interrupted restore; now consumed first in the lifespan.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (No silent death)**: With a schema-desynced or corrupt DB, the server process stays alive and binds the port 100% of the time; `GET /v1/health` returns 200. Verified by: desync/corrupt fixtures + startup assertion.
- **SC-002 (Zero automatic data loss)**: No code path deletes or overwrites the only copy of the app DB automatically. Verified by: a test that asserts the original DB bytes are preserved (quarantined/snapshotted) across every detection and every reset path; a static check that startup contains no destructive DB delete.
- **SC-003 (Honest readiness)**: In maintenance mode `GET /v1/ready` returns 503 with the detected cause; in normal mode it returns 200. Verified by: endpoint tests in both modes.
- **SC-004 (Boot survives best-effort failure)**: Injecting any exception (`SQLAlchemyError`, `OSError`, generic `Exception`) into each best-effort startup step still yields a fully-started, ready server on a healthy DB. Verified by: parametrized fault-injection tests.
- **SC-005 (Correct classification)**: The classifier returns the correct `DbState` for all five fixtured states, and never returns `fresh` for a pre-existing artifact. Verified by: classifier unit tests including the zero-byte-file case.
- **SC-006 (Guided recovery works)**: From maintenance mode, restore-from-backup, quarantine+reset, and retry-migrations each succeed against fixtures, each requires confirmation, and each is preceded by a snapshot. Verified by: recovery-action integration tests.
- **SC-007 (The incident is fixed)**: Reproducing the original incident (revision stamped at head, all tables dropped) results in maintenance mode + preserved DB + a reachable recovery page — not exit code 3 and not data loss. Verified by: a regression test reproducing the exact desync.

## Assumptions

- The app DB is SQLite in WAL mode accessed via async SQLAlchemy + `aiosqlite`; large blobs (models, datasets, `mlruns`) live on the filesystem, not in the DB.
- The existing 027 `BackupService`, `SnapshotPlanner`, `RestoreEngine`, and `RestoreJournal` are available and are the canonical mechanism for snapshot/restore; this spec composes with them rather than replacing them.
- The existing `MigrationService.verify_table_integrity()` and `get_expected_tables()` are available and accurate enough to detect missing tables.
- Recovery operations are performed by a trusted operator (single-tenant local deployment, or an authenticated operator in SaaS); the recovery surface read-only views (page, state display, backup listing) and the liveness/readiness endpoints are auth-exempt. State-altering actions require a pre-configured bearer token (`ANVIL_RECOVERY_KEY` envar) to prevent the DB-deadlock where auth depends on a broken database.
- Per Constitution Article XI (Simplicity First / Boring Technology), the implementation prefers stdlib + the existing backup stack; no new runtime dependency is introduced for detection, preservation, or maintenance mode.
- "Restore from backup" is acknowledged to be a rollback to backup time; recovering data committed after the last backup is explicitly out of scope (see honest failure modes in `research.md`).
- Auto-restore-on-corruption is off by default; the universal default is preserve + maintenance mode + operator decision.

## Out of Scope

- Reconstructing transactions lost to physical byte corruption or an externally-lost WAL — no app-level workflow can recover what is not on disk.
- Automatic logical merge of quarantined data back into a fresh DB.
- The MLflow tracking-sidecar degraded mode — owned by [[Specs/057-degraded-mode-recovery/spec|057 Degraded Mode Recovery]].
- Cross-instance/global-registry corruption handling beyond per-workspace isolation.

## Related

- [[Specs/027 Deployment Backup Restore/spec|027 Deployment Backup Restore]] — composes with (snapshot/restore engine, `RestoreJournal`).
- [[Specs/057-degraded-mode-recovery/spec|057 Degraded Mode Recovery]] — sibling (MLflow tracking sidecar; different subsystem).
- [[Specs/011 Auto DB Schema/011 Auto DB Schema|011 Auto DB Schema]] — Alembic auto-migration infrastructure this builds on.
- `research.md` — full recovery-strategy options analysis with pros/cons and the ranked recommendation.
