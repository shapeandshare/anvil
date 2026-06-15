## Session: Fix MLflow browser URL — derive from request Host header

**Date**: 2026-06-15

### Problem

MLflow links in the UI (operations page `[open]` links, experiment detail run URLs, and the experiments list) were pointing to the network **gateway IP** instead of the local IP the user accessed the web UI through.

Root cause: `MLflowService._detect_lan_ip()` in `anvil/supervisor/services.py` used a UDP connect trick (`socket.connect("1.1.1.1", 80)`) to discover the outbound interface IP. On networks with non-trivial routing (VPNs, bridged adapters, macOS Sequoia network stack changes), this resolved to the gateway/wrong IP rather than the machine's LAN address. The detected IP was stored globally via `set_resolved_mlflow_uri()` and used for all browser-facing links.

### Decision

Replace all backend IP detection with request-derived hostname. A new helper `get_mlflow_browser_uri(request: Request)` in `anvil/config.py` strips the port from the `Host` HTTP header and replaces it with the configured MLflow port. This ensures links always resolve relative to the hostname the user actually typed — no guessing.

See [[Decisions/ADR-012-mlflow-browser-url-from-request-host]].

### Key Observations

- `get_mlflow_uri()` (used by `MlflowClient` inside the Python process) is unaffected — it still returns `http://127.0.0.1:5001` for all internal server-to-server calls.
- The two concerns are now cleanly separated: internal client URI vs. browser-facing link URI.
- `_detect_lan_ip()` was the only user of `socket` in `services.py` — removing it also removes that import.
- `set_resolved_mlflow_uri()` is retained for backward compatibility but is no longer called by the supervisor.
- The operations page already had a JS fallback using `window.location.hostname` — the backend now always produces the correct value and that fallback is consistent.

### Files Changed

- `anvil/config.py` — added `get_mlflow_browser_uri(request)`, cleaned up stale comment on `set_resolved_mlflow_uri`
- `anvil/supervisor/services.py` — removed `_detect_lan_ip()`, removed `set_resolved_mlflow_uri` call from `start()`, removed `socket` import
- `anvil/api/v1/router.py` — `/services` uses `get_mlflow_browser_uri(request)`
- `anvil/api/v1/experiments.py` — `list_experiments`, `get_experiment`, `get_experiment_mlflow` all accept `Request` and use `get_mlflow_browser_uri(request)` for link construction
- `tests/unit/test_config.py` — 4 new tests covering LAN IP, localhost, hostname-only, and bare IPv4 host headers

### Vault Enrichment

- Created [[Decisions/ADR-012-mlflow-browser-url-from-request-host]]
- Updated [[Reference/DecisionLog]]
