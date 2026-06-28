---
title: 030 SaaS Authentication - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/030 SaaS Authentication/
related:
  - '[[030 SaaS Authentication]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---
# Feature Specification: SaaS Authentication — App-Managed Cognito OIDC/JWT

**Feature Branch**: `030-saas-authentication`
**Created**: 2026-06-27
**Status**: Draft

## User Story 1 — SaaS User Signs Up and Logs In via Google/GitHub/Email (Priority: P1)

A new user visits anvil.io and either signs in with Google/GitHub or creates a passwordless account via email magic link (Cognito Hosted UI). They are authenticated and redirected to the dashboard. Session management (tokens, refresh, MFA) is handled entirely by Cognito.

**Why this priority**: Multi-tenancy is the foundation of SaaS mode. Using Cognito means zero auth code to maintain — no password hashing, no token management, no session storage. Social login also eliminates registration friction.

**Independent Test**: Visit the SaaS deployment, click "Sign in with Google" (or use the equivalent test user in dev Cognito pool), complete the OAuth flow, and verify the user lands on the dashboard with their email displayed. Verify the session persists across page reloads.

**Acceptance Scenarios**:

1. **Given** a new user visits anvil.io, **When** they click "Sign in with Google" (or GitHub, or Apple), **Then** they are redirected to the provider's OAuth consent screen, and on approval they land on the anvil dashboard authenticated.
2. **Given** a new user visits anvil.io, **When** they choose email/password registration via Cognito Hosted UI, **Then** their account is created, they are redirected to the dashboard, and a JWT session is established.
3. **Given** a previously authenticated user returns, **When** their session is still valid (Cognito refresh token), **Then** they see the dashboard without re-authentication.
4. **Given** a user signs out, **When** they click logout, **Then** their Cognito session is revoked and they are redirected to the login page.

---

## Functional Requirements

**Owned FRs from the umbrella spec (016)**:

- **FR-001 (auth aspect)**: System MUST use Amazon Cognito User Pools as the sole authentication provider for SaaS mode — no custom auth code (no password hashing, no JWT issuance, no token storage in the application).
- **FR-002**: Cognito MUST be configured with at least one social identity provider (Google or GitHub) plus email/password via Cognito Hosted UI.
- **FR-003**: System MUST scope all data access (corpora, datasets, experiments, models) by the Cognito `sub` (user UUID) derived from the authenticated JWT, mapped to a local integer `user_id` on first login.
- **FR-018**: Cognito Hosted UI MUST handle user-facing login, registration, password reset, and MFA enrollment. The anvil application does not implement any of these flows.
- **FR-019**: Authentication MUST use the **app-managed OIDC/JWT** pattern (NOT ALB-managed auth). The FastAPI backend receives the Cognito bearer token directly and validates it against Cognito's JWKS endpoint via `aws-jwt-verify` in a middleware dependency. ALB does NOT perform `authenticate-cognito`. This single pattern works identically across CloudFront, ALB, direct API access, and CLI.
- **FR-020**: SSE endpoints MUST authenticate via a short-lived signed token passed as a query parameter (since `EventSource` cannot set custom headers). The server issues this token from a validated session; it is single-use or short-TTL and scoped to the specific job stream.
- **FR-021**: CLI authentication MUST use Cognito's OAuth2 device authorization grant (RFC 8628) — the CLI opens a browser for the user to authenticate, then polls the token endpoint. No hardcoded API keys, no custom token endpoints.
- **FR-021a**: Native Cognito email/password users MUST work out of the box with zero post-deploy configuration. Social login (Google, GitHub) MUST be optional and configured AFTER deploy via `anvil deploy config set-idp` once the CloudFront/custom domain (and therefore the OAuth callback URL) is known. The customer brings their own OAuth client ID and secret (BYO identity provider).
- **FR-022**: The anvil application's Cognito User Pool MUST be deployed via the CDK stack as a first-class resource — no separate Cognito setup outside of `anvil deploy`.
- **FR-023**: A local `users` table in PostgreSQL MUST map Cognito `sub` (UUID) to a local integer `user_id` for efficient FK relationships. The mapping is created on first login via a Cognito post-authentication Lambda trigger or a first-request middleware handler.

## Edge Cases

- What happens when two users register with the same email? Cognito enforces email uniqueness in the user pool. The second registration attempt receives an error from Cognito Hosted UI.
- What happens when a user's social login account (Google/GitHub) is deactivated? Cognito's federation means the user can no longer authenticate through that provider. They may have a separate email/password account or need to contact support.
- What happens if the user forgets their password? Cognito Hosted UI provides a built-in "Forgot password" flow with email verification code or magic link.
- What happens to a user's data when their account is deleted? The `users` table entry and all scoped data remain (orphaned) unless a cleanup process is triggered. Mitigation: admin can delete user via Cognito + cascade delete local data.
- What happens in local mode when `ANVIL_MODE=saas` is not set? Local mode runs the `anvil.api.app:app` entrypoint, which has no import path to `anvil/_saas/` — SaaS modules are never loaded and no cloud service is contacted (FR-011, FR-011a).

## Architecture Decisions

### AD-2: Authentication — App-Managed OIDC/JWT

**Decision**: FastAPI validates Cognito JWTs directly via `aws-jwt-verify`. ALB does NOT do `authenticate-cognito`. (See FR-019.)

**Rationale**: Review CRITICAL finding — ALB-managed and app-managed auth are different patterns and must not be mixed. App-managed works identically across CloudFront, ALB, direct API, and CLI, and is the only pattern compatible with bearer-token CLI access.

### AD-3: Social Login — Native Default, BYO Social

**Decision**: Email/password Cognito users work out of the box. Social login is post-deploy, optional, BYO OAuth credentials. (See FR-021a.)

**Rationale**: Review HIGH finding — per-customer Cognito pools need per-customer OAuth apps with callback URLs not known until after deploy. Making social login post-deploy preserves the true one-command install.

---

## Gate G3 — Cognito Auth

**Acceptance Gate**: Cognito pool exists; invalid token → 401; valid token → 200; first login creates `users` row; SSE token auth works.

| Check | Method | Expected |
|-------|--------|----------|
| Cognito User Pool created | CDK synth / describe | Pool exists with native email/password, app client, Hosted UI domain |
| Invalid JWT → 401 | `GET /v1/protected-endpoint` with bogus `Authorization: Bearer xxx` | `401 Unauthorized` |
| Valid JWT → 200 | `GET /v1/protected-endpoint` with valid Cognito JWT | `200 OK`, caller identity in response |
| First login creates `users` row | Authenticate a test user never seen before, then query `users` table | Row exists with `cognito_sub` matching the JWT `sub` claim and a local integer `user_id` |
| SSE signed-token auth | Obtain a valid session, request SSE token, connect to SSE endpoint with token in query | SSE stream delivers events; token without session → 401 |
| Public routes accessible without auth | `GET /v1/health`, `GET /v1/version` | `200 OK` |
| CLI device grant scaffolding | CLI opens browser; completes OAuth2 device grant flow | CLI receives JWT pair from Cognito token endpoint |

---

## Local-Mode Regression Gate (LMRG)

Every feature's Definition of Done includes ALL of:

```bash
make test            # all pre-existing tests pass UNMODIFIED (SC-007)
make lint            # zero new lint errors
make typecheck       # mypy --strict clean; no SaaS imports leaking into non-SaaS modules
pip install .        # clean install
anvil serve          # boots; UI at :8080 works end-to-end (upload → train → SSE → export)
```

Plus the **import-isolation assertion** (cheap, run in CI on every feature):

```bash
# No SaaS module is reachable from the local entrypoint, and no cloud SDK is importable
# in a base (no-extras) install.
python - <<'PY'
import importlib, sys
import anvil.api.app          # local entrypoint must import with zero cloud deps
for forbidden in ("boto3", "redis", "aws_jwt_verify", "opentelemetry", "prometheus_client"):
    assert forbidden not in sys.modules, f"{forbidden} loaded by local entrypoint"
print("import isolation OK")
PY
```

**Specific to Feature 3 (Cognito Authentication)**:

- The **local app factory wires NO JWT middleware**; `anvil serve` requires no token and contacts no Cognito endpoint.
- Import-isolation assertion confirms `aws_jwt_verify` is absent from a base install.
- Local mode: `ANVIL_MODE` unset or `local` → no JWT validation, no Cognito redirect, all routes operate without auth (FR-038b).

---

## Success Criteria (Auth Subset)

- **SC-001 (partial)**: A new user can register, log in, upload data, start training, and see live metrics — all from the browser — within 5 minutes of first visiting anvil.io. (Auth portion: registration and login complete within 5 minutes.)
- **SC-006**: Local mode (`pip install anvil && anvil serve`) has zero SaaS dependencies and no behavioral changes from the pre-SaaS version.

---

## Assumptions

- The Cognito User Pool is created by the CDK stack. The app client, domain name (e.g., `auth.anvil.io`), and identity providers are configured in CDK.
- Authentication is app-managed (AD-2): the FastAPI app validates Cognito JWTs in middleware via `aws-jwt-verify`. The ALB does NOT perform `authenticate-cognito`. Unauthenticated browser requests are redirected to Cognito Hosted UI by the application, not the ALB.
- **Local mode has no authentication**: When `ANVIL_MODE` is unset or `local`, JWT validation middleware is not wired, the Cognito redirect does not apply, and all API routes operate without auth. The local-mode user implicitly has all cluster admin capabilities (FR-038b).
- SSE authentication: since EventSource cannot set custom headers, the SSE endpoint reads a short-lived signed token from a query parameter, issued by the app from a validated session (FR-020).
- CLI authentication uses Cognito's OAuth2 device authorization grant flow: the CLI opens a browser window for the user to sign in, then exchanges the authorization code for tokens.
- A local `users` table exists in PostgreSQL to map Cognito `sub` (UUID) to a local integer `user_id`. This is populated on first login via a Cognito post-authentication trigger (Lambda) or an application middleware that checks and creates the mapping on each authenticated request.