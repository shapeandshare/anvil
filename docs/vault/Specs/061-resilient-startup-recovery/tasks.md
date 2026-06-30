# Tasks: 061 Resilient Startup & Data-Safe Database Recovery

**Input**: Design documents from `docs/vault/Specs/061-resilient-startup-recovery/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/recovery-api.md

**Tests**: Test tasks are included per Constitution Article IV (TDD Mandatory). Each user story has an Independent Test criterion from the spec.

**Implementation order**: US3 (classifier) → US2 (snapshot) → US1 (maintenance mode) → US4 (best-effort fix) → US6 (health) → US5 (recovery actions). US3 and US2 are prerequisites for the US1 MVP.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create new files and sub-packages needed by the feature

- [ ] T001 [P] Create `anvil/services/recovery/__init__.py` with bare docstring for new domain sub-package
- [ ] T002 [P] Create `anvil/services/recovery/recovery_service.py` stub with class skeleton
- [ ] T003 [P] Create `anvil/services/recovery/snapshot.py` stub with class skeleton
- [ ] T004 [P] Create `anvil/services/recovery/quarantine.py` stub with class skeleton
- [ ] T005 [P] Create `anvil/db/db_state.py` stub with DbState enum and StartupClassifier skeleton
- [ ] T006 [P] Create `anvil/api/v1/recovery.py` stub module for recovery routes
- [ ] T007 [P] Create `anvil/api/templates/recovery.html` placeholder for recovery page

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure ALL user stories depend on — DbState enum, MigrationService fixes for schema version reads, test fixtures

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 [P] Define `DbState` StrEnum in `anvil/db/db_state.py` with values: FRESH, HEALTHY, DESYNCED, CORRUPT, RESTORE_IN_PROGRESS
- [ ] T009 [P] Define `IntegrityResult` and `SchemaResult` Pydantic BaseModel classes in `anvil/db/db_state.py`
- [ ] T010 Fix `MigrationService.get_schema_version()` in `anvil/db/migration.py` to return `int | None` (None = read error) instead of silently returning 0 on any exception; update `ensure_schema_version()` and `health_detailed()` call sites
- [ ] T011 [P] Create test fixture helpers for DB states in `tests/conftest.py` — fixtures for: fresh (no file), healthy (migrated), desynced (stamped but tables dropped), corrupt (invalid SQLite), zero-byte DB

**Checkpoint**: Foundation ready — DbState enum defined, get_schema_version() distinguishes error from fresh, all test fixtures available. User story implementation can now begin.

---

## Phase 3: User Story 3 — Startup Classifies the Database Before Touching It (Priority: P2)

**Goal**: Before running migrations or any DB-dependent startup step, the system classifies the DB into one of five explicit states using read-only checks and filesystem provenance.

**Independent Test**: Construct fixtures for each of the five states and assert the classifier returns the correct `DbState` and that `fresh` is decided by provenance (file/sidecar absence), never by table emptiness.

### Tests for User Story 3

- [ ] T012 [P] [US3] Unit test: classifier returns `FRESH` when DB file + sidecars absent in `tests/unit/test_startup_classifier.py`
- [ ] T013 [P] [US3] Unit test: classifier returns `HEALTHY` for valid migrated DB in `tests/unit/test_startup_classifier.py`
- [ ] T014 [P] [US3] Unit test: classifier returns `DESYNCED` for stamped-but-missing-tables DB in `tests/unit/test_startup_classifier.py`
- [ ] T015 [P] [US3] Unit test: classifier returns `CORRUPT` for invalid SQLite file in `tests/unit/test_startup_classifier.py`
- [ ] T016 [P] [US3] Unit test: classifier returns `RESTORE_IN_PROGRESS` when `.restore-journal.json` exists in `tests/unit/test_startup_classifier.py`
- [ ] T017 [US3] Unit test: classifier returns NOT `FRESH` for zero-byte DB file (provenance rule) in `tests/unit/test_startup_classifier.py`

### Implementation for User Story 3

- [ ] T018 [US3] Implement `StartupClassifier.check_provenance(db_path)` in `anvil/db/db_state.py` — checks filesystem for `.db`, `-wal`, `-shm` existence; returns True if none exist
- [ ] T019 [P] [US3] Implement `StartupClassifier.check_integrity(db_url)` in `anvil/db/db_state.py` — runs `PRAGMA quick_check` via async SQLAlchemy, escalates to `integrity_check` on failure; returns `IntegrityResult`
- [ ] T020 [P] [US3] Implement `StartupClassifier.check_schema(db_url)` in `anvil/db/db_state.py` — reads `PRAGMA user_version`, Alembic revision via `MigrationService.current()`, runs `verify_table_integrity()`; returns `SchemaResult`
- [ ] T021 [US3] Implement `StartupClassifier.classify(db_url, db_path)` in `anvil/db/db_state.py` — orchestrates check_provenance → check_integrity → check_schema → return DbState; handles RestoreJournal marker detection
- [ ] T022 [US3] Fix `get_expected_tables()` import in `anvil/db/registry.py` if needed for async startup call context

**Checkpoint**: Classifier correctly distinguishes all 5 DB states + the zero-byte edge case. All 6 acceptance scenarios pass.

---

## Phase 4: User Story 2 — The Suspect Database Is Always Preserved (Priority: P1)

**Goal**: When the system detects a bad DB or before performing any operator-approved repair, it always preserves the current on-disk state (`.db`, `-wal`, `-shm` trio) to a timestamped, clearly-labeled location.

**Independent Test**: Trigger detection on a populated-but-corrupt DB, then verify the original bytes exist intact at a quarantine/snapshot path with a recorded manifest (size, sha256, timestamp), and that the original path was copied (not moved-then-lost) before any further action.

### Tests for User Story 2

- [ ] T023 [P] [US2] Unit test: `DbSnapshot` writes DB trio + manifest to `data/backups/quarantine/<timestamp>/` in `tests/unit/test_recovery.py`
- [ ] T024 [P] [US2] Unit test: snapshot manifest contains correct size, sha256, timestamp, detected state in `tests/unit/test_recovery.py`
- [ ] T025 [US2] Unit test: quarantine moves (does not delete) suspect DB, frees original path in `tests/unit/test_recovery.py`
- [ ] T026 [US2] Unit test: snapshot refuses if destination path has insufficient space (mock `shutil.disk_usage`) in `tests/unit/test_recovery.py`

### Implementation for User Story 2

- [ ] T027 [P] [US2] Implement `SnapshotManifest` Pydantic BaseModel with `size_bytes`, `sha256`, `timestamp`, `detected_state`, `cause` in `anvil/services/recovery/snapshot.py`
- [ ] T028 [P] [US2] Implement `DbSnapshot` class with `take_snapshot(db_path, dest_dir, state, cause)` in `anvil/services/recovery/snapshot.py` — copies `.db`, `-wal`, `-shm` trio to `data/backups/quarantine/<timestamp>/`, writes `manifest.json`, **logs the destination path at INFO** (FR-009)
- [ ] T029 [P] [US2] Implement `Quarantine` class with `quarantine(db_path, dest_dir, state, cause)` in `anvil/services/recovery/quarantine.py` — moves (does not delete) DB trio to quarantine, writes manifest
- [ ] T030 [US2] Implement space check in `anvil/services/recovery/snapshot.py` using `shutil.disk_usage` and required space estimate; raise `OSError` if insufficient (FR-008)

**Checkpoint**: Suspect DB is always snapshot before any destructive action; manifest records metadata; never deletes without preserve first.

---

## Phase 5: User Story 1 — Server Never Dies Silently on a Bad Database (Priority: P1) 🎯 MVP

**Goal**: With a desynced or corrupt DB, the server boots into maintenance/recovery mode: binds port, liveness passes, recovery page reachable — instead of `sys.exit(3)`.

**Independent Test**: Corrupt or desync a test DB, start the app, and verify (a) the process stays alive, (b) `GET /v1/health` returns 200, (c) `GET /v1/ready` returns 503, and (d) the recovery page renders with the detected fault and available actions.

**This is the MVP increment that delivers the core value of the spec.**

### Tests for User Story 1

- [ ] T031 [P] [US1] e2e test: start app with desynced DB fixture → assert process alive, `GET /v1/health` → 200 in `tests/e2e/test_maintenance_mode.py`
- [ ] T032 [P] [US1] e2e test: desynced DB → `GET /v1/ready` → 503 with correct cause in `tests/e2e/test_maintenance_mode.py`
- [ ] T033 [P] [US1] e2e test: corrupt DB → maintenance mode with `corrupt` as cause in `tests/e2e/test_maintenance_mode.py`
- [ ] T034 [P] [US1] e2e test: normal DB → both health and ready return 200 in `tests/e2e/test_maintenance_mode.py`
- [ ] T035 [US1] e2e test: healthy DB routes work; desynced DB routes return "recovery mode" response in `tests/e2e/test_maintenance_mode.py`
- [ ] T036 [US1] e2e test: zero-byte DB does NOT auto-init — enters maintenance mode in `tests/e2e/test_maintenance_mode.py`
- [ ] T037 [US1] e2e regression test: reproduce the original incident (alembic_version stamped at `007`, all tables dropped) → server enters maintenance mode, preserves DB, serves recovery page — NOT exit code 3 (SC-007) in `tests/e2e/test_maintenance_mode.py`

### Implementation for User Story 1

- [ ] T038 [US1] Reorder `lifespan()` in `anvil/api/app.py` to run RestoreJournal recovery and DB classification before `_init_database()`; branch execution based on `DbState`:
  - `FRESH`/`HEALTHY` → normal startup (current flow)
  - `DESYNCED`/`CORRUPT` → snapshot suspect DB → enter maintenance mode → skip best-effort steps
  - `RESTORE_IN_PROGRESS` → journal recovery → reclassify
- [ ] T039 [US1] Replace `sys.exit(1)` in `anvil/api/app.py::_init_database()` with setting maintenance mode state on `app.state` instead
- [ ] T040 [US1] Define `MaintenanceMode` Pydantic BaseModel in `anvil/services/recovery/recovery_service.py` with fields: `active`, `db_state`, `cause`, `detected_at`, `preserved_path`, `available_actions`
- [ ] T041 [P] [US1] Implement maintenance mode middleware/dependency in `anvil/api/deps.py` — checks `request.app.state.maintenance_mode`; if active and route is not in exempt list, returns 503 "recovery mode"
- [ ] T042 [P] [US1] Implement `GET /v1/recovery` endpoint in `anvil/api/v1/recovery.py` — returns current maintenance mode state (auth-exempt)
- [ ] T043 [US1] Implement `GET /v1/recovery/page` endpoint in `anvil/api/v1/recovery.py` — renders recovery.html template with DB state, cause, preserved artifact, available actions (auth-exempt)
- [ ] T044 [US1] Create `recovery.html` Jinja2 template in `anvil/api/templates/recovery.html` — shows DB state, cause, detected time, preserved artifact path, available action buttons, and message to set ANVIL_RECOVERY_KEY if unset
- [ ] T045 [US1] Register recovery router and readiness router in `anvil/api/v1/router.py` so routes are mounted at `/v1/`

**Checkpoint**: MVP complete — server survives bad DB, enters maintenance mode, serves recovery page, never silently exits. The original incident is fixed (SC-007).

---

## Phase 6: User Story 4 — Best-Effort Startup Steps Can Never Crash the Boot (Priority: P2)

**Goal**: Optional startup steps (license seeding, demo bootstrap, warmup) run only after DB is declared writable; failures degrade gracefully without aborting process startup.

**Independent Test**: Inject a failure into each best-effort step and verify the server still completes startup, becomes ready, and logs the degraded step.

### Tests for User Story 4

- [ ] T046 [P] [US4] Unit test: inject `SQLAlchemyError` into `_seed_license_catalog()` → startup completes, WARN logged in `tests/unit/test_startup_sequencing.py`
- [ ] T047 [P] [US4] Unit test: inject `OSError` into `_bootstrap_demo_data()` → startup completes, WARN logged in `tests/unit/test_startup_sequencing.py`
- [ ] T048 [P] [US4] Unit test: inject generic `Exception` into `_warmup_demo_model()` → startup completes, WARN logged in `tests/unit/test_startup_sequencing.py`
- [ ] T049 [US4] Unit test: in desynced/corrupt mode, best-effort steps are skipped entirely (not attempted) in `tests/unit/test_startup_sequencing.py`

### Implementation for User Story 4

- [ ] T050 [US4] Broaden exception handling in `_seed_license_catalog()` in `anvil/api/app.py` — catch `Exception` (not just `ValueError`/`RuntimeError`); log at WARN, never abort
- [ ] T051 [P] [US4] Broaden exception handling in `_bootstrap_demo_data()` in `anvil/api/app.py` — catch `Exception` (not just `ValueError`/`RuntimeError`/`OSError`); log at WARN
- [ ] T052 [P] [US4] Broaden exception handling in `_warmup_demo_model()` in `anvil/api/app.py` — catch `Exception` for thread launch; log at WARN
- [ ] T053 [US4] In lifespan, gate all best-effort startup steps (MLflow start, tracking reconcile, seeding, bootstrap, warmup) behind `app.state.maintenance_mode is None` — skip entirely if in maintenance mode
- [ ] T054 [US4] In lifespan, move `_init_backup_service()` (which includes `recover_interrupted_restore()`) to run before classification per FR-019 order

**Checkpoint**: Best-effort steps never abort the process; degraded features are logged; maintenance mode correctly skips all DB-dependent steps.

---

## Phase 7: User Story 6 — Honest Health Signal (Liveness vs Readiness) (Priority: P3)

**Goal**: Orchestrators can distinguish "process is alive" from "app is fully usable." Liveness stays green in maintenance mode; readiness is red until DB is writable.

**Independent Test**: In maintenance mode, assert `GET /v1/health` → 200 and `GET /v1/ready` → 503 with body describing the detected fault; in normal mode assert both are 200.

### Tests for User Story 6

- [ ] T055 [P] [US6] e2e test: in maintenance mode `GET /v1/health` → 200 in `tests/e2e/test_recovery_endpoints.py`
- [ ] T056 [P] [US6] e2e test: in maintenance mode `GET /v1/ready` → 503 with db_state and cause in `tests/e2e/test_recovery_endpoints.py`
- [ ] T057 [US6] e2e test: in normal mode both endpoints → 200 in `tests/e2e/test_recovery_endpoints.py`

### Implementation for User Story 6

- [ ] T058 [US6] Implement `GET /v1/ready` endpoint in `anvil/api/v1/health_ops.py` — returns 200 with `{"status":"ready"}` if `app.state.maintenance_mode` is absent; returns 503 with `{"status":"not_ready","db_state":"...","cause":"..."}` if in maintenance mode (auth-exempt)
- [ ] T059 [US6] Register ready router in `anvil/api/v1/router.py`
- [ ] T060 [P] [US6] Add liveness route to auth-exempt routes list in `anvil/api/auth.py` if not already there (confirm `GET /v1/ready` is also exempt)
- [ ] T061 [US6] Update `compose.yaml` healthcheck documentation (or inline comment) to target `GET /v1/health` (liveness) so containers survive maintenance mode (FR-022)

**Checkpoint**: Health signals are honest. Liveness keeps container alive; readiness correctly reflects DB state.

---

## Phase 8: User Story 5 — Operator-Gated Recovery Actions From the Recovery Surface (Priority: P3)

**Goal**: From the maintenance-mode recovery surface (UI + API), the operator can choose an explicit recovery action — restore from backup, quarantine+reset, retry migrations — each requiring explicit confirmation and a preserving snapshot.

**Independent Test**: From maintenance mode, exercise each action against fixtures and verify confirmation is required, a snapshot precedes the action, and the resulting state is correct.

### Tests for User Story 5

- [ ] T062 [P] [US5] e2e test: restore-from-backup action requires confirmation + recovery key in `tests/e2e/test_recovery_actions.py`
- [ ] T063 [P] [US5] e2e test: quarantine+reset moves suspect DB to quarantine, inits fresh DB in `tests/e2e/test_recovery_actions.py`
- [ ] T064 [P] [US5] e2e test: retry-migrations snapshots first, attempts migration, reports result in `tests/e2e/test_recovery_actions.py`
- [ ] T065 [US5] e2e test: action without `ANVIL_RECOVERY_KEY` returns 403 in `tests/e2e/test_recovery_actions.py`
- [ ] T066 [US5] e2e test: action without confirmation token returns 400 in `tests/e2e/test_recovery_actions.py`

### Implementation for User Story 5

- [ ] T067 [P] [US5] Define `RecoveryAction` StrEnum in `anvil/services/recovery/recovery_service.py` with values: `RESTORE`, `QUARANTINE_RESET`, `RETRY_MIGRATIONS`, `SALVAGE`
- [ ] T068 [P] [US5] Implement `RecoveryService.verify_recovery_token(token)` in `anvil/services/recovery/recovery_service.py` — compares against `ANVIL_RECOVERY_KEY` env var; returns bool
- [ ] T069 [US5] Implement `RecoveryService.snapshot_suspect_db(db_path, state, cause)` in `anvil/services/recovery/recovery_service.py` — delegates to `DbSnapshot.take_snapshot()`, returns `DbSnapshot`
- [ ] T070 [P] [US5] Implement `RecoveryService.list_available_backups()` in `anvil/services/recovery/recovery_service.py` — scans `data/backups/backup-*.tar.gz` files, reads manifests via `ArchiveReader` (filesystem-only, no DB)
- [ ] T071 [P] [US5] Implement `RecoveryService.restore_from_backup(backup_id, token)` in `anvil/services/recovery/recovery_service.py` — delegates to existing `BackupService.restore()` after token + confirmation validation (FR-015)
- [ ] T072 [P] [US5] Implement `RecoveryService.quarantine_and_reset(db_path, state, cause, token)` in `anvil/services/recovery/recovery_service.py` — delegates to `Quarantine`, then triggers fresh DB init
- [ ] T073 [US5] Implement `RecoveryService.retry_migrations(db_url, token)` in `anvil/services/recovery/recovery_service.py` — snapshots first, then runs `MigrationService.ensure_migrated()`; on failure, stays in maintenance mode
- [ ] T074 [US5] Implement `GET /v1/recovery/backups` endpoint in `anvil/api/v1/recovery.py` — returns list of available backups from filesystem scan (auth-exempt)
- [ ] T075 [P] [US5] Implement `GET /v1/recovery/actions/{action}` endpoint in `anvil/api/v1/recovery.py` — returns confirmation shape (auth-exempt)
- [ ] T076 [US5] Implement `POST /v1/recovery/actions/{action}` endpoint in `anvil/api/v1/recovery.py` — validates recovery key (Bearer), validates confirmation token, executes action via `RecoveryService`, returns result
- [ ] T077 [US5] Wire recovery key check into recovery endpoint — read `ANVIL_RECOVERY_KEY` from env, set on `app.state` at startup; if unset, destructive actions return 403 with guidance message
- [ ] T078 [US5] Update `recovery.html` template to show backup list, action forms with confirmation fields, and recovery key status indicator

**Checkpoint**: All 3 operator-gated recovery actions work; confirmation and recovery key required; each action preceded by safety snapshot.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that tie everything together, edge case hardening, and quality gates

- [ ] T079 Add configuration docs for `ANVIL_RECOVERY_KEY` and `ANVIL_AUTO_RESTORE_ON_CORRUPTION` to `.env.example`
- [ ] T080 [P] Update ops dashboard (if one exists) to show maintenance mode status
- [ ] T081 Document healthcheck guidance in `compose.yaml` comments and `README.md` (liveness vs readiness)
- [ ] T082 [P] Add edge case: snapshot fails for lack of space — ensure FR-008 behavior is tested across all action paths
- [ ] T083 [P] Add edge case: `RestoreJournal` marker found during startup — verify journal.recover() runs before classifier (FR-019 order)
- [ ] T084 [P] Implement auto-restore threshold counter: track consecutive auto-restore attempts on `app.state`, stop auto-restoring after N failures (recommended: 3), log loudly at CRITICAL with instructions to investigate (Edge Cases: recurring corruption)
- [ ] T085 [P] Add edge case test: recurring corruption with `ANVIL_AUTO_RESTORE_ON_CORRUPTION` enabled — verify stop-after-N threshold triggers correctly in `tests/e2e/test_recovery_actions.py`
- [ ] T086 **UX compliance gate** — run `make ux-lint` on `recovery.html` and any changed CSS — must pass GATE: PASS before merge
- [ ] T087 **Vault audit** — run `make vault-audit` — must report 0 errors before merging
- [ ] T088 **Full quality gate** — run `make lint` + `make typecheck` + `make test` — all must pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US3 — Classifier (Phase 3)**: Depends on Foundational (DbState, MigrationService fix) — BLOCKS US1, US4
- **US2 — Preservation (Phase 4)**: Depends on Foundational — BLOCKS US1, US5
- **US1 — Maintenance Mode (Phase 5)**: Depends on US3 (classifier) + US2 (snapshot) — **MVP**
- **US4 — Best-Effort Steps (Phase 6)**: Depends on US3 (classifier result) — can run in parallel with US2
- **US6 — Health Endpoints (Phase 7)**: Depends on Foundational + US1 (maintenance mode state) — simple, can run with US5
- **US5 — Recovery Actions (Phase 8)**: Depends on US1 (maintenance mode) + US2 (snapshot)
- **Polish (Phase 9)**: Depends on all desired stories

### User Story Dependencies Graph

```
Foundational (P2)
    ├──→ US3: Classifier ←── blocks US1, US4
    ├──→ US2: Snapshot  ←── blocks US1, US5
    │
    ├──→ US4: Best-effort (needs US3 classification)
    │
    └──→ US1: Maintenance Mode (needs US3 + US2) ←── MVP!
             ├──→ US6: Health endpoints (needs US1 state)
             └──→ US5: Recovery actions (needs US1 + US2)
```

### Parallel Opportunities

- All [P]-marked tasks within a phase can run in parallel
- **US2 (snapshot) and US3 (classifier)** can run in parallel after Foundational
- **US6 (health) and US5 (recovery actions)** can run in parallel after US1
- Within US5: recovery service, snapshot action, restore action, quarantine action, and backup listing can all be implemented as parallel [P] tasks
- Test tasks marked [P] can run in parallel within each story
- Within a story: models/services marked [P] can run in parallel

---

## Parallel Example: MVP Phase (Phases 3 + 4 + 5)

```bash
# After Foundational (Phase 2) completes, launch US3 + US2 in parallel:

# === US3: Classifier (all [P] tasks) ===
Task: T018 StartupClassifier.check_provenance() in anvil/db/db_state.py
Task: T019 StartupClassifier.check_integrity() in anvil/db/db_state.py
Task: T020 StartupClassifier.check_schema() in anvil/db/db_state.py

# === US2: Snapshot (all [P] tasks) ===
Task: T027 SnapshotManifest in anvil/services/recovery/snapshot.py
Task: T028 DbSnapshot.take_snapshot() in anvil/services/recovery/snapshot.py
Task: T029 Quarantine.quarantine() in anvil/services/recovery/quarantine.py

# After US3 + US2 complete, US1 can begin:
# === US1: Maintenance Mode ===
Task: T038 Reorder lifespan() in anvil/api/app.py
Task: T039 Replace sys.exit(1) with maintenance mode
Task: T040 MaintenanceMode Pydantic BaseModel
Task: T041 Maintenance mode middleware in anvil/api/deps.py
Task: T042 GET /v1/recovery endpoint
Task: T043 GET /v1/recovery/page endpoint
Task: T007 recovery.html Jinja2 template
```

## Implementation Strategy

### MVP First (Phase 3 + 4 + 5 = US3 + US2 + US1)

The minimum viable scope covers the core "pit of success" requirement:

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US3 (Classifier) — needed by US1
4. Complete Phase 4: US2 (Snapshot) — needed by US1
5. Complete Phase 5: US1 (Maintenance Mode) — the MVP!
6. **STOP and VALIDATE**: Desync/corrupt a test DB, start the app — it should enter maintenance mode, bind the port, serve recovery page, and never exit
7. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → core types + fixtures ready
2. Add US3 + US2 → can classify and preserve (not yet visible to user)
3. Add US1 → **MVP: maintenance mode + recovery page** → deploy/demo
4. Add US4 → startup robustness improved
5. Add US6 → honest health signals for orchestrators
6. Add US5 → full recovery actions from the UI
7. Polish → vault audit, UX lint, quality gates

## Notes

- [P] tasks = different files, no dependencies — can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests MUST be written before implementation (Red-Green-Refactor, Article IV)
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All new files must have bare `__init__.py` with docstring (Article VI)
- All new types must use Pydantic `BaseModel` or `StrEnum` (not `@dataclass`)
- No new runtime dependencies (stdlib only for additions)