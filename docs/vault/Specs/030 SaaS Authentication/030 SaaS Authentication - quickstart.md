---
title: 030 SaaS Authentication - quickstart
type: quickstart
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
# Quickstart: SaaS Authentication Development

## Prerequisites

### Local Development (against dev Cognito pool)

- Python 3.11+
- AWS CLI configured with access to a dev AWS account
- Cognito User Pool created (via CDK or deploy CLI)
- `anvil[aws]` installed (`pip install anvil[aws]`)

### Local Mode (no auth)

- Python 3.11+
- `pip install anvil` (no extra)
- No Cognito, no JWT, no auth config needed

---

## Mode 1: No Auth (Local — Unchanged)

```bash
pip install anvil
anvil serve
# → http://localhost:8080
# All routes accessible without authentication
```

No auth middleware wired. No Cognito dependency.

---

## Mode 2: Auth-Enabled Development

```bash
pip install anvil[aws]

ANVIL_MODE=saas \
COGNITO_USER_POOL_ID=us-east-1_xxxxxxxxx \
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx \
COGNITO_REGION=us-east-1 \
SSE_TOKEN_SIGNING_SECRET=dev-secret-not-for-prod \
uvicorn anvil._saas.app:app --reload
```

Then open the app — you will be redirected to Cognito Hosted UI for login.

---

## Mode 3: Test Auth Flow

```bash
# Create a test user programmatically (via boto3)
python -c "
import boto3
client = boto3.client('cognito-idp', region_name='us-east-1')
client.admin_create_user(
    UserPoolId='us-east-1_xxxxxxxxx',
    Username='test@example.com',
    TemporaryPassword='TempPass123!',
    UserAttributes=[{'Name': 'email', 'Value': 'test@example.com'}]
)
"

# Obtain a JWT for the test user
python -c "
from aws_jwt_verify import cognito_jwt
# Use the library to verify tokens
print('JWT validation configured')
"

# Test token validation
curl -H 'Authorization: Bearer <id_token>' http://localhost:8080/v1/health
# → 200 OK

curl -H 'Authorization: Bearer invalid_token' http://localhost:8080/v1/datasets
# → 401 Unauthorized
```

---

## Mode 4: CLI Device Grant Auth

```bash
# Device grant login (FR-021)
anvil remote login <cluster>

# CLI opens browser → user authenticates via Cognito Hosted UI
# CLI polls token endpoint → receives JWT pair
# JWT cached in ~/.anvil/credentials/<cluster> (0600)
```

---

## Auth Debugging

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| 401 on every request | JWT not sent or expired | Re-authenticate via Cognito Hosted UI |
| `aws-jwt-verify` import error | `[aws]` extra not installed | `pip install anvil[aws]` |
| Cognito redirect loops | Invalid callback URL | Check `UserPoolClient` callback URLs in CDK |
| SSE stream 401 | SSE token expired (TTL window) | Re-request SSE token |
| CLI "device grant not supported" | Cognito app client missing `ALLOW_OAUTH_DEVICE_CODE` | Add `ALLOW_OAUTH_DEVICE_CODE` to client OAuth flows |

---

## Architecture Cheatsheet (Auth)

| Layer | Local (no auth) | SaaS (Cognito) |
|-------|----------------|----------------|
| **Auth provider** | None | Cognito User Pool |
| **JWT validation** | None | `aws-jwt-verify` middleware |
| **get_current_user** | Not wired | `anvil/_saas/auth/deps.py` |
| **Login UI** | None | Cognito Hosted UI |
| **SSE auth** | None | Signed query-param token |
| **CLI auth** | None | OAuth2 device grant |
| **User table** | Not consulted | `users` with `cognito_sub` → `user_id` |
| **Route protection** | All public | All except `/v1/health`, `/v1/version` require JWT |

## Project Commands (Auth-related)

```bash
# Build and test
make setup        # Set up venv with [aws] extras
make test         # Run all tests (including auth contract tests)
make typecheck    # Verify mypy strict with aws-jwt-verify

# CDK Cognito construct
cd packages/infra
npx cdk synth     # Verify Cognito User Pool template
npx cdk deploy    # Deploy Cognito + full stack
```