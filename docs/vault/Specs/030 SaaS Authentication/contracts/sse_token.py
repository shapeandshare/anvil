"""
Contract: SSE Authentication via Short-Lived Signed Token — sse_token.

SSE endpoints cannot use the standard `Authorization: Bearer` header because
the browser `EventSource` API does not support custom headers. Instead, SSE
authenticates via a short-lived signed token passed as a query parameter (FR-020).

Implementations:
- `anvil/_saas/auth/sse_token.py` — production implementation
- Local mode — no SSE auth needed (all routes public)

Boundary
--------
Input:     `GET /v1/training/stream/{job_id}?sse_token=<signed_token>`
Output:    SSE event stream (authenticated) or 401

Dependencies
------------
- SSE signing secret from Secrets Manager (FR-045d): stored as JSON `{current, previous}`
- HMAC-SHA256 signing of the token payload

Fixture (Token Structure)
-------------------------
The signed token is an HMAC-SHA256 signature over a JSON payload:
```json
{
  "job_id": 42,
  "user_id": 7,
  "exp": 1719390000,
  "iat": 1719389700,
  "nonce": "random-unique-value"
}
```

The query parameter value is `base64url(json_payload).base64url(signature)`.

Contract
--------
1. `issue_sse_token(user_id: int, job_id: int, secret: str) -> str`:
   - Issues a single-use or short-TTL (default 5 minutes) signed token
   - Token is scoped to a specific `job_id` — cannot be replayed for other jobs
   - Contains a nonce to prevent replay attacks
   - Signs with HMAC-SHA256 using the `current` signing secret

2. `verify_sse_token(sse_token: str, job_id: int, current_secret: str, previous_secret: str | None) -> int`:
   - Decodes token from base64url
   - Verifies HMAC-SHA256 signature against `current_secret` first, then `previous_secret`
   - Checks: token not expired (`exp`), matches `job_id`, nonce not replayed
   - Returns `user_id` (integer) on success
   - Raises `UnauthorizedError` (401) on failure

3. Secret rotation (FR-045s):
   - `current_secret`: used for signing new tokens
   - `previous_secret`: accepted for verification only (tokens signed before rotation)
   - Verification tries `current` first, then `previous`

Error Handling
--------------
- Malformed token → 401 with "Invalid SSE token"
- Expired token → 401 with "SSE token expired"
- Job ID mismatch → 401 with "SSE token scope mismatch"
- Invalid signature → 401 with "SSE token signature invalid"
"""
