# Contract: Health Endpoint Tracking Block

## Endpoint

`GET /v1/health/detailed` (authenticated)

## Tracking Block Shape

Add a `tracking` block to the existing response alongside the existing sections (`system`, `gpu`, `database`, `mlflow`, `docs`).

```json
{
  "status": "healthy",
  "version": "0.x.x",
  "uptime_seconds": 1234,
  "system": { "...": "..." },
  "gpu": { "...": "..." },
  "database": { "...": "..." },
  "mlflow": {
    "status": "reachable",
    "error": null
  },
  "tracking": {
    "status": "active",
    "reason": null,
    "message": "",
    "last_attempt": null
  },
  "docs": { "...": "..." }
}
```

## States

### Active (healthy)
```json
{
  "tracking": {
    "status": "active",
    "reason": null,
    "message": "",
    "last_attempt": null
  }
}
```

### Degraded — Unreachable (transient, may retry)
```json
{
  "tracking": {
    "status": "degraded",
    "reason": "unreachable",
    "message": "MLflow server is unreachable. Automatic retry in progress.",
    "last_attempt": 1719690000.0
  }
}
```

### Degraded — Auth Failure (permanent, no retry)
```json
{
  "tracking": {
    "status": "degraded",
    "reason": "auth_failure",
    "message": "MLflow server rejected credentials (HTTP 403). Check ANVIL_MLFLOW_URI configuration.",
    "last_attempt": 1719690000.0
  }
}
```

### Degraded — Version Incompatibility (permanent, no retry)
```json
{
  "tracking": {
    "status": "degraded",
    "reason": "incompatible_version",
    "message": "MLflow server version is incompatible. Required: MLflow 2.x or later.",
    "last_attempt": 1719690000.0
  }
}
```

### Degraded — Permanent Error (no retry)
```json
{
  "tracking": {
    "status": "degraded",
    "reason": "permanent_error",
    "message": "Tracking encountered a permanent error. Manual intervention required.",
    "last_attempt": 1719690000.0
  }
}
```

## Frontend Consumption

The `GET /v1/health/detailed` response is consumed by:
1. **Training page** (`archetypes/training.html`) — fetches `/v1/health/detailed` during page init
2. **Operations page** (`operations.html`) — fetches `/v1/health/detailed` + `/v1/services`
3. **Experiments page** (`archetypes/experiment.html`) — fetches health data

Frontend should read `response.tracking.status` and `response.tracking.message` to populate the degraded banner.

## Bare Health Endpoint

`GET /v1/health` (unauthenticated, Docker healthcheck)

No change — returns `{"status": "healthy"}` only.