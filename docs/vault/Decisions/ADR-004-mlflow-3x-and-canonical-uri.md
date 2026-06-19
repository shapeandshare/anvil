---
title: ADR-004 — MLflow 3.x bump and canonical HTTP-server tracking URI
type: decision
tags:
- type/decision
- domain/tracking
created: 2026-06-13
updated: 2026-06-13
aliases:
- ADR-004 — MLflow 3.x bump and canonical HTTP-server tracking URI
source: agent
---

# ADR-004: MLflow 3.x bump and canonical HTTP-server tracking URI

**Status**: Accepted

## Context

The project shipped `mlflow>=2.16,<3` with the tracking URI hardcoded as `sqlite:///./mlruns/mlflow.db` in four places, while `get_config()["mlflow_uri"]` was dead code. MLflow 2.x lacks `mlflow.genai` managed evaluation datasets (US6).

## Decision

- Bump `mlflow>=3.1,<4` (resolved: 3.13.0) — enables `mlflow.genai.datasets`
- Single canonical tracking destination: `MICROGPT_MLFLOW_URI=http://127.0.0.1:5000` (HTTP server)
- The sqlite file `mlruns/mlflow.db` is the server's `--backend-store-uri` only; no client opens it directly
- All four hardcoded URI literals removed; all clients read `get_config()["mlflow_uri"]`

## Consequences

- `mlflow.genai.datasets` works on self-hosted SQLite-backed OSS MLflow (NOT Databricks-only, verified)
- HTTP server avoids multi-process SQLite write contention
- `MICROGPT_MLFLOW_URI` env var now actually controls the tracking destination end-to-end