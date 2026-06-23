# Feature Specification: Deployment Backup & Restore

**Feature Branch**: `026-deployment-backup-restore`  
**Created**: 2026-06-21  
**Status**: Draft  
**Input**: User description: "backup & restore - of complete anvil deployment state -- with easy to use documentation, in app information, ops buttons, wizards, etc, -- database and file system snap shooting"

## Clarifications

### Session 2026-06-21

- Q: Should backup archives be encrypted at rest (they contain the full DB incl. secrets)? → A: No encryption in v1; rely on filesystem permissions (same trust boundary as live `data/`) and document that archives contain sensitive data.
- Q: How should the system recover if the process crashes mid-restore (half-applied swap, orphan `.bak` dirs)? → A: Write a restore journal/marker before swapping; on startup detect an interrupted restore and roll back from the `.bak` sides, or surface a clear recovery prompt pointing to the pre-restore safety snapshot.
- Q: Should backup/restore operations be written to the existing audit log? → A: Yes — emit `audit_event` entries for backup create, restore, delete, and safety-snapshot cleanup, in addition to the `backup_operations` history table.
- Q: What happens when the storage quota is reached — block, or auto-rotate? → A: Auto-rotation — when a new backup would exceed the quota, automatically delete the oldest non-safety backups to make room, governed by a configurable retention policy (max count and/or max age). Only block if space is still insufficient after rotation.
- Q: What exactly is included in a "complete deployment state" snapshot (logs? `.env`?)? → A: Data + experiment state only — `data/anvil-state.db`, `data/models/`, `data/datasets/`, `data/storage/`, `data/content/`, `mlruns/`. Exclude `logs/` (diagnostic) and `.env` (environment-specific config/secrets that should not be overwritten across environments).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One-Click Full Backup via Ops Dashboard (Priority: P1)

As an anvil operator, I want to create a complete snapshot of the entire deployment state (database + all file stores) with a single click from the Operations dashboard, so that I can safely perform upgrades, experiments, or maintenance knowing I can restore the current state.

**Why this priority**: This is the core value proposition — backup & restore of complete deployment state. Without this, the feature doesn't exist. Everything else (wizards, docs, scheduling) enhances this core capability.

**Independent Test**: Can be fully tested by clicking the "Create Backup" button on the Operations page and verifying a backup archive appears in the backup storage directory with the correct timestamp and contents.

**Acceptance Scenarios**:

1. **Given** the anvil deployment is running with data in the database, trained models, uploaded datasets, and MLflow experiments, **When** the operator clicks "Create Backup" on the Operations page, **Then** a backup archive is created containing a database snapshot and filesystem snapshots, and a success notification appears.
2. **Given** a previous backup was created, **When** the operator views the Operations page backup section, **Then** the backup appears in a list showing its timestamp, size, and status (completed/failed).
3. **Given** the backup creation fails mid-process (e.g., disk full), **When** the failure occurs, **Then** the partial backup is cleaned up, an error notification appears, and no corrupted backup state remains.

---

### User Story 2 - Guided Restore from Backup via Wizard (Priority: P1)

As an anvil operator, I want to restore the full deployment state from a previously created backup using a step-by-step wizard, so that I can recover from data corruption, failed upgrades, or migrate to a new environment.

**Why this priority**: Restore is the companion to backup — without restore, backup has no value. The wizard reduces risk by showing the operator exactly what will happen before any data is overwritten.

**Independent Test**: Can be fully tested by creating a backup, making a known change to the deployment (e.g., adding a dataset), then using the restore wizard to revert and verifying the change is undone.

**Acceptance Scenarios**:

1. **Given** one or more backups exist, **When** the operator clicks "Restore" next to a backup entry, **Then** a restore wizard opens showing:
   - Summary of backup contents (database size, files included, total size, timestamp, deployment version)
   - Schema compatibility check result (green/pass or red/block)
   - A warning that the current deployment state will be auto-backed up before restore proceeds.
2. **Given** the restore wizard's summary step shows all details, **When** the operator reaches the confirmation step, **Then** they must type the word "RESTORE" into a text field to enable the "Start Restore" button (confirmation cannot be bypassed via `--force` in the CLI — `--force` only skips the service pause prompt, not the typed confirmation).
3. **Given** the operator has confirmed the restore, **When** the system begins, **Then** it first automatically creates a backup of the current deployment state (a "pre-restore safety snapshot"), then proceeds with the restore.
4. **Given** the pre-restore safety snapshot is complete, **When** the system applies the selected backup, **Then** it uses an atomic swap pattern: restore to a temporary directory, verify integrity, then swap into place. A progress indicator is shown throughout.
5. **Given** a restore completes successfully, **Then** a confirmation message appears with a prompt to restart the application, including the ID of the auto-created pre-restore safety snapshot so the operator can undo if needed.
6. **Given** a restore fails (e.g., corrupted backup archive), **When** the error occurs, **Then** the original deployment state is preserved intact (partial files are never left in place), the pre-restore safety snapshot is retained, and an error notification with recovery instructions is shown.

---

### User Story 3 - CLI Backup & Restore for Automation (Priority: P2)

As a DevOps engineer or power user, I want to create backups and perform restores from the command line, so that I can incorporate backup/restore into automated scripts, CI/CD pipelines, and scheduled maintenance windows.

**Why this priority**: CLI provides automation capability that the web UI cannot. This unlocks scheduled backups via cron, pre-upgrade backup hooks, and remote restore workflows. P2 because most operators will start with the UI.

**Independent Test**: Can be fully tested by running `anvil backup create` from the command line, confirming a backup archive is created, then running `anvil backup list` to see it and `anvil backup restore <backup-id>` to restore it.

**Acceptance Scenarios**:

1. **Given** the CLI tool is installed, **When** the operator runs `anvil backup create`, **Then** a backup is created identically to the UI one-click backup, and the command exits with a success message and backup identifier.
2. **Given** backups exist, **When** the operator runs `anvil backup list`, **Then** all backups are shown with timestamp, size, and status.
3. **Given** the operator wants to restore, **When** they run `anvil backup restore <backup-id>`, **Then** a two-step confirmation is required: first a safety snapshot is auto-created, then the operator must type "RESTORE" to proceed. With `--force`, the service-pause confirmation is skipped but typed confirmation is still required.
4. **Given** a restore via CLI, **When** it completes, **Then** the deployment state matches the backup and a summary is printed.

---

### User Story 4 - Backup Information and Monitoring In-App (Priority: P2)

As an anvil operator, I want to see comprehensive backup information directly in the Operations dashboard — latest backup age, total storage used by backups, backup health status — so that I can monitor backup hygiene without leaving the UI.

**Why this priority**: Good operations practice requires visibility into backup status. If backups are stale, failing, or consuming too much storage, the operator needs to know immediately. P2 because the feature still works without monitoring, but good ops requires it.

**Independent Test**: Can be fully tested by creating multiple backups, then viewing the Operations page to confirm backup metrics update correctly (count, total size, latest backup age).

**Acceptance Scenarios**:

1. **Given** backups exist, **When** the operator navigates to the Operations page, **Then** a backup status card shows: number of backups, total storage used, most recent backup timestamp, and oldest backup timestamp.
2. **Given** no backups exist, **When** the operator views the Operations page, **Then** the backup section shows a "No backups yet" empty state with a prominent "Create First Backup" button.
3. **Given** backup storage exceeds a configurable threshold, **When** the operator views the Operations page, **Then** a warning indicator is displayed next to the backup storage usage.

---

### User Story 5 - Getting Started Documentation and Guided Tour (Priority: P3)

As a new anvil operator, I want built-in documentation explaining the backup/restore workflow — what gets backed up, how the wizard works, troubleshooting tips — so that I can confidently use the feature without external references.

**Why this priority**: Documentation reduces support burden and operator errors. P3 because the feature works without it, but well-documented ops features reduce risk in production.

**Independent Test**: Can be fully tested by navigating to a help/documentation section within the app and confirming all backup/restore concepts are explained with actionable guidance.

**Acceptance Scenarios**:

1. **Given** the operator opens the Operations page, **When** they click a "Learn about backups" link or info icon, **Then** a help panel or modal opens explaining what data is backed up, how restore works, and storage considerations.
2. **Given** the operator is in the restore wizard, **When** they see a "Help" or "?" icon, **Then** clicking it shows contextual guidance for the current wizard step.

---

### User Story 6 - Backup Management: Verification and Safe Deletion (Priority: P2)

As an anvil operator, I want to verify that existing backups are intact and safely delete old ones without risk, so that I can maintain backup hygiene and free up storage space with confidence.

**Why this priority**: Backup management is essential for responsible operations. An operator needs to trust their backups are valid (not just at restore time) and needs safe deletion workflows that prevent accidentally losing all recovery options. P2 because the core backup/restore cycle works without it, but responsible ops requires it.

**Independent Test**: Can be fully tested by creating a backup, running a "Verify" action that confirms checksum integrity, then deleting a backup with confirmation and verifying the system warns when attempting to delete the last available backup.

**Acceptance Scenarios**:

1. **Given** an existing backup, **When** the operator clicks "Verify" on that backup entry, **Then** the system recomputes checksums for every file in the archive, compares against the manifest, and reports "Valid" or "Corrupted" with details.
2. **Given** one or more backups exist, **When** the operator clicks "Delete" on a backup entry, **Then** a confirmation dialog appears showing the backup details (timestamp, size, age). If this is the last restorable backup, a prominent warning is shown: "This is the only remaining backup. Deleting it leaves no recovery option."
3. **Given** the operator confirms deletion, **Then** the backup archive is removed and the backup list updates immediately.

---

### Edge Cases

- What happens when the database is locked or a write is in progress during backup? → Backup uses SQLite WAL checkpoint + file copy to ensure a consistent snapshot without locking the running app.
- How does the system handle a corrupted backup archive during restore? → Restore validates the archive checksum before applying; failure preserves current state AND the auto-created pre-restore safety snapshot remains available as a fallback.
- What happens when disk space is insufficient for backup creation? → Pre-flight check estimates required space vs. available. If insufficient, the backup is blocked with a clear message showing how much space is needed and how to free it.
- What happens when disk space is insufficient for restore? → Pre-flight check verifies there is enough space for BOTH the pre-restore safety snapshot AND the restored data before proceeding.
- How does restore interact with a running application? → Restore auto-creates a pre-restore safety snapshot, pauses non-essential services, performs an atomic temp-directory restore, then swaps into place. If swap fails, the original state remains untouched.
- What happens to MLflow experiments that reference now-restored data? → MLflow tracking data is included in the filesystem snapshot; restored experiments reference consistent state.
- How does the system handle concurrent backup operations? → Only one backup or restore operation may run at a time; a queue/lock prevents concurrent operations.
- What if someone clicks "Create Backup" twice quickly? → Each backup gets a unique timestamp-based filename. Backups are immutable (never modified after creation). Two clicks produce two distinct backups — no overwrite risk.
- Can an operator accidentally delete all backups? → Yes, but the deletion flow warns prominently if deleting the last restorable backup and requires explicit confirmation. The pre-restore safety snapshot is NOT deletable through the normal backup list (it has a "safety snapshot" flag and requires separate cleanup).
- What if the operator restores from a backup created by an older deployment version? → The backup manifest stores the deployment version and database schema version. The restore wizard compares these against the current app version and shows a compatibility check: green (compatible), yellow (minor version drift — warning), or red (schema mismatch — blocked).
- What if a backup's checksums don't match on verify? → The backup is marked "Corrupted" in the list. The operator can still attempt a restore (with additional warnings) but the default path guides them toward creating a fresh backup instead.
- What happens when the storage quota for backups is exceeded? → When a new backup would exceed the quota, the system auto-rotates: it deletes the oldest non-safety backups (per the configured retention policy) to make room, then proceeds. Pre-restore safety snapshots are never auto-deleted. If, after rotating all eligible non-safety backups, there is still insufficient room, creation is blocked with a clear message. A visible quota gauge on the backup status card shows usage level at all times, and auto-rotation deletions are recorded in the audit log.
- What if the pre-restore safety snapshot fails (disk full)? → The restore is aborted entirely. The operator is shown the error and advised to free space or delete old backups before retrying.
- What if the process crashes or is killed mid-restore (partial swap)? → A restore journal/marker is written before any swap begins. On the next startup the system detects the interrupted restore and rolls back from the moved-aside `.bak` copies; if the `.bak` copies are unavailable, it surfaces a clear recovery prompt directing the operator to restore the pre-restore safety snapshot. The marker is removed only after a clean, fully-verified completion.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow creating a full deployment backup containing a consistent database snapshot and all persistent filesystem state: `data/anvil-state.db`, `data/models/`, `data/datasets/`, `data/storage/`, `data/content/`, and MLflow tracking data (`mlruns/` incl. `mlruns/mlflow.db`). The backup MUST exclude the `logs/` directory (diagnostic only) and the `.env`/environment configuration (environment-specific settings and secrets that must not be overwritten across environments).
- **FR-002**: System MUST provide a one-click "Create Backup" button in the Operations web UI that initiates a full backup with a single action.
- **FR-003**: System MUST provide a step-by-step restore wizard in the Operations web UI that guides the operator through selecting a backup, reviewing its contents, confirming, and executing the restore.
- **FR-004**: System MUST provide a CLI command (`anvil backup create`) to initiate a full backup from the command line.
- **FR-005**: System MUST provide a CLI command (`anvil backup list`) to enumerate existing backups with metadata.
- **FR-006**: System MUST provide a CLI command (`anvil backup restore <backup-id>`) to restore from a specified backup, with a confirmation prompt (bypassable with `--force`).
- **FR-007**: System MUST store backup archives in a configurable location (default: `data/backups/`).
- **FR-008**: Each backup MUST contain a manifest file describing its contents, timestamp, deployment version, and checksums for integrity verification.
- **FR-009**: System MUST validate backup archive integrity (checksum verification) before proceeding with a restore.
- **FR-010**: System MUST display backup history in the Operations web UI, showing timestamp, total size, and status for each backup.
- **FR-011**: System MUST display a backup status card on the Operations page showing: backup count, total storage used, and latest backup age.
- **FR-012**: System MUST prevent concurrent backup or restore operations (queue or lock mechanism).
- **FR-013**: System MUST clean up partial/failed backup artifacts automatically.
- **FR-014**: System MUST preserve the current deployment state if a restore operation fails (no partial state overwrite).
- **FR-015**: System MUST perform a pre-flight disk space check before backup creation and warn the operator if insufficient space is available.
- **FR-016**: System MUST include in-app documentation accessible from the backup UI explaining: what data is backed up, the restore process, storage considerations, and troubleshooting steps.
- **FR-017**: System MUST include a "Learn about backups" informational link/panel on the Operations page backup section providing contextual help.
- **FR-018**: System MUST automatically create a backup of the current deployment state ("pre-restore safety snapshot") before performing any restore operation.
- **FR-019**: Pre-restore safety snapshots MUST be clearly labeled and distinguishable from manually created backups in the backup list (e.g., "Pre-restore snapshot — 2026-06-21 14:30:00").
- **FR-020**: Pre-restore safety snapshots MUST NOT be deletable through the standard backup deletion flow. They require a separate, explicitly labeled cleanup action.
- **FR-021**: The restore wizard MUST require the operator to type the word "RESTORE" into a confirmation field to proceed. A simple button click is insufficient.
- **FR-022**: Each backup archive MUST use a unique filename (timestamp-based) and MUST be immutable after creation — no existing backup file may be modified or overwritten.
- **FR-023**: The system MUST perform a schema-version compatibility check before restore: compare the deployment version and database schema version in the backup manifest against the current app version. Incompatible backups MUST be blocked from restore with a clear explanation and upgrade guidance.
- **FR-024**: Restore operations MUST use an atomic swap pattern: restore to a temporary directory, verify integrity (checksum comparison of every restored file against the manifest), then swap into the production location. If verification fails at any point, the production data remains untouched.
- **FR-025**: The system MUST provide an on-demand "Verify Backup" action (in both UI and CLI) that recomputes checksums for every file in a backup archive and compares them against the manifest, reporting "Valid" or "Corrupted".
- **FR-026**: Backups detected as "Corrupted" by verification MUST be visually distinguished in the backup list (e.g., red badge, different icon).
- **FR-027**: The system MUST enforce a configurable storage quota for backup archives (default: 10GB). When a new backup would exceed the quota, the system MUST auto-rotate (see FR-032) by deleting the oldest non-safety backups to make room before proceeding. Only if space remains insufficient after rotating all eligible non-safety backups MUST creation be blocked, with a clear message showing usage and guidance.
- **FR-028**: Backup deletion MUST show a confirmation dialog with the backup details (timestamp, size, age). If the backup being deleted is the last remaining restorable backup, the dialog MUST prominently warn: "This is the only remaining backup. Deleting it leaves no recovery option."
- **FR-029**: The backup status card on the Operations page MUST show a visual quota gauge indicating current storage usage relative to the configured quota.
- **FR-030**: The system MUST write a restore journal/marker before beginning the file-swap phase of a restore, recording the roots being swapped and the pre-restore safety snapshot id. On application startup, if a restore journal is present (indicating an interrupted restore), the system MUST recover by rolling back from the moved-aside `.bak` copies; if those are unavailable, it MUST surface a clear recovery prompt referencing the pre-restore safety snapshot. The journal MUST be removed only after a clean, fully-verified restore completion.
- **FR-031**: The system MUST emit an audit-log entry (via the existing audit infrastructure) for each backup creation, restore, backup deletion, and safety-snapshot cleanup, capturing the operation type, target backup id, and timestamp — in addition to recording the operation in the `backup_operations` history table.
- **FR-032**: The system MUST support a configurable retention policy (max backup count and/or max age) that governs auto-rotation. When auto-rotation runs (triggered by FR-027 or by retention limits), the system MUST delete the oldest **non-safety** backups first, MUST NEVER auto-delete pre-restore safety snapshots, and MUST record each auto-deletion in the audit log (FR-031). Retention limits are configurable with sensible defaults.

### Key Entities *(include if feature involves data)*

- **BackupArchive**: A complete point-in-time snapshot of the deployment. Contains a database dump, filesystem archives, and a manifest. Attributes: unique ID, timestamp, total size, status (creating/completed/failed), manifest checksum, deployment version.
- **BackupManifest**: Metadata file within each backup archive describing its structure. Records: backup timestamp, included paths, file checksums, database schema version, deployment version, archive size.
- **BackupStorage**: The storage location for backup archives. Configurable path (default: `data/backups/`). Can be local filesystem. Each backup is a single compressed archive file (e.g., `.tar.gz` or `.zip`).
- **BackupOperation**: A record of a backup or restore operation in progress or completed. Tracks: operation type (backup/restore), status, started_at, completed_at, error_message, backup_id.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can create a full deployment backup in under 2 clicks from the Operations web UI (one click for "Create Backup", one confirmation).
- **SC-002**: A full backup of a deployment with a 100MB database and 500MB of file storage completes in under 30 seconds on local storage.
- **SC-003**: An operator can restore a deployment to a previous state using the guided wizard in under 5 clicks with clear indicators at each step.
- **SC-004**: Backup listing and status display on the Operations page loads in under 1 second regardless of backup count.
- **SC-005**: Restore from a valid backup archive succeeds 100% of the time with the deployment matching the backed-up state exactly (verified by checksum comparison post-restore).
- **SC-006**: A failed restore never results in data loss — the current state is always preserved.
- **SC-007**: All backup/restore operations are available via both web UI and CLI without feature gaps.

## Assumptions

- Backup and restore cover the entire deployment state — partial/selective restore (e.g., database only, or a single model file) is out of scope for v1.
- Backups are stored as single compressed archive files on the local filesystem; cloud/remote storage destinations are out of scope for v1.
- Backup scheduling (automated periodic *creation*) is out of scope for v1; all backups are initiated manually via UI buttons or CLI commands. (Note: auto-*rotation* of existing backups on quota/retention limits IS in scope — see FR-027/FR-032 — and is distinct from scheduled creation.)
- The database uses SQLite in WAL mode, which allows safe file-level snapshotting via a checkpoint + file copy approach.
- MLflow tracking data (MLflow SQLite database at `mlruns/mlflow.db` and artifact files under `mlruns/`) is included in the filesystem snapshot portion of the backup.
- The deployment runs on a single host (not distributed); distributed/clustered deployment backup is out of scope for v1.
- Backup archives may be large (multiple GB); the system provides size estimates before backup and restore operations.
- The operator running backup/restore has filesystem-level access to the deployment directories; no special permission model is needed within anvil.
- Backup archives are NOT encrypted at rest in v1. They contain the full deployment state including sensitive data (e.g., the API key and any secrets in the database), so they inherit the same trust boundary and filesystem permissions as the live `data/` directory. In-app documentation MUST warn operators that archives contain sensitive data and should be stored and transferred securely. Encryption at rest is deferred to a future version.
- The Operations page already exists and a backup section can be added as a new card/panel within its layout.
- Restore requires brief downtime of the application server (web + MLflow) to ensure data consistency during file replacement.
- The existing `audit_event` infrastructure (from responsible-data-governance) is reused for backup/restore audit entries; no new audit subsystem is built.
- A backup captures persistent data + experiment state only. The `logs/` directory and `.env`/environment configuration are deliberately excluded; restoring to a new environment relies on that environment already having its own `.env`/config. This exclusion is documented in the in-app help.
