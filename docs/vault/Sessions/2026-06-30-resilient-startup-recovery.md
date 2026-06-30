## Session Log: Resilient Startup Recovery (Spec 061)

**Date**: 2026-06-30
**Feature**: 061-resilient-startup-recovery
**Status**: Complete (spec → clarify → plan → tasks)

### Summary

Implemented the full Spec-Driven Development pipeline for spec 061 (Resilient Startup & Data-Safe Database Recovery). The spec defines a pit-of-success recovery model where on a bad/desynced DB, the server enters maintenance mode (binds port, serves recovery UI) instead of `sys.exit(3)`.

### Artifacts Created

- **spec.md** — Feature specification with 23 FRs, 7 SCs, 6 user stories, clarifications from `/speckit.clarify` (auth-exempt recovery surface + `ANVIL_RECOVERY_KEY`, snapshot/quarantine at `data/backups/quarantine/`)
- **plan.md** — Implementation plan with constitution check (all gates ✅), project structure, complexity tracking (none needed)
- **research.md** — *(pre-existing)* Options analysis for detection, remediation, sequencing, health signals
- **data-model.md** — Entity definitions: `DbState` enum, `StartupClassifier`, `MaintenanceMode`, `RecoveryAction`, `DbSnapshot`, `RecoveryService`
- **contracts/recovery-api.md** — Full API contracts for `/v1/ready`, `/v1/recovery`, `/v1/recovery/backups`, `/v1/recovery/actions/*`
- **quickstart.md** — Operator guide for recovery scenarios and Docker healthcheck configuration
- **tasks.md** — 88 tasks organized by user story (T001–T088)

### Clarifications Applied

- **Auth model**: Auth-exempt recovery surface + `ANVIL_RECOVERY_KEY` bearer token for state-altering actions (avoids DB-deadlock when auth depends on a broken DB)
- **Snapshot location**: `data/backups/quarantine/<timestamp>/` alongside existing 027 backup tree

### Key Decisions

- Simplicity First (Article XI): All new logic uses stdlib + existing infrastructure (no new deps)
- Reuses existing `MigrationService.verify_table_integrity()`, `BackupService`, `RestoreJournal`, `SnapshotPlanner`
- `DbSnapshot` uses direct stdlib file copy (not `BackupService`) to avoid DB-write dependency in maintenance mode
- `StartupClassifier` lives in `anvil/db/db_state.py` (DB domain) rather than a service, since it's a read-only classification component
- `RecoveryService` in new `anvil/services/recovery/` domain sub-package
- MVP scope: US3 (classifier) → US2 (snapshot) → US1 (maintenance mode)

### Changes

- **Updated**: `.specify/feature.json` — points to spec 061 directory
- **Updated**: `AGENTS.md` — agent context updated with new tech info
- **Updated**: `docs/vault/Specs/061-resilient-startup-recovery/spec.md` — clarifications from `/speckit.clarify`
- **Created**: All plan artifacts listed above

### Quality Gates

- `make pr-ready` (format + lint + typecheck): ✅ Pass (9.84/10, all pre-existing warnings)
- `make test` (1001 unit tests): ✅ 1001 passed, 2 skipped
- `make vault-audit`: ✅ 1 pre-existing error, 39 frontmatter warnings (same pattern as all other spec dirs)
- `mypy --strict`: ✅ 440 files, no issues
