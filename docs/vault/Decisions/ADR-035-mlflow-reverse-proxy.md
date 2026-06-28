---
title: 'MLflow Reverse Proxy — Authenticated, Port-Closed Access in Local and SaaS'
type: decision
status: superseded
source: agent
created: '2026-06-21'
updated: '2026-06-23'
aliases:
  - MLflow Reverse Proxy
  - ADR-035
related:
  - '[[Decisions/ADR-030-saas-architecture]]'
  - '[[Decisions/ADR-012-mlflow-browser-url-from-request-host]]'
  - '[[Decisions/ADR-010-disable-local-mlflow-server]]'
  - '[[Decisions/ADR-003-pit-of-success]]'
code-refs:
  - anvil/supervisor/services.py
  - anvil/config.py
  - anvil/api/app.py
  - docs/vault/Specs/016 SaaS Architecture/016 SaaS Architecture - spec.md
  - docs/vault/Specs/020 OWASP Remediation/020 OWASP Remediation - spec.md
  - docs/vault/Specs/056 Reverse-Proxy Registry/056 Reverse-Proxy Registry - spec.md
tags:
  - type/decision
  - domain/architecture
  - domain/infrastructure
  - domain/mlops
  - domain/operations
  - status/draft
superseded-by: '[[Decisions/ADR-037-unified-interface-local-tls]]'
---

# ADR-035: MLflow Reverse Proxy — Authenticated, Port-Closed Access in Local and SaaS

## Status

superseded

> [!warning] SUPERSEDED by [[Decisions/ADR-037-unified-interface-local-tls|ADR-037]].
> ADR-035 introduced the MLflow reverse proxy as a **one-off**. ADR-037 generalizes
> it into a **registry of mounted upstreams** under a single authenticated origin.
> The proxy mechanism described here is now owned and implemented by
> [[Specs/056 Reverse-Proxy Registry/056 Reverse-Proxy Registry|Spec 056 — Reverse-Proxy Registry]]
> (with MLflow as its first registered upstream). The decision below is retained
> for audit trail; treat ADR-037 + Spec 056 as the binding pattern.

## Context

The bundled MLflow tracking server is currently exposed as an **independent,
unauthenticated network service**:

- `MLflowService` (`anvil/supervisor/services.py`) launches `mlflow server`
  with `--host 0.0.0.0 --allowed-hosts "*"`.
- The host port (`5001` local, mapped in `compose.yaml`) is published alongside
  the app port (`8080`).
- The web UI links the **browser directly** to `http://<hostname>:5001`
  (`config.py::get_mlflow_browser_uri`, per ADR-012).

The OWASP review (spec 017) flagged this as HIGH (A05-001). The naive remediation
— change `--allowed-hosts "*"` to `localhost` — is **both breaking and
insufficient**:

- **Breaking**: a LAN user accessing the app at `http://192.168.1.10:8080` clicks
  "Open in MLflow", the browser navigates to `http://192.168.1.10:5001`, and
  MLflow (now `localhost`-only) rejects it. The README advertises LAN access, so
  this kills a real feature.
- **Insufficient**: MLflow still binds `0.0.0.0`, port 5001 stays published,
  `--allowed-hosts` is a `Host`-header filter trivially bypassed
  (`curl -H "Host: localhost" http://192.168.1.10:5001/`), and MLflow has no
  auth of its own. Any LAN attacker (or any container on the Docker bridge) can
  reach the MLflow API.

The SaaS architecture spec (014) **already mandates the correct pattern** for
SaaS mode: **FR-057 / AD-13** — an authenticated reverse proxy at
`/v1/mlflow-proxy/{path:path}` forwarding to a private MLflow, with MLflow
launched using `--static-prefix=/v1/mlflow-proxy` to fix its SPA's absolute
`/ajax-api/` and `/static-files/` paths. SaaS keeps MLflow in a private subnet
with no internet/ALB route.

The gap: **local mode has no proxy.** Local users (and the OWASP remediation)
need the same managed, pit-of-success experience — MLflow "just works" behind the
single authenticated app port, with no separate exposed port and no manual setup.
A study of the `concourse` repo confirmed the managed-service philosophy (Caddy
fronting upstreams with auth at the proxy layer); for anvil the portable,
zero-extra-process equivalent is an **in-process FastAPI `httpx.AsyncClient`
reverse proxy** (the same mechanism FR-057 already chose for SaaS).

## Decision

Adopt a **single, mode-aware MLflow reverse proxy** as the sole browser path to
MLflow in **both local and SaaS** modes. This unifies the SaaS FR-057 design and
the local OWASP remediation behind one pattern.

1. **In-process FastAPI proxy route** `/v1/mlflow-proxy/{path:path}` (until ADR-036
   de-versions URLs, then `/mlflow-proxy/...`) implemented with `httpx.AsyncClient`:
   - Subject to the same auth middleware as the rest of the app (session cookie
     for browser, `X-API-Key` for programmatic).
   - Streams responses (`httpx` streaming) so MLflow SSE/metric updates pass
     through.
   - Forwards to the upstream MLflow base URI (`ANVIL_MLFLOW_INTERNAL_URI`,
     default loopback locally, Cloud Map DNS in SaaS).
2. **Launch MLflow with `--static-prefix=/v1/mlflow-proxy`** in both modes so the
   MLflow SPA emits correct prefixed asset/AJAX paths (SaaS FR-057g; now also
   local). `MLflowService.start()` adds this flag.
3. **MLflow binds loopback and its host port is NOT published.**
   - Local: bind `127.0.0.1` only; remove `5001:5001` from `compose.yaml`
     (use internal `expose` if needed for the app process).
   - SaaS: private subnet, internal Cloud Map only (already AD-13).
4. **`--allowed-hosts` is hardened but NOT relied upon as the sole control** — the
   network-level closure (loopback bind + unpublished port + proxy-only access)
   is the real boundary.
5. **`get_mlflow_browser_uri(request)` returns the proxy URL**
   (`{request.base_url}v1/mlflow-proxy`) instead of `http://<host>:5001`, so all
   "Open in MLflow" links route through the authenticated app. Local and SaaS
   share this behavior (SaaS FR-057c).
6. **Pit of success preserved**: `make run` still brings MLflow up automatically;
   the user sees one authenticated endpoint on `8080` and never manages MLflow,
   its port, or its auth.

## Consequences

**Easier:**

- One MLflow access pattern across local and SaaS — no mode-specific browser URL
  logic divergence; SaaS FR-057 and local OWASP remediation converge.
- MLflow inherits the app's authentication for free; no second auth system.
- Attack surface closes properly: no published MLflow port, no `Host`-header
  bypass, no Docker-bridge reachability.
- Users keep the zero-config "Open in MLflow" experience.

**Harder / risks:**

- The proxy must correctly stream SSE and handle MLflow's absolute SPA paths;
  `--static-prefix` is mandatory and must be validated (a Playwright/integration
  test loading the MLflow UI through the proxy).
- `httpx` streaming proxying of large artifact downloads needs care (chunked
  pass-through, no full-body buffering).
- A daemon/loopback MLflow that fails to start must surface clearly (health-check
  gating in the lifespan) rather than producing opaque 502s from the proxy.
- Removing the published `5001` port is a breaking change for anyone who scripted
  direct `:5001` access — acceptable per greenfield posture (ADR-032).

## Compliance

- `grep` confirms `MLflowService.start()` passes `--static-prefix=/v1/mlflow-proxy`
  and binds loopback (no `--host 0.0.0.0`) in local mode.
- `compose.yaml` no longer publishes `5001`; only `8080` is exposed to the host.
- `get_mlflow_browser_uri` returns a `/v1/mlflow-proxy`-based URL in both modes;
  no template or JS links directly to `:5001`.
- An integration test loads the MLflow UI through `/v1/mlflow-proxy/` while
  authenticated (200 + assets resolve) and asserts an unauthenticated request is
  rejected (401/redirect).
- A direct request to `http://<lan-ip>:5001/` from off-host fails to connect
  (port not published).
- Cross-references: SaaS spec 014 FR-057/AD-13 and OWASP spec 017 FR-004 both
  point to this ADR as the binding pattern.

## See Also

- [[Decisions/README|Decisions]]
