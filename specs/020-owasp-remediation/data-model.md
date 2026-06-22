# Data Model: OWASP Security Remediation

**Phase**: 1 (Design & Contracts) | **Date**: 2026-06-21 | **Plan**: `plan.md`

## 1. API Key Configuration

### Runtime Config (persisted to a `0600` state file or app DB — NOT logs)

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `key` | `str` | Auto-generated (`secrets.token_urlsafe(32)`) or `ANVIL_API_KEY` env var | 43-char URL-safe random token |
| `generated_at` | `datetime` | Auto-set on first generation | Timestamp of key creation |
| `source` | `enum(auto, env)` | Set at startup | Whether the active key was auto-generated or supplied via env var |

**Lifecycle**:
- Generated once on first startup (in FastAPI lifespan) if no `ANVIL_API_KEY` env var and no persisted key exists
- Persisted to a `0600`-permission state file (or the app DB) so it survives restarts and is retrievable
- **NEVER written to log files.** On first generation, only a short prefix hint (first 8 chars) + recovery instructions are emitted to the console (stderr)
- Full key retrievable on demand via the `--show-api-key` CLI command
- Overridable via `ANVIL_API_KEY` environment variable. When supplied via env var, the value is read once at startup and then removed from `os.environ` (`os.environ.pop`) to limit `/proc/<pid>/environ` exposure

**Validation rules**:
- Must be at least 16 characters if user-supplied via env var
- Must be URL-safe (alphanumeric + `-_` only)
- Case-sensitive
- Validated with constant-time comparison (`secrets.compare_digest`) — never `==`

**Security constraints (from review FR-026)**:
- The key MUST NOT appear in any log file, the operations-page log tail, or `stdout` captured by Docker
- The console hint MUST be non-reversible (prefix only)
- Generation MUST use a CSPRNG (`secrets`), never `random`

---

## 2. Rate Limit Policy

### In-memory config (no DB — config object in middleware)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `requests_per_minute` | `int` | `100` | Max requests per client per minute |
| `burst_size` | `int` | `20` | Max burst requests before throttling kicks in |
| `enabled` | `bool` | `true` | Master toggle |
| `exempt_routes` | `list[str]` | `["/v1/health", "/static"]` | Routes not subject to general rate limiting (see §Login Rate Limit for /login) |

**Configuration source**: `ANVIL_RATE_LIMIT` env var overrides defaults (JSON string) or config module constant.

### Login Rate Limit (separate, stricter, FR-028)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `login_attempts_per_minute` | `int` | `5` | Max POST /login attempts per client IP per minute |
| `failure_delay_ms` | `int` | `1000` | Fixed delay after each failed login attempt |

The login endpoint has its own strict rate limit independent of the general API rate limit.
`POST /login` is NOT exempt from the general rate limit — it is governed by this separate, stricter policy.

---

## 3. Security Headers Configuration

### Static config (hardcoded defaults in middleware)

| Header | Value | Rationale |
|--------|-------|-----------|
| `Content-Security-Policy` | `default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; script-src 'self';` | Allows existing inline styles (design system), self-hosted assets. No external scripts. |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | 1-year HSTS. Safe for local/LAN use. |
| `X-Frame-Options` | `DENY` | No framing — page not designed for embedding. |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing. |

---

## 4. Auth Session (Web UI)

### In-memory session store (no DB)

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `str` | UUID v4 generated on login |
| `created_at` | `datetime` | Timestamp of session creation |
| `last_accessed` | `datetime` | Updated on each authenticated request |
| `client_ip` | `str` | IP that created the session (for binding) |

**Lifecycle**:
- Created on POST to `/login` with valid API key
- Validated via session cookie (`session_id`) on web page requests
- Expires after 24 hours of inactivity (sliding window, reset on each request)
- Cleared on logout or expiry

---

## 5. Idempotency Key Tracking (API)

### In-memory TTL cache (no DB)

| Field | Type | Description |
|-------|------|-------------|
| `key` | `str` | Client-supplied `Idempotency-Key` header value |
| `endpoint` | `str` | Route path (e.g., `/v1/training/start`) |
| `result` | `dict` | Cached response to return on duplicate |
| `expires_at` | `datetime` | TTL (default: 1 hour) |

**Lifecycle**:
- Accepted on POST `/v1/training/start` (and similar mutating endpoints)
- First request with new key: process normally, cache result
- Duplicate request with same key within TTL: return cached result
- Key cleanup: purged from cache after TTL expires

---

## Entity Relationship Diagram (Logical)

```
┌──────────────────────┐
│   APIKeyConfig       │  (in-memory, process lifetime)
│  ──────────────────  │
│  key: str            │
│  generated_at: dt    │
│  source: env/auto    │
└──────────────────────┘
          │ validates
          ▼
┌───────────────────────────────────────┐
│   HTTP Request                        │
│  ───────────────────────────────────  │
│  Headers: X-API-Key or Cookie         │
│  Method: GET/POST/PUT/DELETE          │
│  Path: /v1/...                        │
│  Body: (typed or untyped)             │
└───────────────────────────────────────┘
          │ passes through
          ▼
┌──────────────────────┐
│   Auth Middleware     │  (app-level, every request)
│  ──────────────────  │
│  - Validate API key  │
│  - Validate session  │
│  - Check exempt list │
│  - Add security hdrs │
│  - Rate limit check  │
└──────────────────────┘
          │ if authenticated
          ▼
┌──────────────────────┐
│   Validation Layer    │  (route-level)
│  ──────────────────  │
│  - Typed Pydantic    │
│  - File size caps    │
│  - ReDoS timeout     │
│  - Idempotency check │
└──────────────────────┘
```

## State Transitions

### Authentication State
```
[No Key] ──first startup──▶ [Auto-Generated Key]
    │                            │
    │                            ├── display in logs
    │                            ├── store in memory
    │                            └── accept via X-API-Key header
    │
    └── ANVIL_API_KEY env var set ──▶ [User-Provided Key]
                                        (skips auto-generation)
```

### Web Session State
```
[Not Logged In] ──POST /login──▶ [Session Active]
    │                                │
    │                                ├── cookie set
    │                                ├── 24h sliding expiry
    │                                └── access all routes
    │                                    │
    │                                    └── 24h idle ──▶ [Session Expired]
    │                                                        │
    └── POST /login──▶ [Session Active] (re-login)
    
    [Session Active] ──POST /logout──▶ [Session Cleared]
```

### Idempotency Key State
```
[No Key] ──mutating request──▶ [Process Normally]
                                  │
[New Key] ──first request───▶ [Process + Cache Result]
                                  │
[Same Key] ──retry──────────▶ [Return Cached Result]
                                  │
                                  └── TTL expires ──▶ [Key Purged]
```