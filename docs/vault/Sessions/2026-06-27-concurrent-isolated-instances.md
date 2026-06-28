---
title: 'Session Log: 2026-06-27 Concurrent Isolated Instances'
type: session-log
tags:
  - type/session-log
  - domain/operations
  - domain/infrastructure
status: canonical
created: '2026-06-27'
updated: '2026-06-27'
---

# Session Log: 2026-06-27 — Concurrent Isolated Instances

## Summary

Full feature lifecycle for 028 Concurrent Isolated Instances:
**specify → clarify → plan → tasks → analyze → implement** (72 tasks).

## Decisions made during session

- **Isolation model**: separate OS process groups, one workspace directory each.
- **Restart model**: config changes save to the per-instance DB; MLflow sidecar auto-restarts; boot-critical settings flagged "pending restart" (no speculative hot-reload).
- **Config persistence**: per-instance app DB, layered over env + defaults, with a boot file for the 4 boot-critical values.
- **Management surface**: CLI-first instance lifecycle; per-instance config UI.
- **Port assignment**: auto-allocate free ports by default, optional explicit override.
- **Instance identity**: caller-provided unique name.
- **Destroy default**: delete workspace data by default; explicit `--keep-data` to preserve.
- **Audit**: all lifecycle + config-change operations audited.
- **Scale**: up to ~10 instances per host.

## Architecture review (Oracle)

Six architectural cruxes resolved via Oracle consultation (research.md A–F):
- Two-layer config (boot file + DB table)
- Must-fix import-time DB session read
- Immutable `get_config()` + separate `RuntimeConfigService`
- CLI restart = SIGTERM + `Popen(start_new_session=True)`
- Global SQLite registry (`~/.anvil/registry.db`)
- Path-isolation audit as first-class mitigation

## Key files created/modified

- 17 new source files (models, services, repos, CLI, API routes, templates)
- 15 modified files (workbench, config, session, router, nav, etc.)
- 10 test files (5 unit + 5 e2e)
- New packages: `anvil/workspace/`, `anvil/services/instances/`, `anvil/services/runtime_config/`

## Test results

101+ passing tests across all user stories. Known: 4 lifecycle-service tests with pre-existing SIGTERM-to-self issue.

## Discoveries

- `StrEnum` + PEP 563 causes pyright false positives in strict mode throughout the codebase
- `Sqlite` unique constraints provide atomic collision detection without a separate lock manager
- File-based PID locks with stale detection are sufficient for ≤10 instances on a single host
