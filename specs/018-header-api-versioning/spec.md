# Feature Specification: Header-Based API Versioning & URL Path De-Versioning

**Feature Branch**: `feature/018-header-api-versioning`  
**Created**: 2026-06-21  
**Status**: Draft  
**Input**: Spec review of OWASP remediation (017) surfaced that URL-embedded `/v1/` versioning (a) provides no value for a greenfield, single-version, zero-deployment project and (b) actively harms the auth design by colliding API and page routes under one prefix. Decision recorded in ADR-035.

## Clarifications

### Session 2026-06-21

- Q: Maintain backward compatibility / `/v1/` redirects during the migration? → A: No. Greenfield project (per ADR-032) — no users, no deployments, no released API contract. Remove `/v1/` outright with no alias, redirect, deprecation window, or compatibility layer.
- Q: Scope relative to OWASP remediation (017)? → A: Separate feature + ADR. Spec 017 (auth) ships independently; its auth contract is written to work with both the current `/v1/` layout (via explicit page-route registry) and the post-018 layout.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Stable, version-free URLs with header negotiation (Priority: P1)

As a developer and API consumer, I want the HTTP API and web pages served at clean, version-free paths, with any future version selected via an HTTP header, so that URLs are stable, links/bookmarks never carry a version, and version negotiation is decoupled from routing.

**Why this priority**: This is the entire feature. It removes the `/v1/` prefix and replaces URL-embedded versioning with header negotiation, and it unblocks clean API-vs-page classification for the auth middleware (spec 017).

**Independent Test**: Hit a bare path (e.g. `GET /health`) and confirm 200. Hit the old `/v1/health` and confirm 404 (no compat alias). Send the version header with a known value and confirm the current version responds; send an unknown version and confirm a clear 400.

**Acceptance Scenarios**:

1. **Given** the migration is complete, **When** a client requests a bare API path (e.g. `GET /datasets`), **Then** the request resolves exactly as `/v1/datasets` did before.
2. **Given** the migration is complete, **When** a client requests an old versioned path (e.g. `GET /v1/datasets`), **Then** the server returns 404 with no redirect (no backward compatibility).
3. **Given** a client sends the API version header with the current version, **When** the request is processed, **Then** it succeeds against the current version.
4. **Given** a client sends the API version header with an unsupported version, **When** the request is processed, **Then** the server returns 400 with a clear message listing supported versions.
5. **Given** the web UI is loaded, **When** a user navigates pages and triggers `fetch`/`EventSource` calls, **Then** all links and client calls use version-free paths and function correctly.

---

### User Story 2 — Clean API-vs-page route separation (Priority: P2)

As the maintainer of the auth middleware, I want API (JSON) routes and server-rendered page routes in clearly separable namespaces so that authentication can classify them without prefix ambiguity (API → 401, page → login redirect).

**Why this priority**: The `/v1/` collision between API and page routes was the root cause of the auth-classification footgun in spec 017. Resolving it simplifies and hardens auth.

**Independent Test**: Send an unauthenticated JSON request to an API route and confirm a 401; send an unauthenticated browser request to a page route and confirm a 303 redirect to `/login`. Confirm the classification requires no `Accept`-header heuristic fallback.

**Acceptance Scenarios**:

1. **Given** auth is enabled, **When** an unauthenticated request targets an API route, **Then** the server returns 401 (not a redirect).
2. **Given** auth is enabled, **When** an unauthenticated browser request targets a page route, **Then** the server returns a 303 redirect to `/login`.
3. **Given** the route layout, **When** the auth middleware classifies a request, **Then** it does so by namespace/registry, not by guessing from the shared prefix.

---

### Edge Cases

- What happens to a bookmarked `/v1/...` URL after migration? It 404s with no redirect (acceptable — zero deployments, greenfield per ADR-032).
- How are SSE endpoints affected? Their paths lose `/v1/` but otherwise behave identically; the auth cookie-fallback (spec 017 FR-025) still applies.
- How does the MLflow proxy path interact? The proxy route (ADR-034) moves from `/v1/mlflow-proxy/` to `/mlflow-proxy/`; `--static-prefix` and `get_mlflow_browser_uri` update accordingly.
- What if spec 017 (auth) ships before this? The auth contract uses an explicit page-route registry that works under `/v1/`; after 018 it simplifies to namespace-based classification.
- Does the Docker healthcheck break? The healthcheck target path updates (e.g. `/health`); it must be changed in the same migration.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST remove the `/v1/` prefix from all HTTP routes (API endpoints, page routes, SSE endpoints, static mount references, and the MLflow proxy route).
- **FR-002**: The system MUST NOT provide any backward-compatibility surface for the old `/v1/` paths — no redirect, no alias, no dual registration, no deprecation window (greenfield, per ADR-032).
- **FR-003**: The system MUST support optional API version negotiation via a single HTTP request header. Absent the header, requests target the current (and only) version. An unsupported version MUST yield a clear 400.
- **FR-004**: API (JSON) routes and server-rendered page routes MUST be placed in clearly separable namespaces (or an explicit registry) so authentication can classify them without relying on the shared prefix or `Accept`-header heuristics.
- **FR-005**: All internal consumers MUST be updated atomically in the same change: Jinja2 template links, static JS `fetch`/`EventSource` URLs, the Docker/compose healthcheck target, the CLI (if it references HTTP paths), tests, and the MLflow proxy route + `get_mlflow_browser_uri`.
- **FR-006**: The spec 017 auth middleware and the ADR-034 MLflow proxy MUST be updated to reference the new version-free paths once this feature lands.
- **FR-007**: Documentation (README route table, DESIGN.md if applicable, vault references) MUST be updated to reflect version-free paths and the header-negotiation scheme.

### Key Entities

- **API Version Header**: A single optional request header (e.g. `X-Anvil-API-Version` or an `Accept` media-type parameter) that selects the API version; defaults to current when absent.
- **Route Namespace**: The separation boundary distinguishing JSON API routes from server-rendered page routes for auth classification.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero `/v1/` literals remain in `anvil/api/`, templates, static JS, the Makefile/compose healthcheck, the MLflow proxy, and tests (allowing only the version-header constant). Verified by `grep`.
- **SC-002**: Bare paths resolve identically to their former `/v1/` counterparts; old `/v1/*` paths return 404. Verified by integration tests.
- **SC-003**: The optional version header is parsed; an unknown version yields 400. Verified by a negotiation test.
- **SC-004**: The auth middleware classifies API vs page routes by namespace/registry (no `Accept` heuristic). Verified by tests asserting 401 for API and 303 for pages on unauthenticated requests.
- **SC-005**: The full test suite, Docker healthcheck, browser SSE, and the MLflow proxy all pass against the new paths. Verified by `make test` + container health + a Playwright/integration check.

## Assumptions

- Greenfield posture per ADR-032 holds: no users, no deployments, no released API contract — a hard break is acceptable.
- Only one API version exists today; the header scheme is forward-looking infrastructure, not an immediate multi-version requirement.
- This feature is sequenced independently of spec 017; either order works (documented in both specs and ADR-035).
- The exact header name/format (custom header vs `Accept` media-type parameter) is an implementation decision to be finalized in planning; the spec only requires that negotiation is header-based and URL-free.
