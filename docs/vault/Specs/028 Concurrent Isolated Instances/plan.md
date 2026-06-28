---
title: 'Implementation Plan: Concurrent Isolated Instances'
type: spec
tags:
  - type/spec
  - domain/operations
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/028 Concurrent Isolated Instances/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 028 Concurrent Isolated Instances - plan
---

# Implementation Plan: Concurrent Isolated Instances

**Branch**: `028-concurrent-isolated-instances` | **Date**: 2026-06-27 | **Spec**: [[028 Concurrent Isolated Instances/spec|spec.md]]
**Input**: Feature specification from `docs/vault/Specs/028 Concurrent Isolated Instances/spec.md`

## Summary

Enable running up to ~10 fully isolated instances of the anvil stack concurrently on one host, each as a separate OS process group rooted at its own **workspace directory**. Every persistent write (app DB, datasets, storage, models, content, mlruns, api_key, logs) derives from that workspace root, so instances cannot read or corrupt each other's data, and the lifecycle of one instance never affects another. Each instance exposes UI/REST CRUD over its own runtime configuration; the MLflow sidecar auto-restarts on relevant changes, while boot-critical settings (web port, MLflow port, DB path, workspace root) are flagged **pending restart** and applied via a CLI restart. Instance lifecycle (create/list/start/stop/restart/destroy) is CLI-first for agent automation, backed by a global host-level registry that enforces name/port/workspace uniqueness.

**Technical approach** (per Oracle architecture review — see `research.md`): a **two-layer config model** (an authoritative per-workspace `instance.json` boot file for boot-critical values + a DB-backed `runtime_config` table for editable non-boot settings), an explicit **`WorkspacePaths` resolution layer** that every path derives from (replacing the ~5 CWD-relative hardcoded paths and the import-time DB-engine creation), and a **global SQLite registry** at a host-level path for cross-instance collision detection. `get_config()` stays immutable; a new `RuntimeConfigService` serves live-editable settings without caching.

## Technical Context

**Language/Version**: Python 3.11+ (repo standard; `StrEnum`, PEP 604 unions, PEP 563 `from __future__ import annotations`)
**Primary Dependencies**: FastAPI, async SQLAlchemy + aiosqlite, Alembic, Jinja2, uvicorn, MLflow (sidecar). **No new runtime dependencies** — boot file uses stdlib `json`; global registry uses the existing async SQLAlchemy/Alembic stack (or stdlib `sqlite3` for the host-level store — see research.md F).
**Storage**: Per-instance SQLite app DB (WAL) under each workspace; a host-level global registry SQLite DB at `~/.anvil/registry.db`; per-workspace `instance.json` boot file (JSON on disk).
**Testing**: pytest (`tests/unit/`, `tests/e2e/`); `client` fixture provides an `httpx.AsyncClient` over an in-memory SQLite app DB. New tests: unit (WorkspacePaths resolution, boot-file load/validate, RuntimeConfigService, registry collision/lock, pending-restart diff) + e2e (config CRUD endpoints) + a multi-process isolation test.
**Target Platform**: macOS + Linux (POSIX shell; `make`/`bash` toolchain). Single host.
**Project Type**: Web service + CLI (single `anvil` package, layered architecture).
**Performance Goals**: Config page loads < 1s (SC-003 derived); instance start to healthy comparable to today's single-instance startup; registry collision checks are O(instances) over ≤ ~10 rows.
**Constraints**: Constitution Article XI (Simplicity First / boring); Article IV (TDD, ratcheting coverage); Article V (async throughout); Article VII (Repository→Service→GodClass→Routes/CLI); Article X (domain sub-packages); one-class-per-file; `mypy --strict`; Pydantic `BaseModel`; UX rules (`docs/ux-rules.md`) for the config page.
**Scale/Scope**: Up to ~10 concurrent instances per host (clarified). Not designed for moderate/unbounded fleets. Single host only — no cross-host coordination.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Article I (Zero-Dependency Core)** — PASS. No change to `anvil/core/`; this is an opt-in operational layer.
**Article IV (TDD Mandatory)** — PASS (by plan). Every new unit (WorkspacePaths, BootConfig, RuntimeConfigService, registry repo, lifecycle service, pending-restart diff) is testable in isolation; a multi-process e2e proves isolation. No untested paths shipped (§11.6).
**Article V (Async-First)** — PASS. New services/repos are async; the registry uses async SQLAlchemy. CLI wraps via `asyncio.run()`. Process spawning (subprocess) is the existing sync-at-edge pattern already used by the supervisor.
**Article VII (Layered Architecture)** — PASS. New `InstanceRegistryRepository` + `RuntimeConfigRepository` (DB only), `InstanceLifecycleService` + `RuntimeConfigService` (logic), exposed via `AnvilWorkbench` properties, called by Routes + CLI. No DB primitives leak.
**Article X (Domain-Driven Decomposition)** — PASS. New domain sub-packages `anvil/services/instances/` and `anvil/services/runtime_config/`; path-resolution lives in `anvil/_shared/` or a small `anvil/workspace/` package. Bare docstring `__init__.py` per Article VI.
**Article XI — Simplicity First gate (hard MUST)**:

- [x] **Simplest viable** (§11.1) — separate OS processes + one workspace root is the simplest model that genuinely isolates data on one host; no orchestration/container layer introduced.
- [x] **Boring over novel** (§11.2) — reuses stdlib `json` for the boot file and the existing SQLAlchemy/Alembic stack for the registry. No new framework or dependency.
- [x] **YAGNI** (§11.3) — no guardian/supervisor daemon, no hot-reload plumbing for import-time settings, no cross-host story. Boot file holds only the 4 boot-critical keys.
- [x] **Reuse first** (§11.4) — reuses `ProcessSupervisor`/PID helpers, `AuditService`, the workbench/repository/migration patterns, the operations-page UI pattern, and existing env-var overrides.
- [x] **Testable** (§11.6) — each layer is unit-testable; isolation is provable via a multi-process test. The pending-restart diff is a pure comparison.

> The one structural addition beyond "reuse existing" — the per-workspace `instance.json` boot file and the global registry DB — is recorded in **Complexity Tracking** below with the simpler alternative rejected. Per Oracle, these are the *minimum* extra state needed to break the DB-path/port chicken-and-egg and to detect cross-instance collisions; they are not speculative.

**Gate result: PASS** (with Complexity Tracking entries recorded).

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/028 Concurrent Isolated Instances/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 — Oracle decisions A–F
├── data-model.md        # Phase 1 — entities, enums, migration
├── quickstart.md        # Phase 1 — operator/agent walkthrough
├── contracts/           # Phase 1 — CLI + REST + UI contracts
│   ├── cli-instance-commands.md
│   ├── rest-config-api.md
│   └── ui-config-page.md
└── tasks.md             # Phase 2 (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
anvil/
├── workspace/                         # NEW — path-resolution + boot layer (authoritative level)
│   ├── __init__.py                    #   bare docstring
│   ├── workspace_paths.py             #   WorkspacePaths: derive every path from a workspace root
│   └── boot_config.py                 #   BootConfig: load/validate/write instance.json
├── config.py                          # CHANGED — stays immutable; reads boot layer when ANVIL_WORKSPACE_DIR set
├── db/
│   ├── session.py                     # CHANGED — remove import-time engine creation; explicit init_engine(paths)
│   ├── models/
│   │   ├── runtime_config.py          # NEW — RuntimeConfig ORM (per-instance config table)
│   │   └── instance_record.py         # NEW — InstanceRecord ORM (global registry row)
│   └── repositories/
│       ├── runtime_config.py          # NEW — RuntimeConfigRepository
│       └── instance_registry.py       # NEW — InstanceRegistryRepository (global registry DB)
├── services/
│   ├── runtime_config/                # NEW domain sub-package
│   │   ├── __init__.py
│   │   ├── runtime_config_service.py  #   read/CRUD editable settings; no lru_cache
│   │   ├── config_setting.py          #   ConfigSetting value object (key/value/source/apply_class)
│   │   ├── config_source.py           #   ConfigSource StrEnum (default/env/override)
│   │   └── apply_class.py             #   ApplyClass StrEnum (boot_critical/applies_live/mlflow_restart)
│   └── instances/                     # NEW domain sub-package
│       ├── __init__.py
│       ├── instance_lifecycle_service.py  # create/list/start/stop/restart/destroy
│       ├── instance_status.py             # InstanceStatus StrEnum (running/stopped/unhealthy)
│       └── workspace_lock.py              # lock acquire/reclaim (PID-validated)
├── api/
│   ├── v1/
│   │   ├── config.py                  # NEW — config CRUD router (GET/PUT/reset/pending)
│   │   ├── pages.py                   # CHANGED — add GET /v1/config-page
│   │   ├── router.py                  # CHANGED — include config_router
│   │   └── schemas.py                 # CHANGED — add config request/response DTOs
│   └── templates/
│       ├── config.html                # NEW — configuration page (extends base.html)
│       └── base.html                  # CHANGED — add Configuration nav tab
├── supervisor/                        # REUSED — ProcessSupervisor, write_pid/kill_pid_file
├── workbench.py                       # CHANGED — add runtime_config, instances, registry properties
├── cli.py                             # CHANGED — wire `anvil-instance` console entry (or new module)
└── _resources/migrations/versions/
    ├── 00X_add_runtime_config.py      # NEW — per-instance runtime_config table
    └── (global registry migration / schema — see research.md F)

tests/
├── unit/
│   ├── workspace/test_workspace_paths.py
│   ├── workspace/test_boot_config.py
│   ├── services/test_runtime_config_service.py
│   ├── services/test_instance_lifecycle_service.py
│   └── db/test_instance_registry.py
└── e2e/
    ├── test_config_endpoints.py
    └── test_instance_isolation.py     # multi-process: two instances, no cross-contamination
```

**Structure Decision**: Single `anvil` package, layered. Two new domain sub-packages (`services/instances/`, `services/runtime_config/`) per Article X, plus a small `anvil/workspace/` package for the path/boot layer that must be importable before `db/session.py`. All paths route through `WorkspacePaths`; the import-time DB-engine creation in `db/session.py` is converted to explicit initialization (Oracle B/b1, mandatory).

## Complexity Tracking

> Recording the deviations from "reuse only" required by this feature.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New per-workspace `instance.json` boot file | Boot-critical values (workspace root, web/MLflow ports, DB path) must be known *before* the per-instance DB is opened and the port is bound — they cannot live solely in the DB they gate (chicken-and-egg). | "Store all config in the DB" is impossible for boot-critical keys; "pass everything via CLI flags/env each start" is fragile and non-persistent across restarts. Per Oracle (A), the boot file is the *minimum* extra state to break the cycle. |
| New global registry store (`~/.anvil/registry.db`) | Port/workspace collision detection and name uniqueness are inherently *cross-instance*, so the registry cannot live in any single instance's per-instance DB. | A per-instance table can't see other instances. Directory-scanning + probing (f3) was considered but gives no atomic uniqueness guarantee; a global SQLite DB with unique constraints is the boring, correct choice (Oracle F). |
| Refactor `db/session.py` import-time engine creation → explicit init; route ~5 hardcoded paths through `WorkspacePaths` | Without this, per-instance isolation is unattainable: the DB path is baked at import and 5 write paths resolve to CWD, leaking across instances. | "Set CWD per process" (b2) is too fragile — import-time singletons and any future `resolve()`-at-import bypass it. Oracle (B) rules the import-time read a must-fix regardless; CWD is belt-and-suspenders only. |

*All three are justified by a concrete present requirement (isolation + collision detection), not speculation — Constitution Check passes.*

## Phase Status

- [x] Phase 0 — research.md (Oracle decisions A–F resolved; no open NEEDS CLARIFICATION)
- [x] Phase 1 — data-model.md, contracts/, quickstart.md, agent context update
- [ ] Phase 2 — tasks.md (via `/speckit.tasks`)

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1: design introduces no new dependencies, keeps each new unit testable, preserves layering, and confines complexity to the three justified items above. **PASS** — ready for `/speckit.tasks`.
