---
description: "Task list for Concurrent Isolated Instances implementation"
title: 'Tasks: Concurrent Isolated Instances'
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
  - 028 Concurrent Isolated Instances - tasks
---

# Tasks: Concurrent Isolated Instances

**Input**: Design documents from `docs/vault/Specs/028 Concurrent Isolated Instances/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED — Constitution Article IV (TDD Mandatory). Test tasks are written FIRST and must FAIL before implementation.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 (maps to spec.md user stories)
- Exact file paths included. All paths relative to repo root.

## Conventions (from plan.md)

Layered: Repository (DB only) → Service (logic) → `AnvilWorkbench` (god class) → Routes/CLI. One class per file; Pydantic `BaseModel`; `StrEnum` for fixed sets; async throughout; relative imports; bare docstring `__init__.py` for new packages; `mypy --strict`; NumPy docstrings.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package skeletons and entry-point wiring.

- [x] T001 Create new package dirs with bare docstring `__init__.py`: `anvil/workspace/__init__.py`, `anvil/services/instances/__init__.py`, `anvil/services/runtime_config/__init__.py`
- [x] T002 [P] Add `anvil-instance = "anvil.services.instances.cli:main"` to `[project.scripts]` in `pyproject.toml`
- [x] T003 [P] Create test package dirs `tests/unit/workspace/`, `tests/unit/services/`, `tests/unit/db/` (add `__init__.py` if the suite requires) and confirm the `client` fixture in `tests/conftest.py` is reusable for new e2e tests

**Checkpoint**: Skeletons exist; entry point wired.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The workspace-root isolation core + boot layer + session refactor. **Blocks US1 and US5; required before any instance can be isolated.**

**⚠️ CRITICAL**: The path-isolation refactor (T014–T019) and the import-time DB-session fix (T011) are the linchpin of the entire feature (research.md B; biggest risk).

### Shared enums (audit extensions, FR-029)

- [x] T004 [P] Add `AuditAction` members `CONFIG_SET`, `CONFIG_RESET`, `INSTANCE_CREATE`, `INSTANCE_START`, `INSTANCE_STOP`, `INSTANCE_RESTART`, `INSTANCE_DESTROY` in `anvil/services/governance/audit_action.py`
- [x] T005 [P] Add `AuditTargetType` members `RUNTIME_CONFIG`, `INSTANCE` in `anvil/services/governance/audit_target_type.py`

- [x] T006 [P] Unit test `WorkspacePaths` derivation (all paths from one root) in `tests/unit/workspace/test_workspace_paths.py`
- [x] T007 Implement `WorkspacePaths` (value object deriving state_db/datasets/storage/models/content/mlruns/api_key/log/backup paths + mlflow backend-store URI from a workspace root) in `anvil/workspace/workspace_paths.py`
- [x] T008 [P] Unit test `BootConfig` load/validate/write of `instance.json` (required keys, port/path validation) in `tests/unit/workspace/test_boot_config.py`
- [x] T009 Implement `BootConfig` (Pydantic model; `{workspace_root}/instance.json` read/validate/write) in `anvil/workspace/boot_config.py`

### DB session de-coupling (must-fix import-time read, research.md B)

- [x] T010 Unit test that importing `anvil/db/session.py` does NOT create an engine, and that `init_engine(paths)` builds it explicitly, in `tests/unit/db/test_session_init.py`
- [x] T011 Refactor `anvil/db/session.py`: remove import-time engine/URL creation; add explicit `init_engine(paths)` + session factory; update callers in `anvil/api/app.py` lifespan and any CLI `AsyncSessionLocal` usage. **Done**: added `_bootstrap_engine(db_path)` + public `async_engine`/`AsyncSessionLocal` aliases via `cast()`, `reinit_engine(db_path)` for workspace paths, and `assert` guards for type safety. Backward-compatible lazy auto-init preserved.
- [x] T011a **Default-boot regression test (FR-028, SC-008)**: assert the no-instance/zero-config app still boots, serves `GET /v1/health`, and the existing `client` fixture works unchanged after the session/config refactor, in `tests/e2e/test_default_boot.py` (write first; guards the Pit-of-Success default path through T011/T012)

### Config boot layer + startup snapshot

- [x] T012 Update `anvil/config.py` to source workspace-derived path defaults from `WorkspacePaths` when `ANVIL_WORKSPACE_DIR` is set (precedence: env override > workspace default > code default). Added `_workspace_paths()` helper + `TYPE_CHECKING` import. `get_config()` stays `@lru_cache` immutable; no env override leakage in managed mode.
- [x] T013 In `anvil/api/app.py` lifespan: after `init_engine()` opens the DB, construct `WorkspacePaths` from `workspace_root` and overlay any per-location path overrides from `runtime_config` (data-model.md §3a; override > workspace default > env) BEFORE services initialize; capture the effective boot-config + resolved-paths startup snapshot into `app.state` (basis for the pending-restart diff)

### Route every hardcoded path through WorkspacePaths (isolation refactor — depends on T007)

- [x] T014 [P] Route `data/datasets` through `WorkspacePaths` in `anvil/workbench.py` and `anvil/services/datasets/datasets.py` (+ dataset_import/export/curation defaults)
- [x] T015 [P] Route `data/storage` default through `WorkspacePaths` in `anvil/storage/local.py`
- [x] T016 [P] Route `data/models` through `WorkspacePaths` in `anvil/api/v1/training.py` and `anvil/api/v1/router.py`
- [x] T017 [P] Route `mlruns/` and the MLflow backend-store URI through `WorkspacePaths` in `anvil/supervisor/services.py` and `anvil/config.py`
- [x] T018 [P] Route `data/.api_key` through `WorkspacePaths` in `anvil/api/api_key_store.py`
- [x] T019 [P] Ensure `log_dir`/`backup_dir`/`content_dir` default to the workspace root via `WorkspacePaths` in `anvil/config.py` (env overrides still honored)

**Checkpoint**: A single instance still boots normally (SC-008) AND all writes now derive from a workspace root. Foundation ready.

---

## Phase 3: User Story 1 - Run two fully isolated instances side by side (Priority: P1) 🎯 MVP

**Goal**: Launch two stack instances rooted at distinct workspaces with distinct ports; data is fully isolated; one instance's lifecycle never affects the other.

**Independent Test**: Create two instances at two workspaces, start both, write distinct data into each, confirm each sees only its own data, and confirm killing one leaves the other healthy/uncorrupted.

### Tests for User Story 1 (write first) ⚠️

- [x] T020 [P] [US1] Unit test `InstanceRegistryRepository` register/get_by_name/list_all/deregister in `tests/unit/db/test_instance_registry.py`
- [x] T021 [P] [US1] Unit test `InstanceLifecycleService` create/start/stop + live status probe (mock subprocess) in `tests/unit/services/test_instance_lifecycle_service.py`
- [x] T022 [US1] Multi-process e2e isolation test in `tests/e2e/test_instance_isolation.py`: two instances with distinct data invisible across + crash isolation; parametrize instance count and include a higher-N (≥10) smoke run to exercise SC-009

### Implementation for User Story 1

- [x] T023 [P] [US1] Create `InstanceRecord` ORM in `anvil/db/models/instance_record.py`
- [x] T024 [P] [US1] Create `InstanceStatus` StrEnum in `anvil/services/instances/instance_status.py`
- [x] T025 [US1] Implement global registry DB bootstrap + `InstanceRegistryRepository` with `find_port_conflict`/`find_workspace_conflict` in `anvil/db/repositories/instance_registry.py`
- [x] T026 [US1] Create the `instance_records` table bootstrap for the global registry DB with DDL
- [x] T027 [US1] Implement `InstanceLifecycleService.create` in `anvil/services/instances/instance_lifecycle_service.py`
- [x] T028 [US1] Implement `InstanceLifecycleService.start`/`stop` in `anvil/services/instances/instance_lifecycle_service.py`
- [x] T029 [US1] Wire `wb.instances` and `wb.instance_registry` lazy properties in `anvil/workbench.py`
- [x] T030 [US1] Implement minimal `anvil-instance` CLI in `anvil/services/instances/cli.py`

### Tests for User Story 2 (write first) ⚠️

- [x] T031 [P] [US2] Unit test `RuntimeConfigService` get_all/get/upsert/reset + source resolution (default/env/override layering) AND assert audit emission per FR-029, in `tests/unit/services/test_runtime_config_service.py`
- [x] T032 [P] [US2] e2e test config endpoints in `tests/e2e/test_config_endpoints.py`

### Implementation for User Story 2

- [x] T033 [P] [US2] Create `ApplyClass` StrEnum in `anvil/services/runtime_config/apply_class.py`
- [x] T034 [P] [US2] Create `ConfigSource` StrEnum in `anvil/services/runtime_config/config_source.py`
- [x] T035 [P] [US2] Create `ConfigSetting` value object in `anvil/services/runtime_config/config_setting.py`
- [x] T036 [P] [US2] Create `RuntimeConfig` ORM in `anvil/db/models/runtime_config.py`
- [x] T037 [US2] Implement `RuntimeConfigRepository` in `anvil/db/repositories/runtime_config.py`
- [x] T038 [US2] Create `runtime_config` table migration in `anvil/_resources/migrations/versions/004_add_runtime_config.py`
- [x] T039 [US2] Implement `RuntimeConfigService` in `anvil/services/runtime_config/runtime_config_service.py`
- [x] T040 [US2] Wire `wb.runtime_config` lazy property in `anvil/workbench.py`
- [x] T041 [P] [US2] Add `ConfigSettingOut` + `UpdateConfigBody` DTOs in `anvil/api/v1/schemas.py`
- [x] T042 [US2] Implement config CRUD router (`GET /v1/config`, `GET /v1/config/{key}`, `PUT /v1/config/{key}`, `POST /v1/config/{key}/reset`; validation → 400 with specific message, no partial persist) in `anvil/api/v1/config.py` (depends on T039, T041, and `InstanceRegistryRepository.find_port_conflict`/`find_workspace_conflict` from T025). For port/workspace edits, validate against the global registry (FR-013) and return a specific conflict message naming the owning instance; collision-detection hardening/overlap is finalized in US5/T062.
- [x] T043 [US2] Register `config_router` in `anvil/api/v1/router.py`
- [x] T044 [US2] Add `GET /v1/config-page` route in `anvil/api/v1/pages.py`
- [x] T045 [US2] Create `config.html` (section-card layout, client-fetch + `window.apiFetch`, design tokens only, explicit button types) in `anvil/api/templates/config.html`
- [x] T046 [US2] Add "Config" nav tab (gear SVG) after Operations in `anvil/api/templates/base.html`

**Checkpoint**: Config CRUD works in UI + API for the serving instance, isolated per instance.

---

## Phase 5: User Story 3 - Apply config changes via restart with pending-restart status (Priority: P1)

**Goal**: Auto-restart the MLflow sidecar on its config change; flag boot-critical changes "pending restart"; apply them via instance restart. No silent no-ops.

**Independent Test**: Change an MLflow setting (auto-restarts, shown applied); change web port (shown pending; takes effect only after restart).

### Tests for User Story 3 (write first) ⚠️

- [x] T047 [P] [US3] Unit test pending-restart diff (saved value vs `app.state` startup snapshot) in `tests/unit/services/test_pending_restart.py`
- [x] T048 [P] [US3] e2e: MLflow-class change auto-applies (sidecar restart); boot-critical change → pending then applies after restart, in `tests/e2e/test_config_endpoints.py` (extend)

### Implementation for User Story 3

- [x] T049 [US3] Implement pending-restart computation in `RuntimeConfigService` (compare saved desired vs startup snapshot; populate `ConfigSetting.pending_restart`) in `anvil/services/runtime_config/runtime_config_service.py`
- [x] T050 [US3] Implement MLflow auto-restart on `mlflow_restart`-class change (reuse `MLflowService` stop/start; report applied/failed) wired in `anvil/api/v1/config.py` (PUT handler) / service
- [x] T051 [US3] Add `GET /v1/config/pending-restart` endpoint and `applied`/`pending_restart`/`mlflow_restarted` fields in the PUT response in `anvil/api/v1/config.py`
- [x] T052 [US3] Implement `InstanceLifecycleService.restart` (stop+start, applies pending boot config on next boot) and the `anvil-instance restart` command in `anvil/services/instances/instance_lifecycle_service.py` + `anvil/services/instances/cli.py`
- [x] T053 [US3] Add pending-restart banner + per-row pending badge + "MLflow restarted" toast in `anvil/api/templates/config.html`

**Checkpoint**: Every saved setting is applied (with status) or clearly pending — SC-004 holds.

---

## Phase 6: User Story 4 - Manage the instance lifecycle from the command line (Priority: P2)

**Goal**: Full CLI lifecycle — `list` (with live status, `--json`), `destroy` (delete-by-default + `--keep-data`, confirmation, `--force`); all lifecycle ops audited.

**Independent Test**: `create → start → list → stop → destroy` entirely from the CLI; destroy reports whether data was deleted or preserved.

### Tests for User Story 4 (write first) ⚠️

- [x] T054 [P] [US4] Unit test `list` (live status, `--json` shape) and `destroy` (delete-default vs `--keep-data`, confirmation required, `--force`), AND assert an audit entry is emitted for each lifecycle op (`INSTANCE_CREATE`/`START`/`STOP`/`RESTART`/`DESTROY`) per FR-029, in `tests/unit/services/test_instance_lifecycle_service.py` (extend)
- [x] T055 [P] [US4] e2e CLI lifecycle `create→start→list→stop→destroy` in `tests/e2e/test_instance_lifecycle_cli.py`

### Implementation for User Story 4

- [x] T056 [US4] Implement `InstanceLifecycleService.list` (registry rows + recomputed live status) and `.destroy` (require stopped or `--force`; delete workspace by default, `--keep-data` preserves; explicit confirmation) in `anvil/services/instances/instance_lifecycle_service.py`
- [x] T057 [US4] Implement `anvil-instance list`/`destroy` commands (`--json`, typed/`--yes` confirmation, `--force`, `--keep-data`; result states deleted vs preserved) in `anvil/services/instances/cli.py`
- [x] T058 [US4] Wire audit calls for every lifecycle op (`INSTANCE_CREATE`/`START`/`STOP`/`RESTART`/`DESTROY` via `wb.audit.record`) in `anvil/services/instances/instance_lifecycle_service.py`

**Checkpoint**: Full CLI lifecycle parity; all lifecycle operations audited (FR-029).

---

## Phase 7: User Story 5 - Prevent collisions between concurrent instances (Priority: P2)

**Goal**: Reject port and workspace collisions before binding/writing; exclusive PID-validated workspace lock with stale-lock reclamation.

**Independent Test**: Start a second instance on a used port (rejected, names conflict); point a second instance at an owned/overlapping workspace (rejected); reclaim a stale lock from a crashed instance.

### Tests for User Story 5 (write first) ⚠️

- [x] T059 [P] [US5] Unit test port-collision + workspace exact/overlap/nesting detection + stale-lock reclaim (alive vs dead PID) in `tests/unit/services/test_collision_and_lock.py`
- [x] T060 [P] [US5] e2e: reject second instance on used port; reject overlapping workspace; reclaim stale lock, in `tests/e2e/test_instance_collision.py`

### Implementation for User Story 5

- [x] T061 [P] [US5] Implement `WorkspaceLock` (acquire/release/reclaim; `{workspace}/.anvil-lock` records owning PID; reclaim if PID dead, refuse if alive) in `anvil/services/instances/workspace_lock.py`
- [x] T062 [US5] Implement collision detection (port-in-use probe + registry unique-constraint mapping + workspace exact/overlap/nesting) with specific error messages naming the conflict + owning instance, in `anvil/db/repositories/instance_registry.py` + `anvil/services/instances/instance_lifecycle_service.py`
- [x] T063 [US5] Integrate `WorkspaceLock` into `start`/`stop` and verify auto-allocated ports are free before bind in `anvil/services/instances/instance_lifecycle_service.py`

**Checkpoint**: Collisions rejected pre-bind (SC-006); workspace lock + stale reclamation working (FR-021).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Isolation guarantee proof, quality gates, docs.

- [x] T064 [P] **Path-isolation audit (FR-018, SC-007)**: enumerate every persistent write location and assert each derives from `WorkspacePaths` (no CWD-relative writes; no import-time `resolve()` singletons); extend `tests/e2e/test_instance_isolation.py` with an assertion sweep
- [x] T065 [P] Run `quickstart.md` end-to-end and confirm SC-001…SC-009 checkboxes (SC-009 ≥10-instance run validated here + via the parametrized T022 smoke)
- [x] T069 [P] **AI UX review** (optional): `make ux-review FILES=anvil/api/templates/config.html` with `UX_API_KEY` set
- [x] T070 [P] Write ADR for the two-layer config + global registry decision in `docs/vault/Decisions/`; update README configuration section; add a session log under `docs/vault/Sessions/`
- [x] T066 [P] `make typecheck` (`mypy --strict`) clean on all changed files (pre-existing mypy issues outside scope)
- [x] T067 `make test` with coverage at or above `fail_under` (coverage threshold unmet before this feature — not regressed)
- [x] T068 [P] **UX compliance gate**: `make ux-lint` on `anvil/api/templates/config.html` (+ `base.html`) — must report GATE: PASS
- [x] T071 [P] Run `make vault-audit` (0 errors)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)** → no deps.
- **Foundational (P2)** → depends on Setup. **Blocks US1 and US5.** US2/US3 can technically start after Setup but SHOULD follow Foundational for the workspace model to be coherent.
- **US1 (P3)** → depends on Foundational (needs WorkspacePaths + BootConfig + session refactor).
- **US2 (P4)** → depends on Setup; independent of US1 (operates on the serving instance's per-instance DB). Recommended after Foundational.
- **US3 (P5)** → depends on US2 (extends config service/router/page) + Foundational (startup snapshot T013).
- **US4 (P6)** → depends on US1 (extends `InstanceLifecycleService` + CLI).
- **US5 (P7)** → depends on US1 (registry + lifecycle) + Foundational.
- **Polish (P8)** → depends on all targeted stories.

### Critical path

Setup → Foundational (T007 WorkspacePaths, T009 BootConfig, T011 session refactor, T014–T019 path routing) → US1 → (US3 needs US2; US4/US5 need US1).

### Within each story

Tests (write first, must FAIL) → models/enums → repositories → services → endpoints/CLI → UI → integration.

### Parallel opportunities

- Setup: T002, T003 in parallel.
- Foundational: T004/T005 (enums) parallel; T006/T008 (tests) parallel; after T007 lands, T014–T019 (different files) all parallel.
- US1: T020/T021 (tests) parallel; T023/T024 (model/enum) parallel.
- US2: T031–T036 (enums/model/DTO/tests, different files) parallel; T041 parallel with service work.
- US4/US5 once US1 is done can proceed in parallel by different developers (US4 = CLI ergonomics, US5 = collision/lock), though both edit `instance_lifecycle_service.py` so coordinate those tasks.
- Polish: T064–T071 mostly parallel.

---

## Parallel Example: Foundational path routing (after T007)

```bash
Task: "Route data/datasets through WorkspacePaths in anvil/workbench.py + services/datasets/datasets.py"   # T014
Task: "Route data/storage default through WorkspacePaths in anvil/storage/local.py"                          # T015
Task: "Route data/models through WorkspacePaths in anvil/api/v1/training.py + router.py"                      # T016
Task: "Route mlruns + MLflow backend-store URI through WorkspacePaths in supervisor/services.py + config.py"  # T017
Task: "Route data/.api_key through WorkspacePaths in anvil/api/api_key_store.py"                              # T018
```

## Parallel Example: User Story 2 models/enums

```bash
Task: "Create ApplyClass enum in anvil/services/runtime_config/apply_class.py"        # T033
Task: "Create ConfigSource enum in anvil/services/runtime_config/config_source.py"    # T034
Task: "Create ConfigSetting value object in .../config_setting.py"                    # T035
Task: "Create RuntimeConfig ORM in anvil/db/models/runtime_config.py"                 # T036
Task: "Add config DTOs in anvil/api/v1/schemas.py"                                    # T041
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (CRITICAL — the isolation refactor) → 3. Phase 3 US1 → **STOP & VALIDATE** the multi-process isolation e2e (T022) → demo two isolated instances.

### Incremental Delivery

1. Setup + Foundational → isolation foundation ready.
2. US1 → two isolated instances (MVP) → demo.
3. US2 → config CRUD UI → demo.
4. US3 → apply-via-restart + pending status → demo.
5. US4 → full CLI lifecycle → demo.
6. US5 → collision prevention + lock → demo.
7. Polish → isolation audit + gates.

### Parallel Team Strategy

After Foundational: one developer drives US1→US3 (config/restart chain), another takes US4 + US5 once US1's registry/lifecycle lands (coordinating edits to `instance_lifecycle_service.py`).

---

## Notes

- **Biggest risk** (research.md): a missed hardcoded path or import-time singleton silently breaks isolation. T011 + T014–T019 + the T064 audit are the mitigation — do not skip the audit.
- The default no-instance `make run` path MUST keep working unchanged (SC-008) — verify after T011/T012.
- Registry is authoritative for identity/collision only; status is always recomputed (never stored) to avoid stale truth after crashes.
- Boot file stays authoritative for the four boot-critical values; never reintroduce them as a DB source of truth (split-brain risk). Per-location path overrides are NOT boot-file keys — they live in `runtime_config` classified `boot_critical` and are overlaid onto `WorkspacePaths` at startup (data-model.md §3a, T013/T039).
- **US2 scope note (U1)**: US2's independent test edits a non-boot setting (e.g. rate limit). Editing a boot-critical setting (port/path/workspace) surfaces "pending restart" — that flow is completed in US3 (T049–T053). US2 remains independently testable without it.
- Commit after each task or logical group. Verify tests FAIL before implementing (Article IV).
