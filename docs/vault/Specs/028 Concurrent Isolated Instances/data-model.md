---
title: 'Data Model: Concurrent Isolated Instances'
type: spec
tags:
  - type/spec
  - domain/operations
  - domain/infrastructure
  - domain/database
spec-refs:
  - docs/vault/Specs/028 Concurrent Isolated Instances/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 028 Concurrent Isolated Instances - data-model
---

# Data Model: Concurrent Isolated Instances

Phase 1 output. Three stores, matching the two-layer config model + global registry (research.md A/F):

1. **Boot file** — per-workspace `instance.json` on disk (authoritative for boot-critical values).
2. **`runtime_config` table** — in each instance's per-instance app DB (editable non-boot settings).
3. **`instance_records` table** — in a single global host-level registry DB (cross-instance identity/collision).

All ORM models follow the verified codebase conventions: inherit `Base` + `TimestampMixin`; `Mapped[...]` + `mapped_column`; enums stored as `String(n)` with `StrEnum` applied at the service layer; one class per file; Pydantic `BaseModel` for value objects; NumPy docstrings.

---

## 1. Boot file — `instance.json` (on disk, per workspace)

Plain JSON written/read by `anvil/workspace/boot_config.py` (`BootConfig`, a Pydantic `BaseModel`). Located at `{workspace_root}/instance.json`. Authoritative; never overridden by env in managed mode.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Instance name (== registry identifier). Required, unique, filesystem/URL-safe. |
| `workspace_root` | `str` (abs path) | The single root all other paths derive from. |
| `web_port` | `int` | Web/uvicorn bind port. |
| `mlflow_port` | `int` | MLflow sidecar port. |
| `state_db_path` | `str` (abs path) | Per-instance app DB path; defaults to `{workspace_root}/data/anvil-state.db`. |
| `schema` | `int` | Boot-file format version (for forward compat). |

**Validation**: all four boot-critical values present and well-formed; ports are integers in valid range; paths absolute and under (or consistent with) `workspace_root`. Loaded and validated **before** `db/session.init_engine()` and before binding the port.

**Scope (deliberately minimal — Oracle A/D)**: the boot file holds ONLY these four keys. It is NOT extended with per-location path overrides (see §3a) — keeping boot-file/DB split-brain risk to the four values that genuinely gate DB-open and port-bind.

---

## 2. `WorkspacePaths` (value object — `anvil/workspace/workspace_paths.py`)

Not persisted; a Pydantic `BaseModel` (or frozen value object) constructed from `workspace_root`. Single source of truth for every write location (resolves FR-008, FR-018). Derives:

| Property | Default derivation |
|---|---|
| `state_db_path` | `{root}/data/anvil-state.db` |
| `datasets_dir` | `{root}/data/datasets` |
| `storage_dir` | `{root}/data/storage` |
| `models_dir` | `{root}/data/models` |
| `content_dir` | `{root}/data/content` |
| `mlruns_dir` | `{root}/mlruns` |
| `mlflow_backend_store_uri` | `sqlite:///{root}/mlruns/mlflow.db` |
| `api_key_path` | `{root}/data/.api_key` |
| `log_dir` | `{root}/logs` |
| `backup_dir` | `{root}/data/backups` |

Each replaces a current CWD-relative hardcoded path or import-time `resolve()`. Per-location env overrides remain supported (advanced use) but default to workspace-derived.

---

## 3. `RuntimeConfig` (ORM — per-instance app DB)

File: `anvil/db/models/runtime_config.py`. Table: `runtime_config`. Stores **only editable non-boot overrides** (key/value rows layered over env + defaults at read time).

| Column | Type (DB) | Notes |
|---|---|---|
| `id` | `Integer` PK autoincrement | |
| `key` | `String(100)` unique, indexed | Setting key (e.g. `rate_limit`, `device`, `cors_origins`, `backup_quota_bytes`). |
| `value` | `Text` | Serialized value (string form; typed/validated at service layer). |
| `apply_class` | `String(20)` | `ApplyClass` value — see enums. Defaults from a static setting catalog, not user input. |
| `created_at` / `updated_at` | `DateTime` | via `TimestampMixin`. |

**Constraints**: `key` unique. Reset (FR-012) = delete the row → value falls back to env/default. The **four boot-file keys** (`workspace_root`, `web_port`, `mlflow_port`, `state_db_path`) are **not** stored here (they live in the boot file). All OTHER settings — including per-location path overrides (§3a) — live here; their `apply_class` distinguishes whether they apply live, via MLflow restart, or only on next boot.

### 3a. Per-location path overrides (resolves FR-008)

FR-008 permits overriding an individual derived path (e.g. point `models_dir` elsewhere) without changing `workspace_root`. Decision:

- **Storage**: per-location path overrides (`datasets_dir`, `storage_dir`, `models_dir`, `content_dir`, `mlruns_dir`, `log_dir`, `backup_dir`, `api_key_path`) are stored as rows in the per-instance `runtime_config` table — NOT in the boot file (which stays minimal, §1).
- **apply_class = `boot_critical`**: these paths are read during startup (after the DB opens but before the services that use them initialize), so an edit takes effect only on the next instance start and is surfaced as **pending restart** like any other boot-critical setting.
- **Resolution**: at startup, after `init_engine()` opens the DB, `WorkspacePaths` is constructed from `workspace_root` and then **overlaid** with any per-location overrides found in `runtime_config` (override > workspace-derived default > env). The four boot-file keys are never sourced from the DB (chicken-and-egg).
- **Why not the boot file**: only `state_db_path`/`workspace_root`/`web_port`/`mlflow_port` must be known *before* the DB opens; every other path is needed *after*, so the DB is the correct, boring home for them and keeps the boot file to four keys.

**Repository** (`anvil/db/repositories/runtime_config.py`, `RuntimeConfigRepository(session)`): `get(key)`, `get_all()`, `upsert(key, value, apply_class)`, `delete(key)` — async, `flush()`/`refresh()` per convention.

---

## 4. `InstanceRecord` (ORM — global registry DB)

File: `anvil/db/models/instance_record.py`. Table: `instance_records`. Lives in the **global** host-level DB (`~/.anvil/registry.db`), NOT a per-instance DB. Authoritative for identity + collision; **liveness is derived, not stored**.

| Column | Type (DB) | Notes |
|---|---|---|
| `id` | `Integer` PK autoincrement | |
| `name` | `String(100)` **unique**, indexed | Instance identifier (FR-023a). |
| `workspace_root` | `String(500)` **unique** | Collision target (FR-020). |
| `web_port` | `Integer` **unique** | Collision target (FR-019). |
| `mlflow_port` | `Integer` **unique** | Collision target (FR-019). |
| `created_at` / `updated_at` | `DateTime` | via `TimestampMixin`. |

**Unique constraints**: `name`, `workspace_root`, `web_port`, `mlflow_port` each unique → atomic collision detection on insert (research.md F). Overlap/nesting of workspace paths is checked in the service layer beyond the exact-match DB constraint.

**Not stored**: `status` (running/stopped/unhealthy) — recomputed on read via PID-file + process + port probe to avoid stale truth after crashes.

**Repository** (`anvil/db/repositories/instance_registry.py`, `InstanceRegistryRepository(session)`): `register(record)` (raises on unique violation → mapped to a clear collision error), `get_by_name(name)`, `list_all()`, `deregister(name)`, `find_port_conflict(web, mlflow)`, `find_workspace_conflict(root)`.

---

## 5. `WorkspaceLock` (on disk — `anvil/services/instances/workspace_lock.py`)

Not a DB row. A lock marker at `{workspace_root}/.anvil-lock` recording the owning PID (and start time). Acquire on start; release on clean stop. Stale-lock reclamation (FR-021, edge case): on a start attempt, if the recorded PID is no longer alive → reclaim automatically; if alive → refuse start.

---

## 6. Enums (StrEnum — service layer)

| Enum | File | Values |
|---|---|---|
| `ApplyClass` | `services/runtime_config/apply_class.py` | `BOOT_CRITICAL = "boot_critical"`, `MLFLOW_RESTART = "mlflow_restart"`, `APPLIES_LIVE = "applies_live"` |
| `ConfigSource` | `services/runtime_config/config_source.py` | `DEFAULT = "default"`, `ENV = "env"`, `OVERRIDE = "override"` |
| `InstanceStatus` | `services/instances/instance_status.py` | `RUNNING = "running"`, `STOPPED = "stopped"`, `UNHEALTHY = "unhealthy"` |

**Audit enum extensions** (reuse existing `AuditAction`/`AuditTargetType`, FR-029):
- `AuditAction` += `CONFIG_SET`, `CONFIG_RESET`, `INSTANCE_CREATE`, `INSTANCE_START`, `INSTANCE_STOP`, `INSTANCE_RESTART`, `INSTANCE_DESTROY`
- `AuditTargetType` += `RUNTIME_CONFIG`, `INSTANCE`

---

## 7. `ConfigSetting` (value object — `services/runtime_config/config_setting.py`)

Pydantic `BaseModel` returned by `RuntimeConfigService` to the API/UI (FR-010). Fields: `key: str`, `value: str`, `source: ConfigSource`, `apply_class: ApplyClass`, `pending_restart: bool` (computed via the startup-snapshot diff, research.md D), `editable: bool`.

---

## 8. Migrations

Follow the verified pattern (`anvil/_resources/migrations/versions/NNN_*.py`; `revision`/`down_revision`; `op.create_table` + `op.create_index` in `upgrade`, drops in `downgrade`).

- **Per-instance app DB**: new migration `NNN_add_runtime_config.py` creating `runtime_config` (unique index on `key`). Bump `SCHEMA_VERSION` only if migrations are squashed (per convention).
- **Global registry DB**: initialized at first registry use. Create `instance_records` with the four unique constraints/indexes. Managed by its own lightweight migration/bootstrap against `~/.anvil/registry.db` (kept separate from the per-instance Alembic chain; see research.md F and the plan's Complexity Tracking).

---

## Entity relationships

```text
Global host-level registry DB (~/.anvil/registry.db)
└── instance_records (1 row per instance; unique name/workspace/web_port/mlflow_port)

Per instance (rooted at workspace_root):
├── instance.json            (boot file — authoritative boot-critical values)
├── .anvil-lock              (WorkspaceLock — PID-validated exclusivity)
├── data/anvil-state.db      (per-instance app DB)
│   └── runtime_config       (editable non-boot settings; layered over env+defaults)
├── data/{datasets,storage,models,content,backups,.api_key}
├── mlruns/{mlflow.db,...}
└── logs/{web.pid,mlflow.pid,*.log}
```

Each `InstanceRecord.name` ↔ one workspace ↔ one boot file ↔ one per-instance DB. The registry sees all; no instance DB sees another.

## Terminology mapping (spec → implementation)

The spec uses conceptual names; the implementation uses these concrete names:

| Spec (conceptual) | Implementation |
|---|---|
| `InstanceConfig` entity | `RuntimeConfig` ORM / `runtime_config` table + `ConfigSetting` value object |
| `InstanceRegistry` | `InstanceRecord` ORM + `InstanceRegistryRepository` (`~/.anvil/registry.db`) |
| "tracking port" / "experiment-tracking sidecar" | `mlflow_port` / MLflow sidecar (`MLflowService`) |
| `Instance.identifier` | `InstanceRecord.name` (caller-provided, unique) |
