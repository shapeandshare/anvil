# Research: Recovery Strategy Options — Data-Safe Startup Recovery

**Spec**: [[Specs/061-resilient-startup-recovery/spec|061 Resilient Startup & Data-Safe Database Recovery]]
**Created**: 2026-06-29
**Status**: Draft

This document captures the design-options analysis that fed the spec's requirements: detection strategies, non-destructive remediation options, the startup-sequencing fix, the auto-vs-confirm boundary, the health-signal question, the ranked recommendation, and the honest failure modes where even the recommended strategy can still lose data.

## Governing principle

> **Preserve bytes first, decide second.** Without an external source of truth, the only universal guarantee we can offer is that we never destroy or overwrite the only known copy of user state. Everything else (restore, reset, repair, salvage) is a *decision made on top of* preserved bytes.

The most dangerous mistake to avoid: **treating broken-but-existing state as "empty / safe to reset."** This is why freshness is decided by filesystem provenance, never by table emptiness.

---

## 1. Detection — how to classify the DB at startup

A single check is insufficient (the incident proves a stamped `alembic_version` can lie). Use a **state classifier** with read-only checks.

| State | How detected | Auto-action allowed |
|---|---|---|
| `fresh` | DB file absent before startup **and** no `-wal`/`-shm` sidecars | ✅ init + migrate |
| `healthy` | integrity probe passes **and** all expected tables present **and** Alembic revision known/consistent | ✅ migrate/verify |
| `desynced` | integrity passes but expected tables missing / revision inconsistent (← *the incident*) | ❌ snapshot → maintenance |
| `corrupt` | SQLite can't open/read; `quick_check`/`integrity_check` fails; invalid sidecar state | ❌ snapshot → maintenance |
| `restore_in_progress` | `RestoreJournal` marker present | ✅ journal rollback first |

### Detection options weighed

**D1 — Revision-only (`alembic_version` + `PRAGMA user_version`)**
- **Pros**: cheap, already present.
- **Cons**: not trustworthy alone — exactly the failure we hit. Also, `get_schema_version()` returns `0` on *any* read error, conflating "fresh" with "corrupt".
- **Guarantee**: low.
- **Verdict**: necessary signal, never sufficient on its own.

**D2 — Expected-table verification at boot (`verify_table_integrity()`)**
- **Pros**: deterministic, cheap, catches schema desync ("the revision lies") directly.
- **Cons**: does not detect low-level/physical corruption.
- **Guarantee**: strong for desync.
- **Verdict**: **mandatory** — promote the existing CLI-only check to a startup gate.

**D3 — `PRAGMA quick_check` / `integrity_check`**
- **Pros**: detects many SQLite-level corruptions. `quick_check` is fast; `integrity_check` is exhaustive.
- **Cons**: `integrity_check` is slower on large DBs; physical-consistency signal, not logical-schema truth.
- **Guarantee**: strong for physical integrity.
- **Verdict**: use `quick_check` every boot, escalate to `integrity_check` on failure or detected mismatch. (For this app the DB is small metadata, so a full `integrity_check` at boot is also acceptable.)

**Recommended detection = D2 + D3 + provenance**, combined into the classifier (FR-001…FR-005). Decide `fresh` by provenance only; never decide `fresh` from a read error.

---

## 2. Non-destructive remediation options (pros/cons)

### A. In-place self-heal of missing tables (`metadata.create_all`, or re-stamp-then-upgrade)
- **What**: mutate the live DB to recreate/reinterpret missing schema.
- **Pros**: fastest path to green when the DB was merely uninitialized.
- **Cons**: dangerous in an Alembic-managed system — can create a **hybrid schema** that matches neither a clean migration nor any known revision; `create_all` bypasses migration history; **masks real corruption** and destroys forensic signal.
- **Data-safety**: weak in-place (preserves bytes only if snapshotted first).
- **Effort**: small.
- **Composes**: poorly as a default; acceptable only on a clearly-`fresh` DB, or on a quarantined copy.
- **Verdict**: ❌ not the default recovery path.

### B. Quarantine-not-delete, then start fresh
- **What**: move the suspect `.db`/`-wal`/`-shm` aside to a timestamped quarantine, init a new DB.
- **Pros**: preserves original bytes; restores availability quickly; simple mental model.
- **Cons**: app now runs on empty metadata — user state is preserved but not *logically* recovered until a restore/repair.
- **Data-safety**: strong byte-preservation, weak continuity.
- **Effort**: short.
- **Composes**: well — quarantine artifacts live beside backups.
- **Verdict**: ✅ good **operator-approved** fallback (FR-016), not a silent default.

### C. Auto-snapshot before any repair
- **What**: capture the suspect artifacts before touching anything.
- **Pros**: strictly improves safety; enables later restore, forensics, salvage.
- **Cons**: uses disk; snapshotting a corrupt DB doesn't make it valid.
- **Data-safety**: strong preservation of the last observed on-disk state.
- **Effort**: short.
- **Composes**: excellent with the existing `BackupService`/manifest.
- **Verdict**: ✅ **default, always** (FR-006).

### D. Boot into maintenance / recovery mode
- **What**: bind the port, serve a recovery UI/API, suppress normal routes + best-effort startup work.
- **Pros**: solves the "blank crash" problem; keeps the safe path reachable without shell access; great UX.
- **Cons**: another runtime mode to test; must isolate the bad DB from normal handlers.
- **Data-safety**: strong if read-only until an explicit action.
- **Effort**: medium.
- **Composes**: excellent with `BackupService` + `RestoreJournal` + the existing operations dashboard.
- **Verdict**: ✅ **best default UX + safety tradeoff** (FR-010…FR-013).

### E. Auto-restore latest good backup
- **What**: on detected corruption, automatically restore the newest compatible backup (after snapshotting the corrupt state).
- **Pros**: fastest *unattended* recovery; good for appliance-style deployments.
- **Cons**: it is still a **rollback to backup time** — recent committed data is lost; can **silently mask a recurring defect** by rolling back on every boot.
- **Data-safety**: preserves corrupt bytes if snapshotted first, but logical data rolls back.
- **Effort**: medium.
- **Composes**: very well with current restore engine.
- **Verdict**: ⚠️ **opt-in policy only** (FR-018), never the universal default.

### F. WAL checkpoint / SQLite `.recover` / salvage
- **What**: low-level salvage of recent or partially-corrupt data.
- **Pros**: may recover more than the latest backup.
- **Cons**: expert-only; partial results; easy to make worse if run on live files.
- **Data-safety**: acceptable only on **copies**, never originals.
- **Effort**: large.
- **Composes**: better as a CLI/support tool than startup behavior.
- **Verdict**: ⚠️ advanced, copy-only CLI (FR-023); not a pit-of-success default.

---

## 3. Startup-sequencing fix

The incident was amplified by ordering: DB-dependent best-effort steps (`_seed_license_catalog`, `_bootstrap_demo_data`) ran **before** `_init_backup_service()` (where journal recovery lives), and a missing table in a best-effort step killed the whole boot.

**Recommended order (FR-019):**
1. minimal filesystem / bootstrap
2. `RestoreJournal.recover()` — the one automatic write-path that already has a safety model
3. DB classifier (read-only)
4. branch:
   - `fresh` → init + migrate
   - `healthy` → migrate / verify, continue
   - `desynced` / `corrupt` → snapshot, enter maintenance mode, stop normal startup
5. only after the DB is declared writable → MLflow, tracking reconcile, license seeding, demo bootstrap, model warmup
6. best-effort steps catch a broad exception set and degrade their feature — they never abort the process (FR-020).

---

## 4. Pit of success — what is automatic vs. confirmed

**Automatic (non-destructive or clearly reversible):**
- interrupted-restore rollback via `RestoreJournal`
- fresh-DB initialization when the DB path genuinely did not exist
- normal migrations on a healthy existing DB
- safety-snapshot creation before any operator-triggered repair

**Explicit confirmation required (rolls back / replaces / reinterprets user state):**
- restore from backup
- quarantine + reset
- in-place repair (`stamp`, `create_all`, manual migration fiddling)
- SQLite salvage

This is the right line because **only the first group is non-destructive or clearly reversible**. Auto-restore is convenient but is still a rollback, so it stays opt-in.

---

## 5. Honest health signal — liveness vs. readiness

Today `GET /v1/health` returns `{"status":"healthy"}` unconditionally, so Docker/orchestrators get **false positives** even when the DB is unreachable.

- **Liveness** (`GET /v1/health`): process/event-loop is up; returns 200 even in maintenance mode (so the recovery UI stays reachable).
- **Readiness** (`GET /v1/ready`): app DB is writable and startup completed; returns 503 in maintenance mode or on DB failure, with the detected cause.

**Tradeoff**: if a container healthcheck is wired to *readiness* and returns 503, the orchestrator may crash-loop the container and the operator never reaches the recovery UI. So: **healthcheck → liveness** (keep the container alive for recovery); **traffic gating / load balancer → readiness**. Documented in FR-022.

---

## 6. Ranked options

1. **Recommended composite** — classifier + auto-snapshot + maintenance mode + operator-gated restore/reset. *(best safety + UX, composes with existing infra)*
2. **Quarantine + reset after snapshot** — good fallback for quick availability without deletion.
3. **Auto-restore latest verified backup** — useful only as explicit opt-in unattended policy.
4. **SQLite salvage on copies** — valuable support tool, not default runtime behavior.
5. **In-place self-heal / stamp / create-all** — last resort, narrow use only.

---

## 7. Recommended composite strategy (the layered default)

- **Never delete** DB artifacts automatically.
- **Always** run restore-journal recovery first.
- **Classify** the DB before migrations or any DB-dependent startup.
- If clearly **fresh** → initialize automatically.
- If clearly **healthy** → migrate automatically.
- If **ambiguous / desynced / corrupt** → automatically **snapshot** and **enter maintenance mode**.
- From maintenance mode, offer explicit actions in this order: **restore verified backup → quarantine + reset → advanced salvage (on copy) → force repair.**

**Data-safety invariant guaranteed:** *The system never intentionally destroys or overwrites the only known copy of user state. Worst case, it quarantines the suspect DB and requires operator-directed recovery from preserved artifacts or backups.*

---

## 8. Honest failure modes (where even this can still lose data)

These MUST be communicated plainly; the recommended strategy does not make them disappear:

1. **Physical byte loss**: if the on-disk bytes are already corrupt/truncated, or the WAL was lost externally, **no app-level workflow can reconstruct the missing transactions**.
2. **Restore is a rollback**: restoring from backup returns state to the backup timestamp — **data committed after the last backup is gone**.
3. **Availability ≠ continuity**: a successful quarantine + fresh boot restores *availability*, not *logical continuity*. The original state is preserved on disk but is **not automatically merged** back in.
4. **Auto-restore can mask a bug**: if the opt-in auto-restore is enabled and corruption recurs, it can silently roll back on every boot, hiding the root cause. Mitigation: log loudly and stop auto-restoring after a threshold.

---

## 9. Known code touch-points (informative, for planning)

- `anvil/api/app.py` — `lifespan()` re-sequencing; `_seed_license_catalog()` / other best-effort steps broaden exception handling and gate on writable DB; introduce maintenance-mode branch instead of `sys.exit`.
- `anvil/db/migration.py` — `verify_table_integrity()` promoted to a startup gate; `get_schema_version()` must distinguish `unknown/error` from `0/fresh`.
- `anvil/db/session.py` — engine init must surface (not swallow) open/connect failures for classification.
- `anvil/api/v1/health_ops.py` — add readiness endpoint distinct from liveness; reflect maintenance-mode state.
- `anvil/services/backup/` — reuse `SnapshotPlanner`/`BackupService`/`RestoreEngine`/`RestoreJournal`; add a DB-trio snapshot/quarantine helper.
- `compose.yaml` — document healthcheck → liveness.

> Detailed task breakdown and contracts belong in `plan.md` / `tasks.md` (via `/speckit.plan` and `/speckit.tasks`), not here.
