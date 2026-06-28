---
title: MLflow Reverse Proxy Route Contract
type: spec
tags:
  - type/spec
  - domain/infrastructure
  - domain/mlops
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# MLflow Reverse Proxy Route Contract

Governed by FR-057 and ADR-035.

## Route

```
/v1/mlflow-proxy/{path:path}
```

## Upstream Target

| Mode | Target | Source |
|------|--------|--------|
| Local | `http://127.0.0.1:5001` | `ANVIL_MLFLOW_INTERNAL_URI` default |
| SaaS | `http://mlflow.svc.local:5000` | `ANVIL_MLFLOW_INTERNAL_URI` default (Cloud Map) |

## Auth Requirements

| Property | Value |
|----------|-------|
| **Authentication** | Cognito JWT (same as all `/v1/*` endpoints) |
| **Unauthenticated response** | `401 Unauthorized` |
| **RBAC** | Same org-scoped RBAC — proxy does not filter experiments, app layer controls visibility |

## Request Handling

| Property | Value |
|----------|-------|
| **Method** | All HTTP methods forwarded |
| **Path forwarding** | Full `{path}` + query string forwarded to upstream |
| **Headers** | All headers forwarded except `Host` (rewritten to upstream target) |
| **Body** | Streamed (no buffering for large artifact downloads) |
| **Timeout (UI pages)** | 60s |
| **Timeout (artifact downloads)** | 300s |
| **Transfer-Encoding** | `chunked` pass-through for streaming responses |

## MLflow Server Configuration

| Property | Value |
|----------|-------|
| **Static prefix flag** | `--static-prefix=/v1/mlflow-proxy` |
| **Bind address (local)** | `127.0.0.1` only (NOT `0.0.0.0`) |
| **Host port (local)** | Not published (internal only) |
| **Bind address (SaaS)** | Private subnet, Cloud Map DNS only |

## MLflow SPA URL Resolution

MLflow's SPA emits absolute AJAX paths (`/ajax-api/2.0/mlflow/...`) and
static asset paths (`/static-files/...`). With `--static-prefix=/v1/mlflow-proxy`:

- AJAX calls resolve to `/v1/mlflow-proxy/ajax-api/2.0/mlflow/...`
- Static assets resolve to `/v1/mlflow-proxy/static-files/...`
- Hash routes (`#/experiments/...`) resolve automatically under the prefix

No body rewriting is needed when `--static-prefix` is used (FR-057b mechanism a).

## URI Function

```python
def get_mlflow_browser_uri(request: Request) -> str:
    """Return the MLflow browser URL through the proxy.

    In both local and SaaS modes, returns ``{request.base_url}v1/mlflow-proxy``.
    SaaS mode uses the CloudFront origin (``Host`` header) and
    ``X-Forwarded-Proto`` header for scheme (``https``).
    """
```

## Verification (Playwright)

Before Gate G9 passes, a Playwright integration test MUST verify:

1. Authenticated `GET /v1/mlflow-proxy/` returns HTTP 200 with MLflow HTML
2. AJAX call to `/v1/mlflow-proxy/ajax-api/2.0/mlflow/experiments/list` succeeds with JSON response
3. Static assets (`/v1/mlflow-proxy/static-files/...`) resolve with correct `Content-Type`
4. Unauthenticated request to any proxy path returns HTTP 401

## Error Handling

| Scenario | Response |
|----------|----------|
| Upstream MLflow unreachable | 502 Bad Gateway (with retry/backoff in proxy) |
| Upstream timeout | 504 Gateway Timeout |
| Unauthenticated request | 401 Unauthorized |
| Non-existent experiment link | Forwarded from MLflow (404) |