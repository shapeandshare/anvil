# Contract: docker compose orchestration

**Feature**: `009-pip-installable-package`

Defines the contract for the new root `compose.yaml`. Single service, in-process MLflow (Q2), persistent named volume (Q4).

> **Port-publishing superseded (2026-06-28)**: The `"5001:5001"` publish line and
> requirement R-C2 below are SUPERSEDED by Spec 024 / Spec 056 (ADR-037 single-origin
> front door). Once Spec 056 lands, MLflow binds loopback-only and its port is NOT
> published — `ports:` MUST list only `"8080:8080"`, and MLflow is reachable solely via
> the authenticated `/v1/mlflow-proxy/`. The `5001` line is retained below for historical
> contract context only. See `docs/vault/Specs/056 Reverse-Proxy Registry/`.

## Structure (normative)

```yaml
services:
  anvil:
    build:
      context: .
      target: runtime
    image: anvil:local
    ports:
      - "8080:8080"   # web
      - "5001:5001"   # in-process MLflow
    volumes:
      - anvil-workspace:/workspace
    working_dir: /workspace
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/v1/health').status==200 else 1)"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 30s

volumes:
  anvil-workspace:
```

> Healthcheck uses Python stdlib (always present in the image) rather than `curl` (not guaranteed in slim).

## Requirements

- R-C1: Exactly one service (`anvil`); MLflow runs in-process inside it (Q2) — no separate MLflow service.
- R-C2: Port 8080 published. ~~5001 published~~ — **SUPERSEDED by Spec 024/056**: MLflow port 5001 is NOT published (loopback-only behind `/v1/mlflow-proxy/`). (FR-008, as amended.)
- R-C3: Runtime workspace backed by a **named volume** so state persists across restarts (FR-011a, Q4).
- R-C4: Healthcheck polls `/v1/health`; `docker compose up --wait` blocks until healthy (VR-O1).
- R-C5: No `version:` top-level key (Compose Spec).
- R-C6: `docker compose down -v` removes the volume → next `up` is a fresh first-run (Q4, FR-011a).

## Acceptance checks

| ID | Check | Maps to |
|----|-------|---------|
| CMP-1 | `docker compose up -d --build --wait` reports the service healthy | US3, FR-008 |
| CMP-2 | Workbench reachable at `http://localhost:8080/` after up | SC-004 |
| CMP-3 | State (DB) persists across `docker compose restart` | FR-011a |
| CMP-4 | `docker compose down -v` then `up` re-runs first-run init (migrate + bootstrap) | Q4, FR-011a |
