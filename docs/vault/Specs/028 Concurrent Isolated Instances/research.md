---
title: 'Research: Concurrent Isolated Instances'
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
  - 028 Concurrent Isolated Instances - research
---

# Research: Concurrent Isolated Instances

Phase 0 output. All decisions below were resolved via an architecture review (Oracle) against verified codebase facts. There are **no open NEEDS CLARIFICATION** items.

## Verified codebase facts (inputs to the decisions)

1. `anvil/config.py` `get_config()` is `@lru_cache`, env-driven, static after first call; only `set_resolved_mlflow_uri()` mutates at runtime.
2. `anvil/db/session.py` reads `get_config()["state_db_path"]` and builds the async engine + URL **at module import time** — DB path is baked before any request.
3. ~5 write paths bypass config and resolve relative to CWD: `data/datasets`, `data/storage`, `data/models`, `mlruns`, `data/.api_key`.
4. No workspace-root concept; all paths resolve from `Path.cwd()` independently.
5. Web server is a blocking `uvicorn.run("anvil.api.app:app", ...)` (cli.py `serve()`) — cannot self-restart in-process. MLflow runs as a managed subprocess (`MLflowService`) and is restartable.
6. CLI is argparse; sync def → `asyncio.run(_run())`; `async with AsyncSessionLocal() as session: wb = AnvilWorkbench(session)`. Console scripts in `pyproject [project.scripts]`.
7. No settings/KV table exists. Audit infra exists (`AuditEvent` + `AuditService.record(action_type, target_type, target_id, actor, outcome, params)`); `AuditAction`/`AuditTargetType`/`AuditOutcome` are `StrEnum`s.

---

## Decision A — Bootstrap & config layering

**Decision**: **Two-layer (hybrid)**. A per-workspace **`instance.json` boot file** is the authoritative persisted source for the boot-critical keys (`workspace_root`, `web_port`, `mlflow_port`, `state_db_path`). The per-instance **DB `runtime_config` table** stores only non-boot, editable settings (rate limits, device, quotas, CORS, etc.), layered over env + code defaults. CLI flags are for create/edit/start *selection*, not the steady-state source of truth.

**Precedence (managed instances)**: `instance name → global registry → workspace path → workspace boot file → code defaults`, then overlay **DB runtime config** for non-boot settings only. Ad-hoc env vars MUST NOT override boot-critical keys in managed mode (env stays the mechanism for legacy single-instance/dev runs).

**Rationale**: Boot-critical values must be known before the DB opens and the port binds, so they cannot live solely in the DB they gate. The boot file is the minimum extra state to break the chicken-and-egg cleanly.

**Alternatives considered**: (a2) everything boot-critical via CLI/env only — rejected: not persistent across restarts, fragile. (a3) all config in DB — impossible for boot-critical keys.

---

## Decision B — Workspace-root threading & the import-time DB read

**Decision**: **b1 + treat the import-time DB read as a mandatory fix.** Introduce a `BootConfig`/`WorkspacePaths` object resolved **before** app bootstrap; convert `db/session.py` from import-time engine creation to an explicit `init_engine(paths)`/factory step; change every hardcoded path (the ~5 above + MLflow backend-store URI) to derive from `workspace_root`. Starting each process with `cwd=workspace` is allowed only as **belt-and-suspenders**, never as the isolation contract.

**Rationale**: Explicit workspace-root derivation is the only reliable way to prevent cross-instance data leakage. CWD-based isolation is too fragile — import-time singletons, future `resolve()`-at-import, and subprocess behavior bypass it. Fixing the import-time DB read is unavoidable regardless of approach.

**Alternatives considered**: (b2) CWD-only isolation — rejected as fragile and untestable as a guarantee (violates §11.6).

**Traps to avoid** (flagged): anything resolving absolute paths at import; the MLflow backend-store URI currently built at import; any module-level singleton that reads config once.

---

## Decision C — Config mutability vs `@lru_cache`

**Decision**: **c1 — keep `get_config()` immutable; add a separate DB-backed `RuntimeConfigService`** for live-editable settings, read per-request with no `lru_cache`.

**Rationale**: Keeps blast radius small, preserves all existing assumptions around `@lru_cache`, and is independently testable. Mutating `get_config()` would ripple through every consumer.

**Alternatives considered**: (c2) make `get_config()` cache-busting/mutable — rejected: large blast radius, harder to reason about and test.

**Escalation**: if non-boot reads become hot, add narrow caching/invalidation *inside* `RuntimeConfigService`, never by mutating `get_config()`.

---

## Decision D — "Pending restart" mechanism

**Decision**: At process start, capture a **snapshot of the effective boot config in `app.state`**. Compute `pending_restart` for a setting by comparing the *saved desired* value (boot file / DB) against that startup snapshot. Surface the diff in the UI as a pending-restart summary.

**Rationale**: With no guardian process and a blocking `uvicorn.run`, a pure comparison of "saved desired vs value captured at boot" is the simplest honest signal. No magic, fully testable.

**Pitfall flagged**: if boot-critical settings are mirrored into the instance DB for UI display, the **boot file must remain authoritative** or startup split-brain reappears. The DB mirror (if any) is display-only.

---

## Decision E — Single-instance web restart from CLI

**Decision**: `anvil instance restart <name>` = `SIGTERM` the recorded **process group** → wait for exit / port release → `Popen(..., start_new_session=True, cwd=workspace)` with that instance's boot environment. **Verify the recorded PID belongs to that workspace before killing it.**

**Rationale**: Matches the existing supervisor/PID-file pattern; boring and correct for ≤ ~10 instances without a long-running daemon. `start_new_session=True` detaches cleanly.

**Alternatives considered**: a long-running guardian/supervisor process — rejected per clarification and YAGNI; revisit only if instance count grows well past ~10 or restart/liveness becomes flaky.

---

## Decision F — Registry location

**Decision**: **f2 — a small global SQLite registry DB at a host-level path** (e.g. `~/.anvil/registry.db`) with **unique constraints** on instance name, workspace path, web port, and MLflow port. Live status is **recomputed** from pidfile/process/port probes, not stored as authoritative state.

**Rationale**: The registry is inherently cross-instance, so it can't live in a per-instance DB. A global SQLite DB gives atomic collision detection with boring, well-understood tooling already in the stack. Identity/collision are authoritative in the registry; **liveness is derived** to avoid stale truth after crashes.

**Alternatives considered**: (f1) JSON file + file lock — workable but unique-constraint enforcement is manual/race-prone. (f3) directory scan + probe with no store — no atomic uniqueness guarantee. Both rejected for correctness.

---

## Biggest risk (carry into tasks & review)

**Hidden process-global state or a missed hardcoded path causing cross-instance leakage.** One overlooked import-time singleton or `Path.cwd()`-relative write breaks isolation silently. Mitigation: the **path-isolation audit (FR-018)** is a first-class task — enumerate and prove every write location derives from `WorkspacePaths`, backed by the multi-process isolation e2e test (`tests/e2e/test_instance_isolation.py`). Registry must be authoritative for identity/collision only; status always recomputed.
