---
title: 030 SaaS Authentication - research
type: research
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
# Research: SaaS Authentication — App-Managed Cognito OIDC/JWT

**Phase 0 output** — resolves all auth-specific research unknowns for implementation planning.

> [!NOTE]
> **Superseded by post-review decision**: The original umbrella spec explored BOTH ALB-managed and app-managed auth. The architecture review (Oracle) flagged mixing them as a CRITICAL mismatch. The binding decision is **AD-2: app-managed OIDC/JWT only** — the FastAPI app validates Cognito JWTs via `aws-jwt-verify`; the ALB does NOT perform `authenticate-cognito`. Treat ALB-auth references below as "option considered, not chosen."

## 1. Cognito Integration

### Decision
Amazon Cognito User Pools with **app-managed** OIDC/JWT validation via `aws-jwt-verify` (AD-2). ALB-managed auth was considered but rejected to avoid the dual-pattern mismatch.

### Rationale
- ALB can authenticate against Cognito natively, setting `x-amzn-oidc-*` headers on forwarded requests
- No custom auth code, no password hashing, no session management in the application
- `aws-jwt-verify` (AWS Labs) is the official JWT verification library — handles Cognito JWTs
- Cognito Hosted UI provides login/registration/password-reset/MFA out of the box
- Social login (Google, GitHub) is configured in CDK with `UserPoolIdentityProvider*` constructs

### Key Findings

| Aspect | Decision |
|--------|----------|
| **Auth pattern** | App-managed OIDC/JWT (NOT ALB `authenticate-cognito`) |
| **JWT validation** | `aws-jwt-verify` library in FastAPI middleware — validates Cognito JWT against JWKS endpoint |
| **Browser auth** | Application redirects unauthenticated requests to Cognito Hosted UI |
| **SSE auth** | Short-lived signed token passed as query parameter (FR-020) |
| **CLI auth** | OAuth2 Device Authorization Grant (RFC 8628) — user authenticates via browser popup |
| **User mapping** | Cognito Post-Authentication Lambda trigger OR first-request middleware handler — upserts local `users` table mapping Cognito `sub` → integer `user_id` |
| **CDK constructs** | `cognito.UserPool` + `UserPoolIdentityProviderGoogle` + `UserPoolIdentityProviderOidc` + `user_pool.add_client()` |
| **Lambda trigger CDK** | `cognito.UserPool.add_trigger(CognitoUserPoolTriggers.POST_AUTH, lambda_fn)` |

### Pipe (✗ / ✓)

| Requirement | Status |
|-------------|--------|
| Native email/password via Cognito Hosted UI | ✓ — CDK construct configures `passwordless` or email/password |
| Social login (Google, GitHub) | ✓ — optional, post-deploy BYO (AD-3) |
| `aws-jwt-verify` validates Cognito JWTs | ✓ — FastAPI dependency |
| `get_current_user` creates `users` row on first login | ✓ — middleware or Lambda |
| SSE signed-token auth | ✓ — short-TTL, scoped to job stream |
| CLI device grant | ✓ — RFC 8628 flow |
| No ALB `authenticate-cognito` | ✓ — AD-2 binding decision |

### Alternatives Considered
- **ALB-managed auth** (rejected): Sets `x-amzn-oidc-*` headers but breaks CLI bearer-token access and mixes auth patterns.
- **Custom JWT auth** (rejected): More control but adds security surface area and maintenance burden.
- **Auth0** (rejected): Excellent product but adds a third-party dependency outside AWS.
- **FastAPI middleware-only without Cognito** (rejected): Works but no built-in Hosted UI, no social login, no MFA.

## 2. SSE Token Authentication

### Decision
SSE endpoints authenticate via a short-lived signed token passed as a query parameter. The server issues this token from a validated session; it is single-use or short-TTL and scoped to the specific job stream.

### Rationale
- `EventSource` (browser SSE API) cannot set custom `Authorization` headers
- Cognito tokens in query params would be logged by ALB/CloudFront — this wrapping avoids that
- Short TTL + job-scoping limits the blast radius of a leaked token
- Dual-key window in rotation (FR-045s) prevents rotation from invalidating in-flight streams

### Key Findings

| Aspect | Decision |
|--------|----------|
| **Issuer** | Application, from a validated JWT session |
| **Duration** | Short TTL (e.g., 5 minutes) OR single-use |
| **Scope** | Scoped to specific `job_id` stream |
| **Validation** | HMAC-signed with SSE signing secret from Secrets Manager |
| **Rotation** | Dual-key window: current + previous secret both accepted during overlap |
| **Storage** | SSE signing secret in Secrets Manager (FR-045d), NOT in code or env |

### Alternatives Considered
- JWT in query param: Works but exposes the user's long-lived token to logs. Rejected.
- No auth on SSE (rejected): Would bypass all auth for training data streaming.

## 3. Cognito User Pool CDK Construct

### Decision
The CDK construct at `packages/infra/lib/cognito-auth.ts` creates the User Pool, app client, Hosted UI domain, and identity provider configuration. No ALB `authenticate-cognito` action.

### Rationale
- CDK is the single source of truth for infrastructure
- `cognito.UserPool` + `UserPoolDomain` + `UserPoolClient` + identity provider constructs
- Post-auth Lambda triggers are wired in the same construct

### Key Findings

| Aspect | Decision |
|--------|----------|
| **Pool** | `cognito.UserPool` with email/password and self-sign-up enabled |
| **Client** | `cognito.UserPoolClient` with OAuth 2.0 scopes (openid, email, profile) |
| **Domain** | `cognito.UserPoolDomain` — `auth.{domain}` (from deploy config) |
| **Identity providers** | `UserPoolIdentityProviderGoogle` + `UserPoolIdentityProviderOidc` (GitHub) — BYO after deploy |
| **Post-auth Lambda** | `user_pool.add_trigger(CognitoUserPoolTriggers.POST_AUTH, lambda_fn)` |
| **Lambda code** | Inline or S3-versioned, NOT a CDK asset (AD-7) |
| **No ALB auth** | ALB does NOT carry an `authenticate-cognito` rule — app-managed only (AD-2) |

## 4. User Mapping (Cognito `sub` → Local `user_id`)

### Decision
Two approaches explored, either acceptable:
1. **Cognito Post-Authentication Lambda trigger**: Lambda fires on every successful authentication, upserts the `users` row.
2. **First-request middleware handler**: `get_current_user` dependency checks if the `cognito_sub` exists; if not, creates the row on the first authenticated request.

### Rationale
- Local integer `user_id` is required for efficient FK relationships
- Cognito `sub` is the canonical auth identity — never owned by the application
- Lambda approach offloads the upsert to the auth path; middleware approach keeps all user logic in the application code

### Key Findings

| Aspect | Lambda approach | Middleware approach |
|--------|----------------|-------------------|
| **Location** | `packages/infra/lambdas/post_auth.py` | `anvil/_saas/auth/deps.py` |
| **Trigger** | Cognito post-authentication event | First authenticated request per user |
| **Latency** | Adds ~100ms to login (Lambda cold start) | Zero additional auth latency |
| **Complexity** | Separate Lambda deployment + IAM | Same process as JWT validation |
| **Consistency** | Atomic with auth event | Slight window between auth and row creation |
| **Recommended** | ✅ Preferred for production | ✅ Acceptable for v1 |

## Summary of Architecture Decisions

| Area | Decision | Impact |
|------|----------|--------|
| **Auth provider** | Cognito User Pools (app-managed OIDC/JWT) | Zero custom auth code |
| **JWT validation** | `aws-jwt-verify` against JWKS endpoint | No JWT signing secret in app |
| **Browser auth** | App redirects to Cognito Hosted UI | Full login/MFA/password-reset out of the box |
| **SSE auth** | Short-lived signed query-param token (FR-020) | Works with EventSource; prevents token leakage in logs |
| **CLI auth** | OAuth2 Device Authorization Grant (RFC 8628) | No API keys; browser-based auth for CLI |
| **User mapping** | Lambda or middleware, `cognito_sub` → `user_id` | Efficient FK relationships |
| **Social login** | Optional, post-deploy BYO (AD-3) | One-command deploy not blocked by OAuth callback URL |
| **Infra** | CDK `cognito-auth.ts` construct | Single source of truth for Cognito resources |

## References

- [[030 SaaS Authentication]]
- [[030 SaaS Authentication - spec|spec]]
- [[030 SaaS Authentication - plan|plan]]
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] (AD-2, AD-3)
- [[Reference/SaaSArchitecture|SaaSArchitecture]] (auth topology)