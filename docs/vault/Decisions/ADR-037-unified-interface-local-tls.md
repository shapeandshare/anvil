---
title: Unified Single-Origin Interface and Working Local TLS
type: decision
status: draft
source: agent
created: '2026-06-21'
updated: '2026-06-21'
aliases:
  - Unified Single-Origin Interface and Working Local TLS
  - ADR-037
  - Single Front Door
related:
  - '[[Decisions/ADR-035-mlflow-reverse-proxy]]'
  - '[[Decisions/ADR-036-header-based-api-versioning]]'
  - '[[Decisions/ADR-030-saas-architecture]]'
  - '[[Decisions/ADR-003-pit-of-success]]'
  - '[[Decisions/ADR-018-packaging-resource-relocation]]'
code-refs:
  - anvil/cli.py
  - anvil/config.py
  - anvil/api/app.py
  - anvil/supervisor/services.py
  - docs/vault/Specs/024 Unified Interface Local TLS/spec.md
tags:
  - type/decision
  - domain/architecture
  - domain/infrastructure
  - domain/operations
  - status/draft
---

# ADR-037: Unified Single-Origin Interface and Working Local TLS

## Status

proposed

## Context

anvil is several moving parts behind the scenes — the FastAPI web/API app, an
MLflow tracking server (separate process, separate port), and (in SaaS) more
managed services. Today the local experience leaks that internal composition to
external consumers:

- The web app is on `:8080`; MLflow is on a separately published `:5001`; the UI
  links the browser directly to `http://<host>:5001`.
- The server runs plain HTTP bound to `0.0.0.0`, yet the security posture sets
  HSTS and `Secure` cookies "in production" — there is no TLS locally, so those
  controls are inert and `https://localhost` does not work.

Two product principles are now explicit:

1. **One project, one interface.** External consumers (browsers, API clients,
   the CLI, future integrators) must experience anvil as a *single* product on a
   *single* origin/URL, even though we are combining API + MLflow + other
   services internally. The internal decomposition must not surface as multiple
   ports/hosts/URLs.
2. **TLS must work locally**, while preserving the **pip-install-only** local
   experience (no Caddy/nginx/mkcert or other external binaries), AND the same
   model must extend to the **SaaS** deployment.

Prior decisions already point this way but only partially:
- **ADR-035** put MLflow behind an authenticated in-process reverse proxy
  (`/v1/mlflow-proxy/`) — the first instance of the single-front-door pattern.
- **ADR-030 / spec 014 (SaaS)** already front everything with CloudFront + ALB
  on one origin, with app-managed auth (FR-057 / FR-019).
- **spec 009 / ADR-018** established the pip-installable single-package distribution and packaging layout.

What is missing is a stated, general principle (all secondary services live
under the one origin) and a concrete, pip-only local TLS mechanism.

## Decision

Adopt a **single unified front door** for anvil in every mode, and make **TLS
work locally** using only pip-installable components.

### 1. Single origin / single URL (all modes)

- The anvil app is the **only** externally reachable endpoint. It listens on one
  port and serves: the web UI, the `/`-rooted API, and **all** secondary
  services via in-process reverse-proxy sub-paths (MLflow today at
  `/mlflow-proxy/` per ADR-035; future managed services mount the same way).
- Secondary services (MLflow, and anything added later) bind to **loopback only**
  and their host ports are **never published**. The only way in is through the
  unified origin, under the app's authentication.
- The proxy layer is a **registry of mounted upstreams**, not a one-off, so new
  services attach under the unified origin without bespoke wiring (generalizes
  ADR-035).
- External consumers therefore see one host, one port, one scheme, one auth
  scheme, and one set of URLs — regardless of internal composition.

### 2. Working local TLS, pip-only

- On first run anvil **auto-generates a self-signed certificate** (via the
  already-present `cryptography` library — promoted to a direct dependency)
  for `localhost`, `127.0.0.1`, and the host's LAN IP/hostname (SANs), stored
  `0600` under the data dir (e.g. `data/tls/`).
- `anvil` (uvicorn) serves **HTTPS** using that cert
  (`uvicorn.run(..., ssl_certfile=..., ssl_keyfile=...)`), so `https://localhost`
  works out of the box with no external tooling.
- This is delivered **pip-install-only** — no Caddy/nginx/mkcert, no system trust
  store changes. The tradeoff (a browser trust prompt for the self-signed cert)
  is accepted for local-first; a documented opt-in path may trust the cert
  later. TLS is controllable via config (e.g. `ANVIL_TLS`) with a sensible
  default, and browser-facing URL/scheme derivation (`get_mlflow_browser_uri`
  and friends) becomes **scheme-aware** (honors `https` and
  `X-Forwarded-Proto`).
- In **SaaS**, TLS terminates at the edge (CloudFront/ALB, ADR-030) — the same
  single-origin, scheme-aware app behavior holds; only the termination point
  differs.

### 3. Local vs SaaS parity

- Local (`pip install anvil`): one process, one HTTPS port, loopback-only
  sidecars proxied under the origin, self-signed cert.
- SaaS: one public origin (CloudFront/ALB), private subnet sidecars proxied by
  the app, edge-terminated TLS, app-managed JWT auth.
- Both share the **same app-level front-door + proxy-registry code**; mode
  differences (cert source, upstream addresses, auth scheme) are confined to
  configuration and the `anvil/_saas/` overrides.

## Consequences

**Easier:**

- External consumers integrate against one stable origin/URL; internal service
  composition is invisible and can change without breaking them.
- HSTS, `Secure` cookies, and `https://` links become real locally instead of
  inert — the spec 017 security posture is actually enforced.
- Local and SaaS converge on one front-door design; less mode-specific drift.
- Still pip-install-only locally — no new external runtime tooling.

**Harder / risks:**

- Self-signed certs trigger browser trust warnings; needs clear first-run
  messaging and an optional "trust this cert" doc path.
- `cryptography` must be promoted to a direct dependency (it is already in the
  resolved tree transitively, so footprint is unchanged).
- Proxying all secondary services through the app adds latency and streaming
  responsibilities (SSE, chunked downloads) — already handled for MLflow in
  ADR-035; the registry generalizes it.
- Binding sidecars to loopback and unpublishing their ports is a breaking change
  for anyone scripting direct `:5001` access (acceptable per greenfield posture,
  ADR-032).
- Serving HTTPS by default changes the local URL scheme; healthchecks, tests,
  and docs that assume `http://` must be updated.

## Compliance

- `anvil` serves HTTPS locally from an auto-generated cert; `https://localhost:<port>`
  loads with no external tooling installed (pure `pip install`).
- No secondary-service host port is published locally; `lsof`/`curl` confirms
  only the single app port is reachable; MLflow et al. are reachable only via
  the unified origin's proxy sub-paths.
- Browser-facing URL builders emit `https` and the unified-origin path (never a
  bare `:5001`), verified by an integration test.
- `cryptography` appears as a direct dependency in `pyproject.toml`.
- SaaS mode continues to terminate TLS at the edge with the same app behavior
  (no regression to ADR-030 / FR-057).
- Cross-referenced by spec 019 (this feature), and by spec 017 (ADR-035 is the
  first instance of the single-front-door proxy).
