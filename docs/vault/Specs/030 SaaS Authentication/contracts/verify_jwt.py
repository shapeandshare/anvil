"""
Contract: Cognito JWT Verification — verify_jwt.

The JWT verification contract specifies how Cognito bearer tokens are validated
by the anvil FastAPI application in SaaS mode (AD-2, FR-019).

Implementations:
- `anvil/_saas/auth/verify_jwt.py` — production implementation using `aws-jwt-verify`
- Local mode — no-op (no JWT validation)

Boundary
--------
Input:     `Authorization: Bearer <token>` from incoming HTTP request
Output:    Validated Cognito claims dict (or 401 rejection)

Dependencies
------------
- `aws-jwt-verify` library (optional [aws] extra, NEVER loaded in local mode)
- Environment: `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `COGNITO_REGION`

Fixture (Cognito JWKS)
----------------------
- Validate `kid` matches a key in the JWKS endpoint
  `https://cognito-idp.{region}.amazonaws.com/{userPoolId}/.well-known/jwks.json`
- Verify token signature, expiry (`exp`), issuer (`iss`), client ID (`aud`/`token_use`)
- Extract claims: `sub` (UUID), `email`, `cognito:username`, `token_use`, `iss`, `exp`

Contract
--------
1. `verify_jwt(token: str) -> dict`:
   - Returns decoded + validated claims from a Cognito id_token or access_token
   - Raises `UnauthorizedError` (401) if token is invalid, expired, or has wrong issuer/audience
   - Caches JWKS for the default TTL (1 hour, per aws-jwt-verify cache behavior)

2. Token types:
   - `id_token`: Primary auth token carrying user claims (sub, email, name)
   - `access_token`: For API authorization; verify against Cognito pool
   - Both must be accepted; `token_use` claim distinguishes them

Error Handling
--------------
- Malformed token → 401 with generic "Invalid token" (no detail leakage)
- Expired token → 401 with "Token expired"
- Wrong issuer/client → 401 with "Token audience/issuer mismatch"
- JWKS fetch failure → 503 with "Auth service unavailable" (JWKS endpoint timeout)
"""
