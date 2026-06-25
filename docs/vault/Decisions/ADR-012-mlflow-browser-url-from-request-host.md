---
title: 'ADR-012: Derive MLflow Browser URL from HTTP Request Host Header'
type: decision
tags:
  - type/decision
  - domain/mlops
  - domain/ui
status: accepted
created: '2026-06-15'
updated: '2026-06-15'
aliases:
  - mlflow-browser-url-from-request-host
source: agent
code-refs:
  - anvil/services/tracking/
---
# ADR-012: Derive MLflow browser URL from HTTP request Host header

**Status**: Accepted

## Context

The UI surfaces MLflow links in three places:
1. Operations page — `[open]` link next to the MLflow service status
2. Experiments list — `mlflow_url` per experiment and `mlflow_run_url` per run
3. Experiment detail — `run_url` inside the MLflow data block

Previously these URLs were constructed from `get_mlflow_uri()`, whose value was set by `MLflowService._detect_lan_ip()` at startup. `_detect_lan_ip` connected a UDP socket to `1.1.1.1:80` and read back `getsockname()[0]` — a common trick for finding the default-route interface IP. The result was stored globally via `set_resolved_mlflow_uri()`.

This approach broke on networks where the UDP default route resolves to a gateway or bridge address rather than the machine's LAN IP (observed on macOS Sequoia with VPN or bridged networking active). The symptom was browser clicks on MLflow links opening connections to the wrong host.

## Decision

Introduce `get_mlflow_browser_uri(request: Request) -> str` in `anvil/config.py`. It:

1. Reads the `Host` HTTP header from the incoming request (e.g. `192.168.1.10:8080`)
2. Strips the port component to get the bare hostname (`192.168.1.10`)
3. Appends the configured MLflow port (`mlflow_port` from config, default `5001`)
4. Returns `http://{hostname}:{mlflow_port}`

All three endpoints that return MLflow links are updated to accept `fastapi.Request` and call this helper.

`_detect_lan_ip()` is removed entirely. `set_resolved_mlflow_uri()` is retained (it is still valid for programmatic overrides) but is no longer called by the supervisor on startup.

### Separation of concerns

| Use case | Function | Value |
|---|---|---|
| Internal `MlflowClient` connections (server-to-server) | `get_mlflow_uri()` | `http://127.0.0.1:5001` |
| Browser-facing links returned in API responses | `get_mlflow_browser_uri(request)` | `http://{request_host}:{mlflow_port}` |

### Files changed

| File | Change |
|---|---|
| `anvil/config.py` | Added `get_mlflow_browser_uri(request)` |
| `anvil/supervisor/services.py` | Removed `_detect_lan_ip()`, removed `set_resolved_mlflow_uri` call, removed `socket` import |
| `anvil/api/v1/router.py` | `/services` endpoint uses `get_mlflow_browser_uri(request)` |
| `anvil/api/v1/experiments.py` | `list_experiments`, `get_experiment`, `get_experiment_mlflow` use `get_mlflow_browser_uri(request)` |
| `tests/unit/test_config.py` | 4 new tests for `get_mlflow_browser_uri` |

## Consequences

- **Positive**: Links always resolve correctly regardless of network topology — the user's browser is already successfully connected to the web UI, so reusing that hostname is guaranteed correct.
- **Positive**: Removes the non-deterministic `_detect_lan_ip()` startup side-effect.
- **Positive**: `get_mlflow_uri()` and `get_mlflow_browser_uri()` now have clearly separate responsibilities.
- **Positive**: Works correctly for all access patterns: `localhost`, LAN IP, hostname, or custom domain.
- **Neutral**: `set_resolved_mlflow_uri()` is kept but is now only callable programmatically (e.g. for testing or future tooling). It is no longer part of the startup path.
- **Negative**: None — the `request` object is freely available in every FastAPI endpoint.

## See Also

- [[Decisions/README|Decisions]]
