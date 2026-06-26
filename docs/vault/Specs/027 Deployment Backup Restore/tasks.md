---
title: 'Tasks: Deployment Backup and Restore'
type: spec
tags:
  - type/spec
  - domain/operations
status: draft
created: '2026-06-21'
updated: '2026-06-21'
---

Back to [[Specs/027 Deployment Backup Restore/spec]].

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Enums, value types, ORM model, migration, repository, audit-enum extensions, and the shared `BackupService` skeleton + god-class/app wiring. **No user story can be implemented until this phase is complete.**

**⚠️ CRITICAL**: Complete this entire phase before starting any user-story phase.

### Enums (StrEnum — one per file, co-located in domain)

- [x] T005 [P] Create `BackupStatus(StrEnum)` (`creating`/`completed`/`failed`/`corrupted`) in `anvil/services/backup/backup_status.py`.
- [x] T006 [P] Create `BackupOperationType(StrEnum)` (`backup`/`restore`/`pre_restore_safety`) in `anvil/services/backup/backup_operation_type.py`.
- [x] T007 [P] Create `SchemaCompatibility(StrEnum)` (`ok`/`warn`/`blocked`) in `anvil/services/backup/schema_compatibility.py`.

### Audit enum extensions (existing governance domain — FR-031, R11)

- [x] T008 [P] Add members to `AuditAction` in `anvil/services/governance/audit_action.py`: `BACKUP_CREATE = "backup_create"`, `BACKUP_RESTORE = "backup_restore"`, `BACKUP_DELETE = "backup_delete"`, `SAFETY_SNAPSHOT_CLEANUP = "safety_snapshot_cleanup"`.
- [x] T009 [P] Add member `BACKUP = "backup"` to `AuditTargetType` in `anvil/services/governance/audit_target_type.py`.

### Value & result types (Pydantic BaseModel — one per file)

- [x] T010 [P] Create `ManifestEntry(BaseModel)` (`path`, `sha256`, `size`) in `anvil/services/backup/manifest_entry.py`.
- [x] T011 [P] Create `BackupManifest(BaseModel)` (`manifest_version`, `backup_id`, `created_at`, `operation_type`, `deployment_version`, `schema_revision`, `total_uncompressed_bytes`, `entries: list[ManifestEntry]`; `extra="ignore"`) in `anvil/services/backup/backup_manifest.py`.
- [x] T012 [P] Create `BackupSummary(BaseModel)` (incl. derived `age_seconds`, `is_safety_snapshot`, `deletable`) in `anvil/services/backup/backup_summary.py`.
- [x] T013 [P] Create `BackupStorageStatus(BaseModel)` (count/total/quota/fraction/threshold/latest/oldest) in `anvil/services/backup/backup_storage_status.py`.
- [x] T014 [P] Create `RestorePreview(BaseModel)` (manifest details + `compatibility` + `required_free_bytes` + `sufficient_space`) in `anvil/services/backup/restore_preview.py`.
- [x] T015 [P] Create `VerifyResult(BaseModel)` (`backup_id`, `valid`, `checked_count`, `mismatched`) in `anvil/services/backup/verify_result.py`.
- [x] T016 [P] Create `ProgressEvent(BaseModel)` (`event`, `operation_type`, `backup_id`, `percent`, `current_step`, `message`, `safety_snapshot_id`) in `anvil/services/backup/progress_event.py`.
- [x] T017 [P] Create `CreateBackupResult(BaseModel)` (`backup_id`, `rotated_backup_ids: list[str]`) in `anvil/services/backup/create_backup_result.py` (lets the route emit audit per rotation — R11).

### Persistence (TDD: tests first)

- [x] T018 [P] Write failing unit tests for `BackupOperationRepository` CRUD in `tests/unit/db/test_backup_operations_repo.py` (create/get_by_backup_id/list/update_fields/delete).
- [x] T019 Create `BackupOperation` ORM model (inherits `Base, TimestampMixin`; columns per data-model.md §1; `backup_id` unique+indexed) in `anvil/db/models/backup_operation.py`.
- [x] T020 Register the new model import in `anvil/_resources/migrations/env.py` so autogenerate sees it.
- [x] T021 Create Alembic revision `003_add_backup_operations.py` (`down_revision="002"`) in `anvil/_resources/migrations/versions/` creating the `backup_operations` table with `upgrade()`/`downgrade()`.
- [x] T022 Implement `BackupOperationRepository` (session-injected, async CRUD mirroring `DatasetRepository`) in `anvil/db/repositories/backup_operations.py` — make T018 tests pass.

### Shared service infrastructure

- [x] T023 [P] Implement `BackupLock` (process-scoped `asyncio.Lock` + in-flight operation descriptor; `try_acquire`/`release`/`current`) in `anvil/services/backup/backup_lock.py`.
- [x] T024 Create the `BackupService` skeleton in `anvil/services/backup/backup_service.py` — constructor takes `backup_dir`, `quota_bytes`, `warn_fraction`, `retention_policy`, and holds a `BackupLock`; sweeps `.tmp/` and `.restore-tmp/` on init (FR-013); declares (stub) async methods: `create_backup`, `list_backups`, `get_backup`, `storage_status`, `restore_preview`, `restore`, `verify`, `delete_backup`, `cleanup_safety`, `stream_for`, `recover_interrupted_restore`. Methods raise `NotImplementedError` for now.
- [x] T025 Wire `BackupService` into app lifespan in `anvil/api/app.py`: instantiate one process-lifetime instance on `app.state.backup_service` at startup, mirroring the existing `app.state.mlflow` assignment (~line 128–132).
- [x] T026 Add god-class accessors in `anvil/workbench.py`: `backup_repo` property (lazy `BackupOperationRepository(self._session)`) and `backup` property returning the shared `app.state.backup_service` bound with the per-request `backup_repo` (add the private attrs in `__init__`). Note: the `audit` accessor already exists and is used by routes, not by `BackupService`.

**Checkpoint**: Types, audit-enum extensions, persistence, lock, service skeleton, and wiring exist. User stories can now be built on top.

---

## Phase 3: User Story 1 — One-Click Full Backup (Priority: P1) 🎯 MVP

**Goal**: Operator creates a complete, consistent, immutable deployment snapshot (DB + persistent filesystem roots, excluding `logs/` and `.env`) via one click / one CLI command, with quota auto-rotation, audit logging, and partial-failure cleanup.

**Independent Test**: Click "Create Backup" (or run `anvil-backup create`); a `.tar.gz` with a valid manifest appears in `data/backups/`, the operation is recorded `completed`, an audit event is written, and `logs/`/`.env` are NOT in the archive.

### Tests for User Story 1 (write first, must FAIL) ⚠️

- [x] T027 [P] [US1] Write failing unit tests for `SnapshotPlanner` (collects all managed roots; **excludes `logs/` and `.env`** per FR-001/R14; uncompressed-size estimate; `disk_usage` + quota pre-flight math) in `tests/unit/services/backup/test_snapshot_planner.py`.
- [x] T028 [P] [US1] Write failing unit tests for `RetentionPolicy` (selects oldest non-safety backups to delete to fit quota/count/age; **never returns a safety-snapshot id**) in `tests/unit/services/backup/test_retention_policy.py`.
- [x] T029 [P] [US1] Write failing unit tests for `ArchiveWriter` (atomic temp→final write, unique timestamped names, `manifest.json` first member, per-file sha256 entries, WAL-safe DB snapshot via `sqlite3.backup()`) in `tests/unit/services/backup/test_archive_writer.py`.
- [x] T030 [P] [US1] Write failing unit tests for `BackupService.create_backup` (lock acquired; row CREATING→COMPLETED; auto-rotation returns `rotated_backup_ids`; partial-failure → FAILED + `.tmp` cleaned; second concurrent create raises busy; **performance assertion (SC-002): backing up a synthetic ~100MB DB + ~500MB files completes in < 30s** — mark with a generous CI margin or `@pytest.mark.slow`) in `tests/unit/services/backup/test_backup_service.py`.
- [x] T031 [P] [US1] Write failing e2e tests for `POST /v1/backup` (202 + id + `rotated_backup_ids`), `GET /v1/backup` (lists completed), 409-on-busy, **assert an `audit_event` row with action `backup_create` exists**, **and a timing assertion (SC-004): `GET /v1/backup` + `GET /v1/backup/status` each return in < 1s with multiple backups present** in `tests/e2e/test_backup_endpoints.py`.

### Implementation for User Story 1

- [x] T032 [P] [US1] Implement `SnapshotPlanner` (managed roots: `data/anvil-state.db`, `data/models/`, `data/datasets/`, `data/storage/`, `data/content/`, `mlruns/`; hard-coded exclusion of `logs/` and `.env`; size estimate; space/quota pre-flight) in `anvil/services/backup/snapshot_planner.py` — make T027 pass.
- [x] T033 [P] [US1] Implement `RetentionPolicy` (given current backups + projected size, return ordered oldest non-safety ids to delete; respect `max_count`/`max_age_days`/`quota_bytes`; exclude safety snapshots) in `anvil/services/backup/retention_policy.py` — make T028 pass.
- [x] T034 [US1] Implement `ArchiveWriter` (WAL-safe DB copy via `sqlite3.Connection.backup()` in a thread; stream files into `tar.gz`; build `BackupManifest` with sha256 per file; atomic `.tmp`→`os.replace`; blocking work via `asyncio.to_thread`) in `anvil/services/backup/archive_writer.py` — make T029 pass.
- [x] T035 [US1] Implement `BackupService.create_backup` (acquire lock or raise busy; pre-flight via `SnapshotPlanner`; run `RetentionPolicy` auto-rotation deleting oldest non-safety to fit quota, collect `rotated_backup_ids`; persist CREATING row; run `ArchiveWriter` with progress callback → queue; on success COMPLETED with size/manifest/version/schema_revision; on failure FAILED + cleanup; release lock; return `CreateBackupResult`) in `anvil/services/backup/backup_service.py` — make T030 pass.
- [x] T036 [US1] Implement `BackupService.list_backups` and `get_backup` (repo → `BackupSummary` with derived fields) in `anvil/services/backup/backup_service.py`.
- [x] T037 [US1] Create the backup API router with `POST /v1/backup` (202; 409 busy; 507 space-after-rotation), `GET /v1/backup` (list), and `GET /v1/backup/{backup_id}` (single, 404 if unknown) in `anvil/api/v1/backup.py`; add request/response Pydantic schemas (`extra="forbid"`); **after success emit `workbench.audit.record(action=backup_create, target=backup, outcome=success)` plus one `backup_delete` audit per id in `rotated_backup_ids`** (R11).
- [x] T038 [US1] Include `backup_router` in `anvil/api/v1/router.py` — make T031 pass.
- [x] T039 [P] [US1] Implement `anvil-backup` CLI skeleton + `create` and `list` subcommands (`build_parser`/`main`/`_cmd_create`/`_cmd_list`; `asyncio.run` + `AsyncSessionLocal`; emit audit in `_run()` via a session-bound workbench; print `rotated_backup_ids`; exit codes 0/3/4 per cli-backup.md) in `anvil/services/backup/cli.py`.

**Checkpoint**: Full backups can be created (with rotation + audit) and listed via API and CLI. MVP deliverable.

---

## Phase 4: User Story 2 — Guided Restore via Wizard (Priority: P1)

**Goal**: Operator restores full deployment state through a guided flow that auto-creates a pre-restore safety snapshot, checks schema compatibility, requires a typed `RESTORE` confirmation, applies the restore atomically with a crash-safe journal + rollback, and writes an audit entry.

**Independent Test**: Create a backup, change state (add a dataset), run restore (UI wizard or CLI); the change is reverted, a safety snapshot id is returned, an injected mid-swap failure leaves the original state intact, a leftover journal triggers recovery on next startup, and an audit `backup_restore` event is written.

### Tests for User Story 2 (write first, must FAIL) ⚠️

- [x] T040 [P] [US2] Write failing unit tests for `ArchiveReader` (verify per-file sha256; reject path-traversal members; refuse higher `manifest_version`; extract to temp dir) in `tests/unit/services/backup/test_archive_reader.py`.
- [x] T041 [P] [US2] Write failing unit tests for schema-compat mapping (`BackupManifest` head vs current Alembic head → OK/WARN/BLOCKED) in `tests/unit/services/backup/test_backup_manifest.py`.
- [x] T042 [P] [US2] Write failing unit tests for `RestoreJournal` (write before swap; clear on success; **startup recovery rolls back from `.bak`, or surfaces recovery state pointing to safety snapshot when `.bak` missing**) in `tests/unit/services/backup/test_restore_journal.py`.
- [x] T043 [P] [US2] Write failing unit tests for `RestoreEngine` (extract→verify→journal→move-aside→swap; **injected swap failure rolls back, original intact** [SC-006]; WAL DB round-trip fidelity [SC-005]) in `tests/unit/services/backup/test_restore_engine.py`.
- [x] T044 [P] [US2] Write failing unit tests for `BackupService.restore` + `restore_preview` + `recover_interrupted_restore` (always creates `PRE_RESTORE_SAFETY` first; BLOCKED compat aborts; missing/incorrect confirm rejected; restore-space pre-flight covers safety snapshot + extract; startup recovery delegates to journal) in `tests/unit/services/backup/test_backup_service.py` (extend).
- [x] T045 [P] [US2] Write failing e2e tests for `GET /v1/backup/{id}/preview`, `POST /v1/backup/{id}/restore` (202 happy w/ safety_snapshot_id; 400 bad confirm; 409 schema BLOCKED), **and assert an `audit_event` with action `backup_restore`** in `tests/e2e/test_backup_endpoints.py` (extend).

### Implementation for User Story 2

- [x] T046 [US2] Implement `ArchiveReader` (open `tar.gz`; read `manifest.json`; reject `..`/absolute members; `manifest_version` gate; stream-verify each member's sha256; safe extract to `data/backups/.restore-tmp/<id>/` via `asyncio.to_thread`) in `anvil/services/backup/archive_reader.py` — make T040 pass.
- [x] T047 [US2] Add schema-compatibility logic (read current Alembic head via `MigrationService`; compare to manifest `schema_revision` + `deployment_version` → `SchemaCompatibility` + detail string) in `anvil/services/backup/restore_engine.py` — make T041 pass.
- [x] T048 [US2] Implement `RestoreJournal` (write/read/clear `data/backups/.restore-journal.json`; fields per data-model.md; recovery helper that rolls back from `.bak` or reports recovery state) in `anvil/services/backup/restore_journal.py` — make T042 pass.
- [x] T049 [US2] Implement `RestoreEngine` (extract+verify via `ArchiveReader`; write `RestoreJournal` before swap; pause MLflow sidecar; per-root move-aside `.bak` → `os.replace`/move restored in; delete `.bak` + clear journal on full success; rollback `.bak` on any failure; progress callback → queue) in `anvil/services/backup/restore_engine.py` — make T043 pass.
- [x] T050 [US2] Implement `BackupService.restore_preview` (load manifest, compute compat + space pre-flight → `RestorePreview`) in `anvil/services/backup/backup_service.py`.
- [x] T051 [US2] Implement `BackupService.restore` (acquire lock; validate `confirm=="RESTORE"`; block on `SchemaCompatibility.BLOCKED`; auto-create `PRE_RESTORE_SAFETY` snapshot; record RESTORE row; run `RestoreEngine`; persist `safety_snapshot_id`; COMPLETED/FAILED; release lock) and `recover_interrupted_restore` (called at startup; delegate to `RestoreJournal` recovery) in `anvil/services/backup/backup_service.py` — make T044 pass.
- [x] T052 [US2] Call `BackupService.recover_interrupted_restore()` from the app startup lifespan in `anvil/api/app.py` (after DB init/migrate, before serving) so an interrupted restore (FR-030) is recovered on boot.
- [x] T053 [US2] Add `GET /v1/backup/{id}/preview` and `POST /v1/backup/{id}/restore` (202; 400 bad confirm; 409 busy/BLOCKED; 507 space) to `anvil/api/v1/backup.py`; **emit `workbench.audit.record(action=backup_restore, ...)` after success** — make T045 pass.
- [x] T054 [US2] Implement CLI `restore` subcommand (auto safety snapshot; print compat; interactive typed-`RESTORE` prompt always required; `--force` skips only service-pause confirm; emit `backup_restore` audit in `_run()`; exit codes 2/3/4/5/7; print safety snapshot id) in `anvil/services/backup/cli.py`.
- [x] T055 [US2] Add the restore wizard UI to `anvil/api/templates/operations.html`: a **3-step** `wizard-steps`/`wizard-panel` inside a `modal-dialog`, designed to complete in **≤5 clicks (SC-003)** — Step 1 review + compat badge + safety-snapshot banner (1 click to open Restore); Step 2 typed-`RESTORE` field gating Start (1 click Next); Step 3 SSE progress (1 click Start Restore). Reuse existing design-system components only.
- [x] T056 [US2] Add wizard control + restore actions to `anvil/api/static/js/backup.js` (`backupWizard` step navigation; `restore(id)` calls preview then opens wizard; typed-confirm enables Start).

**Checkpoint**: Restore works end-to-end via wizard and CLI with safety snapshot, compat gating, atomic swap, crash-safe journal recovery, and audit.

---

## Phase 5: User Story 3 — CLI Backup & Restore for Automation (Priority: P2)

**Goal**: Complete, scriptable CLI parity with the UI, with documented exit codes and audit emission.

**Independent Test**: Run `anvil-backup create`, `list`, `show`, `restore`, `status` from a shell; behavior, exit codes, and audit entries match cli-backup.md and produce the same effects as the UI.

> `create`/`list` (T039) and `restore` (T054) built in US1/US2. This phase completes parity (`show`, `status`) and locks the exit-code contract with tests.

### Tests for User Story 3 (write first, must FAIL) ⚠️

- [x] T057 [P] [US3] Write failing unit tests for the CLI argument parser + exit-code mapping (`create`/`list`/`show`/`status` happy + error paths; `--json` output shape; audit emitted in `_run()`) in `tests/unit/services/backup/test_cli.py`.

### Implementation for User Story 3

- [x] T058 [US3] Implement CLI `show` and `status` subcommands (table + `--json`; exit 5 not-found) in `anvil/services/backup/cli.py`.
- [x] T059 [US3] Audit and finalize all CLI exit codes (0/2/3/4/5/6/7/8/9), `--json` output, and audit emission across every subcommand to match cli-backup.md — make T057 pass.

**Checkpoint**: Full CLI parity with documented, tested exit codes (SC-007).

---

## Phase 6: User Story 4 — Backup Information & Monitoring In-App (Priority: P2)

**Goal**: Operations page shows a backup status card: count, total storage, latest/oldest age, quota gauge, and empty state.

**Independent Test**: With backups present, the status card shows correct count/total/ages and a quota gauge; with none, it shows the "No backups yet" empty state + "Create First Backup".

### Tests for User Story 4 (write first, must FAIL) ⚠️

- [x] T060 [P] [US4] Write failing unit tests for `BackupService.storage_status` (count/total/fraction/threshold/latest/oldest; empty-state values) in `tests/unit/services/backup/test_backup_service.py` (extend).
- [x] T061 [P] [US4] Write failing e2e test for `GET /v1/backup/status` in `tests/e2e/test_backup_endpoints.py` (extend).

### Implementation for User Story 4

- [x] T062 [US4] Implement `BackupService.storage_status` (aggregate repo + on-disk sizes → `BackupStorageStatus`) in `anvil/services/backup/backup_service.py` — make T060 pass.
- [x] T063 [US4] Add `GET /v1/backup/status` to `anvil/api/v1/backup.py` — make T061 pass.
- [x] T064 [US4] Add the backup status `section-card` to `anvil/api/templates/operations.html`: metrics rows + `meter` quota gauge + backup `grouped-list` + `empty-state` (reuse `section-card`, `meter`, `badge`, `empty-state`, `info-grid`).
- [x] T065 [US4] Add `backup.list()`/`backup.status()`/`backup.create()` rendering + toast notifications to `anvil/api/static/js/backup.js` (populate status card and list, wire "Create Backup" button + empty-state CTA).

**Checkpoint**: Operators have full in-app backup visibility.

---

## Phase 7: User Story 6 — Verification & Safe Deletion (Priority: P2)

**Goal**: On-demand integrity verification (marking corrupted backups) and safe deletion with last-backup and safety-snapshot guards, all audited.

**Independent Test**: Verify a good backup → "Valid"; tamper an archive and verify → "Corrupted" + red badge; delete the last backup without confirm → blocked; delete a safety snapshot via normal route → refused; `cleanup-safety` removes safety snapshots; each delete/cleanup writes an audit event.

### Tests for User Story 6 (write first, must FAIL) ⚠️

- [x] T066 [P] [US6] Write failing unit tests for `BackupService.verify` (valid→true; tampered→false + status `corrupted`), `delete_backup` (last-restorable guard; safety-snapshot refusal), and `cleanup_safety` in `tests/unit/services/backup/test_backup_service.py` (extend).
- [x] T067 [P] [US6] Write failing e2e tests for `POST /v1/backup/{id}/verify`, `DELETE /v1/backup/{id}` (400 last w/o confirm_last; 403 safety snapshot), **and assert `backup_delete`/`safety_snapshot_cleanup` audit events** in `tests/e2e/test_backup_endpoints.py` (extend).

### Implementation for User Story 6

- [x] T068 [US6] Implement `BackupService.verify` (stream-verify via `ArchiveReader` → `VerifyResult`; transition status to `corrupted` on mismatch) in `anvil/services/backup/backup_service.py`.
- [x] T069 [US6] Implement `BackupService.delete_backup` (refuse safety snapshots → 403/exit 9; require `confirm_last` when last restorable → 400/exit 8; else remove archive + row) and `cleanup_safety` (separate path for safety snapshots) in `anvil/services/backup/backup_service.py` — make T066 pass.
- [x] T070 [US6] Add `POST /v1/backup/{id}/verify` and `DELETE /v1/backup/{id}` (with `confirm_last` query) to `anvil/api/v1/backup.py`; **emit `backup_delete` / `safety_snapshot_cleanup` audit after success** — make T067 pass.
- [x] T071 [US6] Implement CLI `verify`, `delete`, and `cleanup-safety` subcommands (emit audit in `_run()`; exit codes 5/6/8/9) in `anvil/services/backup/cli.py`.
- [x] T072 [US6] Add Verify/Delete actions + confirm dialogs to `anvil/api/templates/operations.html` and `anvil/api/static/js/backup.js`: per-row Verify/Delete; corrupted backups get a red `badge`; delete confirm dialog shows details + last-backup warning; safety snapshots show non-deletable state.

**Checkpoint**: Backup hygiene (verify + safe delete) complete and audited.

---

## Phase 8: User Story 5 — Documentation & Guided Help (Priority: P3)

**Goal**: In-app help explaining what's backed up (and what's excluded), how restore works, storage/quota/rotation, the sensitive-data warning, and troubleshooting; contextual help in the wizard.

**Independent Test**: Click "Learn about backups" on the Operations page → help panel opens with the concepts; the restore wizard shows a contextual "?" per step.

### Implementation for User Story 5

- [x] T073 [P] [US5] Add a "Learn about backups" help panel/modal to `anvil/api/templates/operations.html` using the existing `help-box` component: what is backed up + **excluded `logs/`/`.env`**, restore process incl. safety snapshot, storage/quota/auto-rotation, **archives-contain-secrets warning (not encrypted)**, troubleshooting.
- [x] T074 [P] [US5] Add contextual help ("?") affordances to each restore-wizard step in `anvil/api/templates/operations.html` + toggle logic in `anvil/api/static/js/backup.js`.
- [x] T075 [P] [US5] Add an operator-facing backup & restore section to `README.md` (and/or `docs/`) covering UI + `anvil-backup` CLI usage, config env vars (incl. retention), and the not-encrypted sensitive-data note.

**Checkpoint**: Feature is self-documenting in-app and in repo docs.

---

## Phase 9: SSE Progress Streaming (Cross-Cutting — serves US1 & US2)

**Purpose**: Live progress for backup and restore via SSE, consumed by the UI. Built after the queue-producing operations exist.

### Tests (write first, must FAIL) ⚠️

- [x] T076 [P] Write failing e2e test for `GET /v1/backup/stream/{id}` (emits `progress` then `complete`; `error` for unknown id; heartbeat shape) in `tests/e2e/test_backup_endpoints.py` (extend).

### Implementation

- [x] T077 Implement `BackupService.stream_for(operation_id)` exposing the per-operation `asyncio.Queue`; ensure `create_backup`/`restore` push `ProgressEvent`s thread-safely (`loop.call_soon_threadsafe`) in `anvil/services/backup/backup_service.py`.
- [x] T078 Add `GET /v1/backup/stream/{id}` SSE endpoint (`StreamingResponse`, `text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`; 30s heartbeat; close on `complete`/`error`) mirroring `anvil/api/v1/training.py` in `anvil/api/v1/backup.py` — make T076 pass.
- [x] T079 Implement `BackupSession` SSE client (modeled on `anvil/api/static/js/sse.js`, targeting `/v1/backup/stream/{id}`; `onprogress`/`oncomplete`/`onerror`) in `anvil/api/static/js/backup.js`; wire backup-create and restore wizard to live progress.
- [x] T080 Link `backup.js` from `anvil/api/templates/operations.html` (script include) and confirm it loads on the Operations page.

**Checkpoint**: Live progress streams for both backup and restore in the UI.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, docs, and merge-gate compliance.

- [x] T081 [P] Add an ADR for the backup architecture (WAL-safe snapshot, atomic restore + crash-safe journal, safety snapshot, quota auto-rotation, route-layer audit, stdlib-only, no encryption) in `docs/vault/Decisions/` per Constitution governance.
- [x] T082 [P] Add a backup/restore session log and discovery notes to `docs/vault/Sessions/`; ensure wikilinks resolve.
- [x] T083 Run `make typecheck` (mypy --strict) and resolve any typing issues across all new files — no suppressions.
- [x] T084 Run `make lint` and `make format`; fix ruff/black/isort/pylint findings (NumPy docstrings on every module/class/method).
- [x] T085 [P] **UX compliance gate**: run `make ux-lint` on changed UI/template/CSS (`operations.html`, `backup.js`) — must report GATE: PASS.
- [x] T086 [P] **AI UX review** (UI feature): `make ux-review FILES=anvil/api/templates/operations.html` with `UX_API_KEY` set; address S4/S3 findings.
- [x] T087 Run `make test` with coverage; ensure all backup tests pass and coverage ratchets up (Article IV).
- [x] T088 Run `make vault-audit` — must report 0 errors before committing vault changes.
- [x] T089 Execute the `quickstart.md` manual smoke (`anvil-backup create` → change state → `restore` → verify reverted; simulate interrupted restore → confirm startup recovery; fill quota → confirm auto-rotation) and confirm SC-001–SC-007 hold.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**.
- **US1 (Phase 3)**: Depends on Foundational. MVP.
- **US2 (Phase 4)**: Depends on Foundational + US1 (reuses `create_backup` for the safety snapshot + `ArchiveWriter`).
- **US3 (Phase 5)**: Depends on US1 + US2 (completes CLI parity).
- **US4 (Phase 6)**: Depends on Foundational (+ US1 to have backups to display). Independent of US2/US3.
- **US6 (Phase 7)**: Depends on Foundational + US1 (needs archives + manifest). Independent of US2/US3/US4.
- **US5 (Phase 8)**: Depends on US2 UI existing (documents the wizard). P3.
- **SSE (Phase 9)**: Depends on US1 + US2 (queue producers must exist).
- **Polish (Phase 10)**: Depends on all targeted stories complete.

### Within Each User Story

- Tests written FIRST and must FAIL (Article IV) → Types/models → Service → Endpoint/CLI → UI → Integration.

### Parallel Opportunities

- **Phase 2**: enums (T005–T007), audit-enum extensions (T008–T009), all value types (T010–T017), repo tests (T018), and `BackupLock` (T023) are fully parallel `[P]`.
- **Within a story**: all test tasks marked `[P]` run together (e.g. US1 T027–T031; US2 T040–T045).
- **Across stories after Foundational**: US4 (Phase 6) and US6 (Phase 7) can proceed in parallel with US2/US3 if staffed, coordinating shared edits to `operations.html`/`backup.js`/`backup_service.py`/`anvil/api/v1/backup.py`.

---

## Parallel Example: Phase 2 Foundational Types

```bash
# Enums, audit extensions, and value types are independent files — launch together:
Task: "Create BackupStatus in anvil/services/backup/backup_status.py"
Task: "Create BackupOperationType in anvil/services/backup/backup_operation_type.py"
Task: "Create SchemaCompatibility in anvil/services/backup/schema_compatibility.py"
Task: "Add BACKUP_* members to anvil/services/governance/audit_action.py"
Task: "Add BACKUP member to anvil/services/governance/audit_target_type.py"
Task: "Create the 8 Pydantic value/result type files (ManifestEntry … CreateBackupResult)"
```

## Parallel Example: User Story 1 Tests

```bash
# Write all US1 tests first (they must FAIL):
Task: "SnapshotPlanner tests (incl. logs/.env exclusion) in tests/unit/services/backup/test_snapshot_planner.py"
Task: "RetentionPolicy tests in tests/unit/services/backup/test_retention_policy.py"
Task: "ArchiveWriter tests in tests/unit/services/backup/test_archive_writer.py"
Task: "BackupService.create_backup tests in tests/unit/services/backup/test_backup_service.py"
Task: "create/list/409/audit e2e tests in tests/e2e/test_backup_endpoints.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1).
2. **STOP & VALIDATE**: create + list backups via API and CLI; confirm a valid archive on disk (no `logs/`/`.env`), audit event written, auto-rotation works.
3. Demo the one-click backup MVP.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → test → demo (MVP: backups exist, audited, rotated).
3. US2 → test → demo (safe restore + crash-safe journal — the killer feature).
4. US3 (CLI parity) + US4 (monitoring) + US6 (verify/delete) → test → demo.
5. US5 (docs) + SSE polish → final.
6. Phase 10 gates → merge.

### Parallel Team Strategy

After Foundational completes: Dev A → US1→US2 (core), Dev B → US4 (monitoring), Dev C → US6 (verify/delete). SSE (Phase 9) + US5 (docs) fold in once US1/US2 land. Coordinate shared edits to `backup_service.py`, `anvil/api/v1/backup.py`, `operations.html`, and `backup.js`.

---

## Notes

- `[P]` = different files, no incomplete-task dependencies.
- `[Story]` label maps each task to its spec.md user story for traceability.
- Every test task is written to FAIL before its implementation task (Constitution Article IV).
- All blocking I/O (`tarfile`/`hashlib`/`shutil`/`sqlite3.backup()`) runs via `asyncio.to_thread` (Article V).
- **Audit (FR-031) is emitted at the route/CLI layer via the session-bound `workbench.audit`, never inside the process-lifetime `BackupService`** (research R11).
- Relative imports only inside `anvil/`; one class per file; Pydantic `BaseModel` for all structured types; enums over magic strings.
- Migrations live at `anvil/_resources/migrations/` (NOT under `db/`).
- Commit only when explicitly requested.

### Task Count Summary

| Phase | Story | Tasks |
|---|---|---|
| 1 Setup | — | 4 (T001–T004) |
| 2 Foundational | — | 22 (T005–T026) |
| 3 US1 (P1) 🎯 | One-click backup | 13 (T027–T039) |
| 4 US2 (P1) | Guided restore | 17 (T040–T056) |
| 5 US3 (P2) | CLI parity | 3 (T057–T059) |
| 6 US4 (P2) | Monitoring | 6 (T060–T065) |
| 7 US6 (P2) | Verify & safe delete | 7 (T066–T072) |
| 8 US5 (P3) | Documentation | 3 (T073–T075) |
| 9 SSE | cross-cutting (US1/US2) | 5 (T076–T080) |
| 10 Polish | — | 9 (T081–T089) |
| **Total** | | **89** |

**Suggested MVP scope**: Phases 1–3 (US1) = 39 tasks → one-click full backup (audited, auto-rotating, `logs/`/`.env` excluded) via UI + CLI.
