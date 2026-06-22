---
title: 020 OWASP Remediation - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/020 OWASP Remediation/
related:
  - '[[020 OWASP Remediation]]'
created: ~
updated: ~
---
# Feature Specification: OWASP Top 10 Security Remediation

**Feature Branch**: `020-owasp-remediation`  
**Created**: 2026-06-21  
**Status**: Draft  
**Input**: OWASP Top 10 security review and finding tracker (35 open findings + 2 accepted risks across A01-A10 categories)

## Clarifications

### Session 2026-06-21

- Q: Should authentication protect only API routes (`/v1/...`), or also the web UI page routes (`/`, `/v1/datasets-page`, etc.)? → A: Protect both API and page routes — all HTTP routes require authentication. Web UI gets a login page redirect; API routes return 401/403.
- Q: How should the initial authentication credential be established for a new deployment? → A: Auto-generate a random API key on first startup, overridable via the `ANVIL_API_KEY` environment variable. This ensures zero-friction local setup while guaranteeing every instance starts with auth active. (Refined during review: the full key is NEVER written to log files — only a short prefix hint is shown on first run, with the full value retrievable via a `--show-api-key` CLI command, to avoid credential disclosure to persistent/ tailable log stores.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Harden critical attack surface against unauthorized access (Priority: P1)

As a developer running anvil on a shared or LAN-accessible network, I want the most critical attack vectors blocked — authentication on API endpoints, structured input validation on training configuration, and restricted MLflow access — so that an attacker who reaches the server cannot execute privileged operations (service management, model inference, training execution) or submit malformed payloads.

**Why this priority**: Addresses all 3 CRITICAL-severity findings (A07-001: zero auth on entire API, A04-001: unvalidated training config dict, A01-001/A01-002: unauthenticated service management) and the HIGH-severity MLflow misconfiguration (A05-001). Without this layer, every other security control is moot — an attacker with network access has full control.

**Independent Test**: Can be fully tested by attempting privileged API calls (POST /services/restart-all, POST /training/start, GET /v1/inference/model-params) without credentials — each MUST return an authentication error. Then repeat with valid credentials — each MUST succeed. Independently verifies that the auth gate works before any other remediation.

**Acceptance Scenarios**:

1. **Given** the application is running on a network-accessible host, **When** an unauthenticated request is sent to any route (API or web page), **Then** the server either redirects to a login page (browser requests) or returns an authentication error (API requests, HTTP 401 or 403), and does not execute the requested operation.
2. **Given** a user has valid credentials, **When** they send an authenticated request to a privileged endpoint (service management, training start, inference), **Then** the request is processed normally.
3. **Given** the MLflow tracking server is managed by the application, **When** the application starts MLflow, **Then** the server is configured to accept connections only from expected hosts (localhost/127.0.0.1) rather than any host.
4. **Given** an unauthenticated user sends a POST /training/start with arbitrary JSON fields, **Then** the request is rejected before any compute resources are allocated.
5. **Given** a user sends a raw untyped JSON body to an endpoint that currently accepts `body: dict`, **Then** the request is rejected with a validation error describing which fields are expected.

---

### User Story 2 — Strengthen endpoint and configuration security (Priority: P2)

As a developer, I want the remaining HIGH-severity findings addressed — typed request validation across all endpoints, input size limits, rate limiting, ReDoS protection, secure CI/CD pins, and restricted error disclosure — so that common attack vectors (DoS via large uploads, regex backtracking, brute force, supply chain via floating action tags) are blocked and internal implementation details are not leaked to API clients.

**Why this priority**: Covers 12 HIGH-severity findings (A01-003, A01-004, A01-005, A04-002, A04-003, A04-004, A04-006, A04-007, A04-008, A07-002, A06-001/A08-001 duplicate) and the A05-003 information leak. These are individually exploitable and represent the most common web application attack patterns after authentication is in place.

**Independent Test**: Can be tested by sending oversized payloads to upload endpoints, submitting regex patterns with catastrophic backtracking, making rapid repeated requests, and examining API error responses for internal path/stack information — all must be blocked or sanitized. CI/CD workflow changes can be verified by inspecting the pinned action digests.

**Acceptance Scenarios**:

1. **Given** the application is running, **When** a client sends a file larger than the allowed limit to a dataset upload or content staging endpoint, **Then** the request is rejected with a clear error message and the file is not stored.
2. **Given** the application is running, **When** a client submits a regex pattern known to cause catastrophic backtracking to the regex_replace endpoint, **Then** the operation times out or is rejected before causing resource exhaustion.
3. **Given** the application is running, **When** a client sends requests more rapidly than the configured rate limit, **Then** subsequent requests are throttled with a rate-limit error response.
4. **Given** the application returns an error response triggered by an internal exception, **When** a client inspects the response body, **Then** it contains a generic user-facing message (not filesystem paths, variable names, or DB constraint details).
5. **Given** the CI/CD workflows in the repository, **When** a reviewer inspects the SonarCloud action references, **Then** they are pinned to specific SHA256 digests rather than floating `@master` tags.

---

### User Story 3 — Implement security hardening best practices (Priority: P3)

As a developer, I want the remaining MEDIUM and LOW severity findings addressed — security headers, CORS policy, idempotency keys, proper logging, digest-pinned Docker images, path containment checks, and race-condition fixes — so that the application meets industry security best practices and is prepared for deployment in more restrictive environments.

**Why this priority**: Covers the remaining 19 findings (12 MEDIUM + 7 LOW). These are lower-risk individually but collectively represent defense-in-depth gaps. Security headers and CORS are table-stakes for any web application; logging improvements aid incident response; idempotency prevents data corruption under retry.

**Independent Test**: Each remediation can be verified independently — check HTTP response headers for CSP/HSTS, confirm CORS headers restrict origins, verify concurrent duplicate requests don't create duplicate training runs, confirm Dockerfile uses digest-pinned base images, confirm path operations are contained within expected directories.

**Acceptance Scenarios**:

1. **Given** the application is running, **When** a client inspects HTTP response headers, **Then** security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options) are present with secure defaults.
2. **Given** the application is running on a network interface, **When** a browser on a different origin sends a cross-origin request, **Then** the server either blocks the request (no CORS header) or responds with an explicit allowlist.
3. **Given** a duplicate training start request arrives within a short window, **When** the second request carries the same idempotency key as the first, **Then** only one training run is created and the second request returns the existing run identifier.
4. **Given** the application starts via the uvicorn entry point (not CLI), **When** a startup failure occurs (e.g., license seeding, demo bootstrap), **Then** the failure is logged with a warning rather than silently swallowed.
5. **Given** the Dockerfile builds the runtime image, **When** a reviewer inspects the base image reference, **Then** it is pinned to a specific SHA256 digest rather than a floating tag.
6. **Given** a file operation uses a user-controlled path, **When** the path is resolved, **Then** it is verified to be contained within the expected directory before any read or write occurs.

---

### Edge Cases

- What happens when authentication is configured but the configured auth method is unavailable (e.g., auth provider is down)? The system should fail closed — deny access until auth is available.
- How is the login page itself protected? The login page must be the single unauthenticated route — all other routes require a valid session. The login endpoint must have rate limiting to prevent brute force.
- What happens if the auto-generated API key is lost? Run the `--show-api-key` CLI command to retrieve it (the key is persisted, e.g. in the app DB or a `0600`-permission state file, NOT in logs). If a custom key was set via `ANVIL_API_KEY`, check the deployment configuration. The key is never printed in full to logs, so log access alone does not disclose it.
- How does the system behave when rate-limited requests are from a legitimate user performing bulk operations? Rate limits should be configurable and per-endpoint to accommodate different usage patterns.
- What happens when a file upload is interrupted mid-stream? The partial upload should be discarded and not leave orphaned temporary files.
- How does idempotency interact with training run failures — should retrying with the same key create a new run or return the failed run? Returning the existing failed run preserves idempotency semantics.
- What should happen when CORS is configured in local-only mode vs LAN-accessible mode? Local mode may not need CORS; LAN mode requires an explicit allowlist.
- How does the system handle a regex timeout — should it return a partial result, an error, or silently skip the offending pattern? It should return an error with a clear message indicating the pattern was too complex.

## Requirements *(mandatory)*

### Functional Requirements

#### Critical Severity (Authentication & Input Validation)

- **FR-001**: System MUST require authentication on all HTTP routes before serving content or processing requests. Web page routes MUST redirect unauthenticated users to a login page; API routes MUST return HTTP 401 or 403. Exemptions for unauthenticated access must be explicitly and minimally declared.
- **FR-002**: System MUST reject requests to service management endpoints (restart-all, start, stop, restart, kill-port, clear-logs) when no valid authentication is provided.
- **FR-003**: System MUST validate training configuration input against a defined schema before allocating any compute resources.
- **FR-004**: System MUST stop exposing the MLflow tracking server as an independently reachable, unauthenticated network service. MLflow MUST be reachable only through the authenticated anvil app via a reverse proxy (see ADR for the MLflow reverse-proxy pattern and the SaaS spec updates). Concretely: (a) MLflow binds to loopback only and its host port is no longer published; (b) the web UI's "Open in MLflow" links route through an authenticated app route (e.g. `/v1/mlflow-proxy/`) instead of `http://<lan-ip>:5001`; (c) `--allowed-hosts` is NOT relied upon as the sole control (it is Host-header-bypassable). NOTE: a plain `--allowed-hosts localhost` change alone is both breaking (kills LAN "Open in MLflow") and insufficient (MLflow stays unauthenticated on its own port) — the reverse proxy is the required remediation.

#### High Severity (Endpoint Hardening & Secure Configuration)

- **FR-005**: All API endpoints that accept request bodies MUST validate input against typed schemas with appropriate constraints (string length limits, numeric ranges, required fields). At minimum, the 18+ endpoints currently accepting `body: dict` MUST be transitioned to typed validation.
- **FR-006**: System MUST enforce a maximum request body size to prevent resource exhaustion from oversized payloads.
- **FR-007**: File upload endpoints (dataset upload, content staging) MUST enforce a maximum file size limit with a clear error message when exceeded.
- **FR-008**: System MUST protect against ReDoS for user-supplied regex patterns by enforcing a wall-clock execution timeout. The timeout MUST be implemented without adding a runtime dependency — using a stdlib mechanism (a worker thread whose result is awaited with a timeout, or a `signal`-based alarm on platforms that support it). Note: Python's stdlib `re` module does NOT support a `timeout=` argument; the timeout MUST wrap regex *execution*, not be passed to `re.compile`.
- **FR-009**: System MUST enforce rate limiting to prevent brute-force and denial-of-service attacks, with configurable thresholds per endpoint or endpoint group.
- **FR-010**: System MUST return sanitized, generic error messages in API responses — internal paths, variable names, and exception details MUST NOT be exposed (replace `str(exc)` patterns).
- **FR-011**: CI/CD workflows (CI and release) MUST pin third-party GitHub Actions to specific SHA256 digests rather than floating branch tags.
- **FR-012**: The AuthzContext stub MUST either implement actual access control checks or be clearly documented as a no-op for local-only use, with a warning when used in network-accessible deployments.

#### Medium/Low Severity (Defense in Depth)

- **FR-013**: System MUST include security headers (Content-Security-Policy, Strict-Transport-Security, X-Frame-Options, X-Content-Type-Options) in HTTP responses.
- **FR-014**: System MUST apply an explicit CORS policy that restricts cross-origin requests to an allowlist, with a secure default for local-only operation.
- **FR-015**: Training start operations MUST support idempotency keys to prevent duplicate run creation from retried requests.
- **FR-016**: File path operations using user-influenced paths MUST contain a verification step ensuring the resolved path is within the expected directory.
- **FR-017**: Logging configuration MUST be initialized in the application lifespan (not only in the CLI entry point) so that all runtime paths produce structured logs.
- **FR-018**: Startup failures in non-critical initialization paths (license seeding, demo bootstrap, model warmup) MUST be logged at warning level rather than silently swallowed.
- **FR-019**: Output intended for operational logging (training progress, model warm-up, CLI status messages) MUST use structured logging instead of direct console output, so that all runtime events are recorded in the application log.
- **FR-020**: Docker base images MUST be pinned to SHA256 digests rather than floating version tags.
- **FR-021**: Version and system-fingerprint information MUST NOT be disclosed on the unauthenticated `/v1/health` endpoint. Because `/v1/health` is auth-exempt (for the Docker healthcheck), the public response MUST be reduced to a bare liveness payload (e.g. `{"status": "healthy"}`); detailed metrics (version, uptime, CPU/memory/disk, GPU details) MUST move to a separate authenticated endpoint (e.g. `/v1/health/detailed`). This resolves the contradiction where the prior FR-021/T012 attempted to gate data on an exempt route.
- **FR-022**: Optional dependency version bounds (`torch>=2.0`) SHOULD include an upper bound to prevent breaking changes.
- **FR-023**: The TOCTOU race condition in content lock acquisition MUST be resolved so that concurrent lock requests cannot interleave.
- **FR-024**: StaticFiles mount SHOULD explicitly declare `html=False` for clarity.

#### Review-Derived Requirements (added after adversarial spec review, 2026-06-21)

These requirements close gaps and contradictions found during critical review. Several are CRITICAL because the original auth design would break core functionality or introduce new vulnerabilities.

- **FR-025 (CRITICAL — SSE auth)**: The auth middleware MUST authenticate Server-Sent Events endpoints (e.g. `GET /v1/training/stream/{run_id}` and the 5 other `text/event-stream` routes) via the session cookie, because browser `EventSource` cannot send an `X-API-Key` header. For `/v1/*` routes the middleware MUST accept EITHER a valid `X-API-Key` header OR a valid session cookie (cookie fallback). Without this, the live training dashboard breaks the moment auth is enabled.
- **FR-026 (CRITICAL — credential disclosure)**: The API key MUST NOT be written to log files or any persistent, tailable store. On first generation only a short non-reversible hint (e.g. first 8 characters) MAY be emitted to the console. The full key MUST be retrievable only via an explicit `--show-api-key` CLI command. If supplied via `ANVIL_API_KEY`, the value MUST be read once and removed from the process environment to limit `/proc/<pid>/environ` exposure.
- **FR-027 (HIGH — CSRF)**: State-changing requests authenticated by session cookie (POST/PUT/DELETE from the web UI) MUST be protected against CSRF via a synchronizer token (signed per-session token delivered to the page and echoed in an `X-CSRF-Token` header validated server-side). `SameSite=Strict` MUST be set on the session cookie as defense-in-depth (the app has no legitimate cross-site usage). API-key-authenticated requests (header-based) are exempt from CSRF token checks because they cannot be driven by ambient browser credentials. The `/v1/mlflow-proxy/*` prefix (FR-004) is ALSO exempt from the CSRF token check, because the embedded MLflow SPA issues its own state-changing AJAX calls that cannot carry anvil's CSRF token; the exemption is safe because the proxy is same-origin and protected by `SameSite=Strict`.
- **FR-028 (HIGH — login brute force)**: The login endpoint MUST enforce a strict, separate rate limit (e.g. 5 attempts/minute per client) independent of the general API rate limit, plus a small fixed delay on failure, to prevent key brute-forcing. The login endpoint MUST NOT be exempt from rate limiting.
- **FR-029 (HIGH — CORS preflight & middleware order)**: The auth middleware MUST allow CORS preflight (`OPTIONS`) requests through without authentication. Middleware execution order MUST be defined and documented: rate-limit → CORS → security-headers → auth.
- **FR-030 (HIGH — silent exception scope)**: All silent `except ...: pass` / `except Exception: pass` patterns that swallow security-relevant errors MUST either be remediated (log at warning with context) or explicitly enumerated as accepted with a one-line rationale. The remediation MUST NOT be limited to the 4 startup paths in `app.py`; the full set discovered during review (~97 occurrences) MUST be triaged.
- **FR-031 (HIGH — auth migration safety)**: Enabling auth MUST be accompanied by coordinated updates so that dependent consumers do not break simultaneously: (a) ALL THREE test client fixtures inject auth — `tests/conftest.py` (shared ASGI `AsyncClient`), `tests/e2e/api/conftest.py` (whole-API e2e suite client), and `tests/browser/conftest.py` (Playwright browser context, via a login fixture or injected header); (b) the Docker/compose healthcheck targets an exempt endpoint or is given credentials; (c) browser SSE relies on the cookie path (per FR-025); (d) the `/v1/health` exemption is confirmed to cover the healthcheck. NOTE: the post-merge codebase added `tests/e2e/api/` (14 modules) and `tests/browser/` (Playwright) — both are currently auth-unaware and will fail the instant auth is enabled if not updated here.

#### Wontfix / Accepted Risks (Acknowledged in OWASP Review)

- **A02-001**: `random.choices()` for LLM token sampling — accepted as appropriate for non-security context.
- **A10-001**: User-configurable MLflow URI — accepted as deliberate configuration option for local-only use.

### Key Entities *(include if feature involves data)*

- **Security Finding**: A discrete vulnerability or security issue identified during the OWASP review, categorized by OWASP Top 10 category, severity, status, and affected file location.
- **Authentication Credential**: A token, key, or session that identifies and authorizes a user to access protected API endpoints.
- **Rate Limit Policy**: A configurable rule defining the maximum number of requests allowed from a client within a time window, optionally scoped to specific endpoints.
- **Idempotency Key**: A client-supplied unique identifier that ensures a mutating operation (e.g., training start) is performed exactly once, even if the request is retried.
- **CORS Allowlist**: A configured list of origins permitted to make cross-origin requests to the application.
- **Content Security Policy**: A configured set of directives that control which resources (scripts, styles, fonts) the browser is allowed to load.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 35 open security findings (4 CRITICAL, 12 HIGH, 12 MEDIUM, 7 LOW) are resolved, verified by re-running the OWASP review and confirming each finding's status changes from "open" to "resolved".
- **SC-002**: Zero CRITICAL or HIGH severity findings remain after remediation — the application must pass an equivalent security review with no findings above MEDIUM severity.
- **SC-003**: All HTTP routes (API and web pages) respond with authentication errors or login redirect when accessed without valid credentials. Verified by automated integration tests covering every route.
- **SC-004**: All 18+ endpoints currently accepting `body: dict` are migrated to typed validation schemas. Verified by automated tests sending invalid payloads to each endpoint.
- **SC-005**: Application can be deployed in a Docker container with digest-pinned base images. Verified by `docker build` succeeding and the runtime image showing the pinned digest.
- **SC-006**: CI/CD workflows complete successfully with SHA-pinned action references. Verified by workflow runs in CI.
- **SC-007**: All `str(exc)` patterns in API error handling are replaced with sanitized messages. Verified by code review and by triggering error conditions in integration tests.
- **SC-008**: No silent `except: pass` patterns remain in critical startup paths. Verified by code review and by simulating startup failures in test scenarios.
- **SC-009**: All `print()` calls used for operational output in runtime paths (CLI training progress, model warm-up sequence) are replaced with structured logging calls. Verified by code review and by inspecting log output during normal operation.

## Assumptions

- The application remains a local-first, single-user development tool. Authentication is intended to prevent unauthorized LAN access, not to support a multi-user SaaS model — full multi-tenant auth (Cognito/JWT per ADR-030) is a separate initiative.
- Authentication implementation uses a single API key auto-generated on first startup. The key value is NEVER written to log files (which are persistent and tailable via the operations page) or to stdout. On first generation, only a short non-reversible prefix hint (first 8 chars) plus recovery instructions are emitted to stderr only — not to persistent log files or stdout. The full key is retrievable on demand via a `--show-api-key` CLI command. The key can be overridden via the `ANVIL_API_KEY` environment variable (read once at startup, then popped from `os.environ` to limit `/proc` exposure). This ensures zero-friction local-first setup while guaranteeing every instance starts with active authentication and without disclosing the credential to persistent stores.
- Rate limiting will use a reasonable default (e.g., 100 requests/minute per endpoint) that is configurable via environment variable. The exact default is a tuning decision during implementation.
- File upload size limits default to 100 MB for datasets and 50 MB for content staging, adjustable via configuration.
- ReDoS protection enforces a wall-clock timeout on regex *execution* (not `re.compile`, which has no timeout parameter) for user-supplied patterns, default 2 seconds, via a stdlib mechanism (worker thread + timed join, or `signal.SIGALRM` on Unix) so no new dependency is introduced. On timeout the operation returns an error; normal operation is unaffected.
- Security headers use conservative defaults (e.g., CSP: `default-src 'self'`, HSTS: `max-age=31536000; includeSubDomains`).
- CORS is explicitly configured with an allowlist; if no origins are configured, the system defaults to same-origin only.
- Idempotency keys are client-generated unique identifiers passed with each mutating request; expired keys are cleaned up after a configurable time window.
- The existing AuthzContext stub in `anvil/services/content/authz.py` will be documented as a local-mode no-op and potentially gated behind a configuration flag.
- Findings already marked "wontfix" or acknowledged as acceptable risk (A02-001, A10-001) are explicitly out of scope for remediation.