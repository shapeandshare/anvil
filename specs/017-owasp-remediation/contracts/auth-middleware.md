# Auth Middleware Contract

**Phase**: 1 (Design & Contracts) | **Date**: 2026-06-21 | **Plan**: `plan.md`

## Purpose

Define how authentication is enforced across all HTTP routes (API + web UI) in the anvil application.

## Authentication Methods

### 1. API Key (Programmatic Access)

- **Header**: `X-API-Key: <key>`
- **Key format**: 43-character URL-safe base64 string (`secrets.token_urlsafe(32)`)
- **Auto-generated**: On first startup. **Never written to logs** — only a prefix hint is shown on the console; the full key is retrievable via `--show-api-key` (C-4/FR-026)
- **Override**: `ANVIL_API_KEY` environment variable
- **Validation**: Constant-time comparison (`secrets.compare_digest`) to prevent timing attacks

### 2. Session Cookie (Web UI Access)

- **Login endpoint**: `POST /login` with `body: {"api_key": "..."}`
- **Cookie name**: `anvil_session`
- **Cookie attributes**: `HttpOnly`, **`SameSite=Strict`**, `Secure` (in production), `Path=/`, **`Max-Age=86400`** (aligned with server-side expiry to avoid browser/server drift)
- **Session expiry**: 24 hours sliding (reset on each authenticated request)
- **Logout**: `POST /logout` clears session cookie
- **CSRF**: cookie-authenticated state-changing requests (POST/PUT/DELETE) MUST carry a valid `X-CSRF-Token` (see CSRF section below)

> ⚠️ **CRITICAL DESIGN FIX (review finding C-2 / FR-025) — SSE + cookie fallback.**
> Browser `EventSource` (SSE) **cannot send an `X-API-Key` header**. The original design (header-only for `/v1/*`) breaks all 6 SSE endpoints — most importantly the live training stream `GET /v1/training/stream/{run_id}` that drives the hero dashboard. Therefore `/v1/*` routes MUST accept **EITHER** a valid `X-API-Key` header **OR** a valid session cookie. This is implemented as a cookie fallback in the middleware below.

## Route Classification

| Classification | Behavior | Routes |
|---------------|----------|--------|
| **Public** (no auth) | Accessible without any credential | `GET /login`, `POST /login`, `GET /static/*`, `GET /v1/health` |
| **API** (key OR cookie) | Valid `X-API-Key` header **OR** valid session cookie (cookie path required for browser SSE) | All `/v1/*` API + SSE routes except `/v1/health` |
| **Web Page** (session) | Valid session cookie; redirect to `/login` if missing | Page routes (`/`, `/v1/*-page`, `/v1/learn/*`, etc.) |

> **Note on route disambiguation**: API routes and page routes BOTH live under the `/v1/` prefix, so the prefix alone cannot classify them. The middleware MUST use an explicit page-route registry (or a dedicated sub-prefix) to decide redirect-vs-401 behavior. A request that fails auth is given a `303 → /login` if it targets a known page route or accepts `text/html`; otherwise it gets a `401`.

## Auth Middleware Implementation

### FastAPI Middleware (`@app.middleware("http")`)

Middleware execution order (FR-029): **rate-limit → CORS → security-headers → auth**.

```python
PAGE_ROUTES = {"/", ...}          # explicit set of HTML page paths
PAGE_PREFIXES = ("/v1/learn",)    # plus page sub-prefixes; *-page suffix also treated as page

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # 1. CORS preflight must bypass auth (FR-029)
    if request.method == "OPTIONS":
        return await call_next(request)

    # 2. Exempt routes
    if path in EXEMPT_ROUTES or path.startswith("/static/"):
        return await call_next(request)

    # 3. Resolve identity: header OR cookie (cookie fallback enables browser SSE — FR-025)
    api_key = request.headers.get("X-API-Key")
    session_id = request.cookies.get("anvil_session")
    authed = (
        (api_key is not None and verify_api_key(api_key))
        or (session_id is not None and validate_session(session_id))
    )

    if not authed:
        # Pages (or browsers asking for HTML) get a login redirect; APIs get 401
        if _is_page_route(path) or "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(url="/login", status_code=303)
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

    # 4. CSRF check for cookie-authenticated state-changing requests (FR-027)
    if session_id and not api_key and request.method in ("POST", "PUT", "DELETE", "PATCH"):
        if not verify_csrf(request, session_id):
            return JSONResponse(status_code=403, content={"detail": "CSRF token invalid or missing"})

    return await call_next(request)
```

### Exempt Routes (no auth required)

```python
EXEMPT_ROUTES = {
    "/login",
    "/v1/health",   # bare liveness only; detailed metrics move to /v1/health/detailed (FR-021)
}

EXEMPT_PREFIXES = {"/static"}
```

## CSRF Protection (FR-027)

- On every authenticated **page render**, emit a signed token: `hmac_sha256(session_id, server_secret)` as a `<meta name="csrf-token">` tag.
- Client JS reads the meta tag and sends it as `X-CSRF-Token` on all `fetch()` POST/PUT/DELETE/PATCH calls.
- `verify_csrf()` recomputes the HMAC and compares with `secrets.compare_digest`.
- **Header (`X-API-Key`) authenticated requests are exempt** from CSRF — they cannot be driven by ambient browser credentials, so CSRF does not apply.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `OPTIONS` preflight | Always pass through without auth (FR-029) |
| Browser SSE (`EventSource`) to `/v1/training/stream/...` | Authenticated via session cookie (cookie fallback) — never blocked for lacking `X-API-Key` (FR-025) |
| Invalid API key format (too short, non-URL-safe) | 401 `{"detail": "Authentication required"}` (do not echo the reason in detail) |
| Missing both API key and session cookie | Page/HTML request: 303 → `/login`. API request: 401 |
| Cookie-auth POST without CSRF token | 403 `{"detail": "CSRF token invalid or missing"}` (FR-027) |
| Expired session cookie | Redirect to `/login` (page) or 401 (API) |
| API key in query string | Not supported. 400 |
| `POST /login` brute force | Strict per-IP rate limit (5/min) + failure delay (FR-028) |

## Future Remediation Markers (per C-2 directive)

The implementation MUST leave explicit, greppable markers so future hardening efforts can find these
deliberate tradeoffs. Add these in code comments, the operations/security docs, and the architecture
diagrams:

- `# SECURITY-FUTURE(C-2/FR-025): cookie fallback on /v1/* exists ONLY because browser EventSource
  cannot send X-API-Key. Revisit if SSE is replaced by a transport that supports custom headers
  (e.g. fetch-streams / WebSocket with subprotocol token).`
- Documentation note (security README + `DESIGN.md` if UI-facing): the dual header-or-cookie model for
  `/v1/*` is intentional and its rationale.
- Architecture diagram: annotate the auth middleware node with "header OR cookie (SSE)" and a footnote
  referencing C-2/FR-025.
| Multiple `X-API-Key` headers | Use first value. Log warning if multiple. |