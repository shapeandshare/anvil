---
title: ADR-042 Two-Layer Config Model and Global Instance Registry
type: decision
tags:
  - type/decision
  - domain/operations
  - domain/infrastructure
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - adr-042-two-layer-config
source: agent
code-refs:
  - anvil/services/runtime_config/runtime_config_service.py
  - anvil/db/repositories/instance_registry.py
---

# ADR-042: Two-Layer Config Model and Global Instance Registry

## Context

Feature 028 (Concurrent Isolated Instances) requires running N fully isolated copies of the anvil stack on a single host. Each instance needs its own ports, database, storage paths, and writable runtime configuration. Two fundamental chicken-and-egg problems emerged:

1. **Config boot-strapping**: boot-critical values (web port, MLflow port, DB path, workspace root) must be known *before* the per-instance DB opens and the port binds. They cannot live solely in the DB they gate.
2. **Cross-instance identity**: the instance registry (names, ports, workspaces) must be visible to *all* instances for collision detection — it cannot live in any single per-instance DB.

## Decision

### A — Two-layer config model

1. **Boot file** (`instance.json`): a minimal JSON file in the workspace root holding the four boot-critical keys (`name`, `workspace_root`, `web_port`, `mlflow_port`, `state_db_path`). Authoritative persisted source. Loaded before any DB operation.
2. **DB-backed `runtime_config` table**: in each instance's per-instance app DB. Stores editable non-boot settings (rate limits, device, quotas, per-location path overrides). Layered as: `override > env-var > code-default`.

This breaks the chicken-and-egg: the boot file provides the values needed to open the DB; the DB provides everything else.

### B — Global SQLite registry

A separate SQLite database at `~/.anvil/registry.db` with four unique constraints (name, workspace_root, web_port, mlflow_port). Provides atomic collision detection. Lives at the host level, not inside any instance. Liveness is recomputed from PID/process probes — never stored as authoritative truth.

## Status

Accepted (applies to feature 028).

## Consequences

**Positive**:
- Clean separation between boot-critical and runtime-editable config
- Atomic collision detection via SQLite unique constraints
- No new infrastructure (uses existing SQLAlchemy/Alembic)

**Negative**:
- The boot file introduces ONE new filesystem artifact (`.specify/templates/plan-template.md` previously tracked zero)
- The global registry DB is a new state file outside the per-instance workspace

**Risks**:
- Path-isolation regression: a single CWD-relative hardcoded path bypasses workspace isolation. Mitigation: path-isolation audit (FR-018) is a first-class task.
- Stale registry state after crashes: mitigated by recomputing liveness from PID/port probes, never trusting stored status.

## Alternatives Considered

- **All config in env vars**: rejected — requires caller to pass or persist env per-instance, no CRUD, no UI.
- **All config in the DB**: impossible for boot-critical values (chicken-and-egg).
- **JSON-file registry without constraints**: rejected — no atomic uniqueness guarantee.
- **Directory-scanning registry**: rejected — slow, race-prone, no atomic collision detection.