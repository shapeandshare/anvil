# Feature Specification: Unified Single-Origin Interface & Working Local TLS

**Feature Branch**: `019-unified-interface-local-tls`  
**Created**: 2026-06-21  
**Status**: Draft  
**Input**: Product principle — external consumers must experience anvil as a single project on a single URL/origin (even though it internally combines API + MLflow + future services), and TLS must work locally while keeping the pip-install-only experience, with a parallel SaaS variant. Decision recorded in ADR-037.

## Clarifications

### Session 2026-06-21

- Q: How should TLS work locally without external binaries (Caddy/nginx/mkcert)? → A: uvicorn serves HTTPS using a self-signed certificate auto-generated on first run via the `cryptography` library (already in the dependency tree). Pure pip-install. Browser trust prompt is accepted for local-first; an opt-in trust path may be documented later.
- Q: What is the unified-interface model? → A: One origin/port. The anvil app is the only externally reachable endpoint; MLflow (now) and any future managed service are reverse-proxied under sub-paths of that single origin. Secondary services bind loopback-only with unpublished ports. The proxy layer is a registry so new services mount without bespoke wiring.
- Q: Packaging? → A: New ADR (ADR-037) + this new spec. Cross-references threaded into spec 017 (ADR-035 MLflow proxy = first instance) and SaaS spec 014.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — One URL for everything (Priority: P1)

As an external consumer (browser user, API client, or CLI), I want to reach all of anvil's functionality — web UI, API, MLflow, and any other bundled service — through a single host, port, and URL, so that I never have to know or connect to anvil's internal service composition.

**Why this priority**: This is the core principle. It removes the leaked `:5001` second port, makes the product feel like one coherent interface, and is the prerequisite for consistent auth, TLS, and URL handling across everything.

**Independent Test**: With anvil running, confirm only one port is reachable from off-host; reach the web UI, an API endpoint, and the MLflow UI all under that single origin (the latter via a proxied sub-path); confirm the secondary service's own port is not externally reachable.

**Acceptance Scenarios**:

1. **Given** anvil is running, **When** an external client scans for reachable ports, **Then** only the single anvil app port is reachable; secondary-service ports (e.g. MLflow's) are bound to loopback and not published.
2. **Given** anvil is running, **When** a user opens the MLflow UI from the web app, **Then** it loads under the unified origin (a proxied sub-path), not a separate host:port.
3. **Given** a future bundled service is added, **When** it is registered with the proxy layer, **Then** it is reachable under the unified origin without changes to how external consumers connect.
4. **Given** any external consumer, **When** they integrate against anvil, **Then** they use one host, one port, one scheme, one auth scheme, and one URL space.

---

### User Story 2 — HTTPS works locally, pip-install-only (Priority: P1)

As a developer who installed anvil with `pip install`, I want `https://` to work locally with no extra tools, so that the app's security controls (HSTS, Secure cookies) are actually in force and the local experience matches a secure deployment.

**Why this priority**: Spec 017 sets HSTS and Secure cookies but local mode is plain HTTP, making those controls inert and `https://localhost` impossible. TLS must be real locally to honor the security posture — and it must not require any non-pip tooling.

**Independent Test**: On a clean `pip install`, start anvil and load `https://localhost:<port>` — it serves over TLS using an auto-generated certificate, with no Caddy/nginx/mkcert installed. Security headers and Secure cookies are now effective.

**Acceptance Scenarios**:

1. **Given** a clean pip install with no external tooling, **When** anvil starts for the first time, **Then** it auto-generates a self-signed certificate (covering localhost, 127.0.0.1, and the host's LAN address) stored with restrictive permissions, and serves HTTPS.
2. **Given** anvil is serving HTTPS, **When** a browser loads `https://localhost:<port>`, **Then** the app loads over TLS (a trust prompt for the self-signed cert is acceptable) and Secure cookies + HSTS are honored.
3. **Given** TLS is active, **When** the web app generates links to proxied services or sets browser-facing URLs, **Then** those URLs use `https` and the unified origin (scheme-aware), never a bare `http://…:5001`.
4. **Given** a user who does not want TLS, **When** they set the documented config toggle, **Then** anvil serves over the alternate scheme without code changes.

---

### User Story 3 — Local and SaaS parity (Priority: P2)

As a maintainer, I want the local single-origin + TLS model to mirror the SaaS deployment, so that one front-door design serves both modes and behavior does not diverge.

**Why this priority**: SaaS (spec 014) already fronts everything with CloudFront/ALB on one origin with edge TLS and app-managed auth. Local mode should use the same app-level front-door + proxy-registry code, with only configuration differing (cert source, upstream addresses, auth scheme).

**Independent Test**: Inspect that the single-origin front door and proxy registry are shared code paths across modes; confirm the only differences are config (local self-signed cert + loopback upstreams vs edge TLS + private-subnet upstreams).

**Acceptance Scenarios**:

1. **Given** the shared front-door implementation, **When** running in local mode, **Then** TLS is app-terminated via the self-signed cert and upstreams are loopback.
2. **Given** the same implementation, **When** running in SaaS mode, **Then** TLS terminates at the edge (CloudFront/ALB) and upstreams are private-subnet services, with no divergence in the app's single-origin behavior.

---

### Edge Cases

- What happens on first run if cert generation fails (e.g. unwritable data dir)? Fail fast with a clear error, or fall back to HTTP with a loud warning per the configured policy — decided in planning.
- How is the LAN IP determined for the cert SANs, and what if it changes (DHCP)? Regenerate or include a wildcard/again-on-change strategy; documented as an assumption.
- What happens to existing direct `:5001` MLflow bookmarks/scripts? They break (port unpublished) — acceptable per greenfield posture (ADR-032); the proxied path is the supported route.
- How does the self-signed cert interact with the CLI / API clients (which reject untrusted certs)? Document the trust/`--insecure`/CA-path options for programmatic clients.
- How does HTTPS affect the Docker healthcheck and browser SSE? Healthcheck and SSE must target the unified HTTPS origin (or an exempt path); coordinated with spec 017.
- What if a proxied service emits absolute paths (like MLflow's SPA)? Handled by the per-service prefix mechanism (e.g. `--static-prefix`), per ADR-035.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: anvil MUST expose a single externally reachable origin (one host, one port, one scheme). All bundled functionality — web UI, API, MLflow, and any future managed service — MUST be reachable only through that origin.
- **FR-002**: Secondary/bundled services (MLflow now; others later) MUST bind to loopback only, MUST NOT publish their host ports, and MUST be reachable solely via the app's reverse-proxy sub-paths under the unified origin.
- **FR-003**: The reverse-proxy layer MUST be a registry of mounted upstreams (not a one-off), so additional managed services can be mounted under the unified origin without bespoke per-service wiring. (Generalizes ADR-035.)
- **FR-004**: anvil MUST serve TLS locally using a certificate auto-generated on first run, with no external tooling required (pip-install-only). Generation MUST use the `cryptography` library (promoted to a direct dependency) and cover localhost, 127.0.0.1, and the host's LAN address via SANs.
- **FR-005**: The generated private key and certificate MUST be stored with restrictive permissions (`0600`) under the data directory and reused across restarts; regeneration MUST be possible on demand.
- **FR-006**: Browser-facing URL and scheme derivation (e.g. `get_mlflow_browser_uri` and any link/redirect builders) MUST be scheme-aware — honoring `https` and `X-Forwarded-Proto` — and MUST emit the unified-origin path, never a bare secondary-service host:port.
- **FR-007**: TLS MUST be configurable (e.g. `ANVIL_TLS`) with a sensible default; the chosen default and any opt-out MUST be documented.
- **FR-008**: The local and SaaS deployments MUST share the same app-level single-origin front-door and proxy-registry code; mode-specific differences (cert source, upstream addresses, auth scheme, TLS termination point) MUST be confined to configuration and `anvil/_saas/` overrides — no divergent front-door logic.
- **FR-009**: Enabling local HTTPS MUST be coordinated so dependent consumers do not break: the Docker/compose healthcheck, browser SSE, the CLI, and tests MUST target the unified (HTTPS) origin or a designated exempt path.
- **FR-010**: `cryptography` MUST be declared as a direct runtime dependency in `pyproject.toml` (it is already present transitively, so the footprint is unchanged).

### Key Entities

- **Unified Origin**: The single externally reachable endpoint (host + port + scheme) through which all anvil functionality is served.
- **Proxy Registry**: The collection of mounted upstream services (MLflow, future services) exposed under sub-paths of the unified origin.
- **Local TLS Certificate**: The auto-generated self-signed cert + key (with SANs for localhost/127.0.0.1/LAN), stored `0600`, used by uvicorn to serve HTTPS.
- **Mode Configuration**: The per-mode settings (local vs SaaS) that select cert source, upstream addresses, auth scheme, and TLS termination — without changing front-door logic.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From off-host, only the single anvil app port is reachable; secondary-service ports are not. Verified by a port/connectivity check.
- **SC-002**: On a clean `pip install` with no external tooling, `https://localhost:<port>` loads over TLS from the auto-generated cert. Verified by an integration test on a clean environment.
- **SC-003**: The MLflow UI (and any registered service) loads under the unified origin via its proxy sub-path; the direct `:5001` route is not externally reachable. Verified by an integration test.
- **SC-004**: All browser-facing URLs emit `https` and the unified-origin path (no bare secondary host:port). Verified by code review + an integration test.
- **SC-005**: Adding a new managed service to the proxy registry exposes it under the unified origin with no change to how external consumers connect. Verified by a registry-level test using a stub upstream.
- **SC-006**: Security controls from spec 017 (HSTS, Secure cookies) are effective locally because the connection is TLS. Verified by inspecting response headers and cookie flags over HTTPS.
- **SC-007**: Local and SaaS use the same front-door/proxy code; a diff shows mode differences confined to config and `anvil/_saas/`. Verified by code review.

## Assumptions

- Local-first remains pip-install-only; no Caddy/nginx/mkcert or system-trust-store modification is introduced. The self-signed cert's browser trust prompt is an accepted local tradeoff; a documented opt-in "trust this cert" path may follow.
- `cryptography` is acceptable as a direct dependency — it is already resolved transitively, so no net new footprint.
- The unified-origin proxying for MLflow reuses the ADR-035 mechanism (in-process `httpx` reverse proxy, `--static-prefix`, streaming pass-through); this spec generalizes it into a registry.
- SaaS TLS continues to terminate at the edge (CloudFront/ALB per ADR-030); this spec does not change SaaS termination, only ensures shared app behavior.
- Sequencing: this feature complements spec 017 (which introduces the MLflow proxy and the security headers) and ADR-036/spec 018 (URL de-versioning, which moves proxy sub-paths off `/v1/`). Exact ordering is a planning decision; cross-references are recorded in all affected specs.
- Default TLS posture (on vs opt-in) is finalized in planning; the spec requires only that it be configurable and documented.
