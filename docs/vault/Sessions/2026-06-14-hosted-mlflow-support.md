## Session: Hosted MLflow support — disable local server

**Date**: 2026-06-14

### Work Done

Implemented `ANVIL_MLFLOW_DISABLE_LOCAL` env var to allow users to disable the locally-managed MLflow server when connecting to a hosted/remote MLflow service.

### Key Decisions

- Explicit env var only — no auto-detection based on URI. A remote URI alone does NOT disable local server to avoid surprising users using LAN IPs.
- All MLflow connectivity was already URI-driven (`ANVIL_MLFLOW_URI`), so no changes to `TrackingService` or routes were needed beyond the conditional server spawn.
- MLflow's native auth env vars (`MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD`, `MLFLOW_TRACKING_TOKEN`) work without application code changes.

### Files Changed

- `anvil/config.py` — added `mlflow_disable_local` config key
- `anvil/api/app.py` — conditional `MLflowService` start in lifespan
- `anvil/api/v1/router.py` — `/services` shows `"external"` status
- `anvil/cli.py` — `stop()` skips MLflow cleanup when disabled
- `.env.example` — documented `ANVIL_MLFLOW_DISABLE_LOCAL`
- `tests/unit/test_config.py` — 4 new tests

### Vault Enrichment

- Created [[Decisions/ADR-010-disable-local-mlflow-server]]
- Updated [[Reference/DecisionLog]]