---
title: 'Quickstart: Concurrent Isolated Instances'
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
  - 028 Concurrent Isolated Instances - quickstart
---

# Quickstart: Concurrent Isolated Instances

This walkthrough shows a coding agent running **two fully isolated instances** side by side, targeting each independently, editing config in the UI, and tearing one down — proving the core value (US1–US5).

> Commands are illustrative of the contracts in `contracts/`. The default (no-instance) `make run` path is unchanged (FR-028, SC-008).

## 1. Create two isolated instances (CLI-first)

```bash
# Auto-allocated ports (default), distinct workspaces
anvil-instance create agent-a --workspace ~/anvil-work/agent-a
#   → created 'agent-a'  web_port=8211  mlflow_port=8212

anvil-instance create agent-b --workspace ~/anvil-work/agent-b
#   → created 'agent-b'  web_port=8213  mlflow_port=8214
```

Each writes `~/anvil-work/<name>/instance.json` (boot file) and registers a row in the global registry (`~/.anvil/registry.db`). Duplicate names, ports, or overlapping workspaces are rejected with a specific message (FR-019/FR-020/FR-023a).

## 2. Start both, confirm health

```bash
anvil-instance start agent-a
anvil-instance start agent-b
anvil-instance list
#  NAME      WORKSPACE                 WEB   MLFLOW  STATUS
#  agent-a   ~/anvil-work/agent-a      8211  8212    running
#  agent-b   ~/anvil-work/agent-b      8213  8214    running
```

Status is probed live (PID/process/port), not read from stored state. Each instance serves its own UI at its own port:
- `http://localhost:8211` → agent-a
- `http://localhost:8213` → agent-b

## 3. Prove isolation (US1, SC-001/SC-002)

Write distinct data into each (upload a dataset, train a model) via its own URL/UI. Then:

```bash
# All of agent-a's data lives under its workspace — nothing leaks to agent-b
ls ~/anvil-work/agent-a/data    # anvil-state.db datasets/ storage/ models/ content/ .api_key
ls ~/anvil-work/agent-a/mlruns  # mlflow.db + runs
```

Stop or kill agent-a; agent-b keeps serving uninterrupted with no corruption (SC-002):

```bash
anvil-instance stop agent-a
curl -sk https://localhost:8213/v1/health   # agent-b still {"status":"healthy"}
```

## 4. Edit config in the UI + restart to apply (US2/US3)

Open agent-b's UI → **Config** tab (`/v1/config-page`):

- Change a **live/MLflow** setting (e.g. an MLflow-related option) → saves and applies; MLflow sidecar auto-restarts; toast confirms (FR-016).
- Change a **boot-critical** setting (e.g. `web_port`) → saved to the boot file, marked **pending restart**; the banner shows the action required (FR-017). Apply it:

```bash
anvil-instance restart agent-b   # stop + start; new boot config takes effect; pending clears
```

Invalid edits (bad port, a port already used by agent-a, colliding workspace) are rejected inline with a specific message and nothing is persisted (FR-013).

## 5. Target instances independently (agents)

An agent discovers and targets instances via the registry + each instance's base URL — independent of any other instance's state (FR-004, FR-027):

```bash
anvil-instance list --json   # machine-readable: names, ports, workspaces, live status
# → POST training/datasets to http://localhost:8213 for agent-b only
```

## 6. Destroy (US4 — destructive default)

```bash
anvil-instance destroy agent-a --yes
#   → instance 'agent-a' unregistered; workspace data DELETED.

# Keep the data, just unregister:
anvil-instance destroy agent-b --keep-data --yes
#   → instance 'agent-b' unregistered; workspace data PRESERVED at ~/anvil-work/agent-b.
```

Destroy requires the instance stopped (or `--force`) and explicit confirmation; the result states clearly whether data was deleted or preserved (FR-026). Every step above is recorded in the per-instance audit log (FR-029).

## Verification checklist (maps to Success Criteria)

- [ ] Two instances run concurrently; data written to one is invisible to the other (SC-001).
- [ ] Killing one leaves the other healthy and uncorrupted (SC-002).
- [ ] Config view + edit in UI under 1 min; change persists to that instance only (SC-003).
- [ ] Every saved setting is either applied (with status) or flagged pending — never silent (SC-004).
- [ ] Full create→start→health→stop→destroy works from CLI alone (SC-005).
- [ ] Port/workspace collisions rejected before any bind/write (SC-006).
- [ ] Path-isolation audit: 100% of writes resolve under the workspace root (SC-007).
- [ ] `make run` with no instance config still works as a single default instance (SC-008).
- [ ] ≥10 instances run concurrently without conflict (SC-009).
