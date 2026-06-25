---
title: 'ADR-010: Hosted MLflow Support — Disable Local Server'
type: decision
tags:
  - type/decision
  - domain/mlops
status: accepted
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - disable-local-mlflow-server
source: agent
code-refs:
  - anvil/services/tracking/
  - shared/tracking.mk
---
# ADR-010: Hosted MLflow support — disable local server

**Status**: Accepted

## Context

ADR-004 established a canonical HTTP-server tracking URI (`ANVIL_MLFLOW_URI`) driving both writers and readers. However, the local `mlflow server` subprocess was spawned unconditionally in the FastAPI lifespan. This prevented users from pointing the application at a hosted/remote MLflow service (e.g. Databricks MLflow, a shared team server) without also running a redundant local `mlflow server`.

## Decision

Add an explicit `ANVIL_MLFLOW_DISABLE_LOCAL` env var (default `false`) that controls whether the `MLflowService` subprocess is spawned on app startup.

- When `false` (or unset): existing behavior — `MLflowService` spawns a local `mlflow server` subprocess
- When `true`: the supervisor skips `MLflowService` entirely; `app.state.mlflow` is `None`
- All `TrackingService`/`MlflowClient` calls continue to work because they connect to whatever URI is in `ANVIL_MLFLOW_URI`
- Authentication is handled by MLflow's native env vars (`MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD`, `MLFLOW_TRACKING_TOKEN`) — no application code changes needed
- No auto-detection: a remote URI alone does NOT disable local — the user must set the env var. This avoids surprising behavior when using LAN IPs (e.g. `http://192.168.1.50:5001` which is common for LAN access but is technically not localhost)

### Files changed

| File | Change |
|---|---|
| `anvil/config.py` | Added `mlflow_disable_local` key to config dict from `ANVIL_MLFLOW_DISABLE_LOCAL` env var |
| `anvil/api/app.py` | Lifespan conditionally creates/starts `MLflowService`; shutdown uses `getattr` guard |
| `anvil/api/v1/router.py` | `/services` endpoint shows `"external"` status when local MLflow is disabled |
| `anvil/cli.py` | `stop()` skips MLflow PID file kill and port-scan when disabled |
| `.env.example` | Documented the new env var |
| `tests/unit/test_config.py` | 4 new tests covering default, explicit true, explicit false, remote-URI-without-flag |

## Consequences

- **Positive**: Users can now run with a hosted MLflow service by setting two env vars (`ANVIL_MLFLOW_URI` + `ANVIL_MLFLOW_DISABLE_LOCAL=true`)
- **Positive**: No changes needed to `TrackingService` or any route — all MLflow connectivity was already URI-driven
- **Positive**: The operations page shows `"external"` status, making the disabled state visible
- **Positive**: Explicit-only opt-in avoids the footgun of auto-detecting LAN IPs as "remote"
- **Negative**: Service management endpoints (start/stop/restart for MLflow) return 500 when local is disabled — user must manage the remote server separately

## See Also

- [[Decisions/README|Decisions]]
