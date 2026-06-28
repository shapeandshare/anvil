---
title: 056 Reverse-Proxy Registry - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/056 Reverse-Proxy Registry/
related:
  - '[[056 Reverse-Proxy Registry]]'
created: '2026-06-28'
updated: '2026-06-28'
status: draft
---
# Feature Specification: Reverse-Proxy Registry & Single-Origin Front Door

**Feature Branch**: `056-reverse-proxy-registry`
**Created**: 2026-06-28
**Status**: Draft
**Input**: ADR-037 (Unified Single-Origin Interface) generalizes the one-off MLflow reverse proxy (ADR-035) into a registry of mounted upstreams. Three specs — 020 OWASP Remediation (FR-004), 036 SaaS Observability (FR-057a–g), and 024 Unified Interface (FR-003) — each independently restated the same proxy mechanism. This spec consolidates that mechanism into one foundational owner so the others reference it instead of duplicating it.

## Clarifications

### Session 2026-06-28

- Q: Why a new foundational spec rather than extending 020/024/036? → A: The proxy mechanism was triple-specified across 020 (T009), 036 (FR-057), and 024 (FR-003), with ADR-035 superseded by ADR-037 but still cited as binding in 020/036. A single foundational spec removes the drift: it owns the generic registry + the MLflow upstream, and the other specs become consumers that reference it.
- Q: What is the boundary between this spec and spec 024? → A: ADR-037 has two halves. Spec 056 owns the **proxy-registry / single-origin front door** half; spec 024 owns the **local TLS** half. Both share the same mode-aware front-door code; this spec does not introduce or own TLS.
- Q: What is the boundary between this spec and spec 036? → A: 056 owns the **generic proxy mechanism** (route, streaming, registry, loopback bind, `--static-prefix`, `get_mlflow_browser_uri`). 036 keeps only the **SaaS-specific** concerns layered on top: Cognito JWT + RBAC enforcement on the proxied route, `org_id` experiment tagging, Cloud Map upstream address, and CloudFront-aware scheme.
- Q: Does this resolve the spec 012 port-publishing conflict? → A: Yes. Spec 012 publishes MLflow port `5001`; this spec mandates loopback-only with the port unpublished. Spec 056 is the governing architecture; spec 012's Docker/compose contracts defer to it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — One authenticated origin for every bundled service (Priority: P1)

As an external consumer (browser, API client, CLI), I want every bundled service — the web UI, the API, MLflow, and any future managed service — reachable through one host/port/scheme under one authentication scheme, so that I never connect to anvil's internal service composition directly.

**Why this priority**: This is the core single-origin principle and the prerequisite for the OWASP A05-001/A07 remediation (no separately exposed, unauthenticated MLflow port). Without it, every secondary service is an independent attack surface.

**Independent Test**: With anvil running, scan reachable ports from off-host — only the single app port answers. Load the MLflow UI from the web app — it resolves under a proxied sub-path of the app origin, not a separate `host:port`. Confirm the MLflow port is not reachable off-host.

**Acceptance Scenarios**:

1. **Given** anvil is running, **When** an external client scans for reachable ports, **Then** only the single app port answers; registered upstreams (MLflow now) are bound to loopback and their ports are not published.
2. **Given** anvil is running and the user is authenticated, **When** they open the MLflow UI from the web app, **Then** it loads under the unified origin via `/v1/mlflow-proxy/` and its SPA AJAX/static assets resolve under that prefix.
3. **Given** an unauthenticated client, **When** it requests `/v1/mlflow-proxy/` (or any proxied sub-path), **Then** the app's auth middleware rejects it (401 for API-style, login redirect for browser) before the request reaches the upstream.
4. **Given** a direct request to the upstream's own port from off-host, **When** it is attempted, **Then** it fails to connect (port not published).

---

### User Story 2 — Register a new upstream without bespoke wiring (Priority: P1)

As a maintainer adding a future bundled service, I want to register it with the proxy layer and have it reachable under the unified origin automatically, so that no new per-service routing, auth, or URL-derivation code is required.

**Why this priority**: This is the generalization mandated by ADR-037 FR-003 — the difference between a one-off MLflow proxy (ADR-035) and a reusable layer. It is what lets specs 028 (concurrent instances) and future SaaS services attach cleanly.

**Independent Test**: Register a stub upstream against the registry under a test prefix; confirm a request to that prefix is forwarded to the stub and the response streams back, with no code added beyond the registration call.

**Acceptance Scenarios**:

1. **Given** the proxy registry, **When** a new upstream is registered with a mount prefix and an upstream base URI, **Then** requests under that prefix are forwarded and responses streamed without any other code change.
2. **Given** a registered upstream, **When** the app derives a browser-facing URL for it, **Then** the URL is the unified-origin sub-path (scheme-aware), never the upstream's own host:port.
3. **Given** two registered upstreams, **When** requests arrive for each prefix, **Then** each is routed to its own upstream independently.

---

### User Story 3 — Local and SaaS share one front-door, differ only by config (Priority: P2)

As a maintainer, I want the local and SaaS deployments to use the same single-origin front-door and proxy-registry code, so that behavior does not diverge and only configuration (upstream addresses, auth scheme, TLS termination) differs.

**Why this priority**: SaaS (spec 016/033) already fronts everything with CloudFront/ALB on one origin. Local mode should reuse the same app-level registry; divergent front-door logic is a maintenance and security hazard.

**Independent Test**: Inspect that the front-door + registry are shared code paths across modes; confirm the only differences are configuration (loopback upstream vs Cloud Map upstream; self-signed TLS vs edge TLS; API-key/session auth vs Cognito JWT).

**Acceptance Scenarios**:

1. **Given** the shared front-door implementation, **When** running locally, **Then** upstreams are loopback and the MLflow proxy upstream is `127.0.0.1:<mlflow_port>`.
2. **Given** the same implementation, **When** running in SaaS, **Then** upstreams are private-subnet/Cloud Map addresses and TLS terminates at the edge, with no divergence in the app's single-origin or registry behavior.

---

### Edge Cases

- What happens when an upstream fails to start or is unreachable? The proxy MUST surface a clear error (gated by a readiness/health check in the app lifespan) rather than opaque 502s; the upstream's health is checked before its proxy is advertised.
- How are MLflow's absolute SPA paths handled? Via the per-upstream prefix mechanism (`--static-prefix=/v1/mlflow-proxy`), so the SPA emits correctly-prefixed AJAX/static URLs; no response-body rewriting.
- How does the proxy handle long-lived streaming (SSE, chunked artifact downloads)? Via `httpx` streaming pass-through with no full-body buffering; per-upstream timeouts (e.g. 60s UI, 300s artifact downloads).
- How does CSRF interact with a proxied SPA that issues its own AJAX? The proxy prefix is exempt from the synchronizer-token check (the embedded SPA cannot carry anvil's CSRF token); safety relies on `SameSite=Strict` + same-origin (cross-ref spec 020 FR-027).
- What happens to scripts/bookmarks hitting the upstream's old direct port? They break (port unpublished) — accepted per greenfield posture (ADR-032); the proxied path is the supported route.
- How does the proxy prefix interact with URL de-versioning (spec 023 / ADR-036)? The prefix moves from `/v1/mlflow-proxy/` to `/mlflow-proxy/` when 023 lands; `--static-prefix` and the URL builder update in lockstep. This spec owns that move.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST expose a single externally reachable origin (one host, one port, one scheme). All bundled functionality — web UI, API, and every registered upstream — MUST be reachable only through that origin.
- **FR-002**: Every registered upstream service (MLflow now; others later) MUST bind to loopback (local) or a private address (SaaS) only, MUST NOT publish its host port, and MUST be reachable solely via the app's reverse-proxy sub-path.
- **FR-003**: The reverse-proxy layer MUST be a **registry of mounted upstreams**, not a per-service one-off. Registering an upstream MUST require only a mount prefix and an upstream base URI; no bespoke routing, auth, or URL-derivation code per upstream. (Implements ADR-037 FR-003; generalizes ADR-035.)
- **FR-004**: The proxy MUST forward the full request path + query string to the upstream and **stream** the response (no full-body buffering), so SSE and chunked artifact downloads pass through. Per-upstream timeouts MUST be configurable.
- **FR-005**: Every proxied sub-path MUST be subject to the same app authentication middleware as the rest of the app (API key / session cookie locally; Cognito JWT in SaaS — the SaaS auth layer is owned by spec 030/036, applied here unchanged). Unauthenticated requests MUST be rejected (401 for API-style, login redirect for browser) before reaching the upstream.
- **FR-006**: The proxy MUST support per-upstream **path-prefix correction** for upstreams whose SPA emits absolute paths. For MLflow this MUST be `--static-prefix=<mount-prefix>` passed at launch; no response-body rewriting.
- **FR-007**: Browser-facing URL builders (e.g. `get_mlflow_browser_uri`) MUST return the unified-origin sub-path for a registered upstream, MUST be **scheme-aware** (honor `https` and `X-Forwarded-Proto`), and MUST NEVER emit a bare upstream host:port.
- **FR-008**: The MLflow upstream MUST be the first registered upstream: route `/v1/mlflow-proxy/{path:path}`, upstream configurable via `ANVIL_MLFLOW_INTERNAL_URI` (local default loopback `http://127.0.0.1:<mlflow_port>`; SaaS default Cloud Map). In SaaS mode a missing value MUST fail fast at startup.
- **FR-009**: `MLflowService.start()` MUST launch MLflow bound to loopback (not `0.0.0.0`) with `--static-prefix=/v1/mlflow-proxy`, and MUST NOT rely on `--allowed-hosts` as the sole control. The MLflow host port MUST NOT be published (`compose.yaml`, `Dockerfile EXPOSE`).
- **FR-010**: The proxy prefix MUST be exempt from the CSRF synchronizer-token check (the embedded SPA issues its own state-changing AJAX that cannot carry anvil's CSRF token); safety relies on `SameSite=Strict` + same-origin. This wires the existing `CSRF_EXEMPT_PREFIXES` entry to a live route. (Cross-ref spec 020 FR-027.)
- **FR-011**: An upstream's readiness MUST be checked (health check) before its proxy is advertised/used; an unreachable upstream MUST produce a clear error in the app lifespan/logs, not opaque proxy 502s.
- **FR-012**: The local and SaaS deployments MUST share the same front-door + registry code; mode differences (upstream addresses, auth scheme, TLS termination point) MUST be confined to configuration and `anvil/_saas/` overrides — no divergent front-door logic.
- **FR-013**: The proxy mount prefix MUST be defined in one place so that URL de-versioning (spec 023 / ADR-036) can move it from `/v1/mlflow-proxy/` to `/mlflow-proxy/` by changing that single definition, with `--static-prefix` and the URL builder following automatically.

### Key Entities

- **Unified Origin**: The single externally reachable endpoint (host + port + scheme) through which all functionality is served.
- **Proxy Registry**: The collection of mounted upstreams (mount prefix → upstream base URI + options), exposed under sub-paths of the unified origin.
- **Registered Upstream**: A bundled service (MLflow now; future services) reached only via its proxy sub-path; bound loopback/private with an unpublished port.
- **Mount Prefix**: The single-source-of-truth URL prefix for an upstream (e.g. `/v1/mlflow-proxy`), used by the route, `--static-prefix`, and the browser-URL builder.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From off-host, only the single app port is reachable; registered-upstream ports are not. Verified by a port/connectivity check.
- **SC-002**: The MLflow UI loads under `/v1/mlflow-proxy/` while authenticated (200, assets resolve under the prefix); unauthenticated → 401/redirect; direct off-host `:5001` is not reachable. Verified by an integration test (replaces spec 020 T009t).
- **SC-003**: A cookie-authenticated state-changing MLflow AJAX call succeeds without an `X-CSRF-Token` (proxy prefix CSRF-exempt). Verified by an integration test.
- **SC-004**: Registering a stub upstream exposes it under the unified origin with no code change beyond the registration call. Verified by a registry-level test using a stub upstream (closes spec 024 SC-005).
- **SC-005**: All browser-facing URLs for registered upstreams emit the unified-origin sub-path and correct scheme (no bare host:port). Verified by code review + integration test.
- **SC-006**: `MLflowService` launches with loopback bind + `--static-prefix`; `compose.yaml` and `Dockerfile` no longer publish/expose `5001`. Verified by code review + container port inspection.
- **SC-007**: Local and SaaS use the same front-door/registry code; a diff shows differences confined to config and `anvil/_saas/`. Verified by code review.

## Assumptions

- `httpx` is already a direct dependency (FastAPI uses it); the in-process reverse proxy introduces no new runtime dependency (Article I / lean-deps intact).
- TLS is owned by spec 024 (ADR-037's other half); this spec consumes the scheme-aware URL behavior but does not generate or terminate TLS.
- SaaS auth (Cognito JWT + RBAC) is owned by specs 030/031/036 and applied to proxied routes via the same middleware mechanism; this spec does not define the SaaS auth itself.
- The MLflow upstream is the only registered upstream at v1; the registry is built for one real consumer plus a stub-upstream test (YAGNI honored — the registry exists because a second use case, SaaS Cloud Map MLflow, is already concrete).
- The proxy prefix stays `/v1/mlflow-proxy/` until spec 023 de-versions URLs; the single-definition requirement (FR-013) makes that a one-line change later.
- Spec 012's Docker/compose contracts are amended to stop publishing `5001` (this spec is the governing architecture for that port).
