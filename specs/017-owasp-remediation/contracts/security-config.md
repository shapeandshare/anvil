# Security Configuration Contract

**Phase**: 1 (Design & Contracts) | **Date**: 2026-06-21 | **Plan**: `plan.md`

## 1. Rate Limiting

### Configuration

```python
RATE_LIMIT_CONFIG = {
    "enabled": True,                    # Master toggle
    "requests_per_minute": 100,         # Per client IP (general)
    "burst_size": 20,                   # Burst allowance before throttling
    "exempt_routes": {"/v1/health", "/static"},   # NOTE: /login is NOT exempt (see below)
    "login_requests_per_minute": 5,     # STRICT separate limit for POST /login (FR-028)
    "login_failure_delay_seconds": 1,   # Fixed delay after each failed login attempt
}
```

> ⚠️ **Review fix H-2 / FR-028**: `POST /login` MUST NOT be rate-limit-exempt. It carries its own
> stricter limit (5/min/IP) plus a fixed failure delay, because it is the brute-force surface for the
> API key. `GET /login` (the page) may be served freely; only the credential-submitting `POST` is
> strictly limited.

**Override**: `ANVIL_RATE_LIMIT` env var (JSON string matching config shape) or `ANVIL_RATE_LIMIT_DISABLE=true` to disable.

### Implementation

Custom in-process sliding window counter keyed by `(client_ip, route_prefix)`. Not using external rate limiter (`slowapi`) to avoid a new dependency.

> **Limitation (review L-4)**: this counter is per-process. Under multi-worker uvicorn or replicated
> containers it does not share state across workers; an attacker could spread requests across workers.
> Acceptable for the single-process local-first deployment; documented as an accepted limitation. A
> shared store (e.g. Redis) is the SaaS-mode upgrade path.

### Middleware Order (FR-029)

Registration/execution order MUST be: **rate-limit → CORS → security-headers → auth**. The auth
middleware MUST allow `OPTIONS` (CORS preflight) through without authentication, or browsers get
opaque failures on cross-origin calls.

### Behavior

| Scenario | Response |
|----------|----------|
| Under limit | Normal response |
| At limit (burst consumed) | `429 Too Many Requests` with `Retry-After` header |
| `POST /login` over 5/min | `429` + `Retry-After`; failed attempts also incur a fixed delay |
| Exempt route (`/v1/health`, `/static`) | No general rate limit applied |
| `OPTIONS` preflight | Passes auth; still subject to rate limiting |

---

## 2. Security Headers

### Default Header Set

```python
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "script-src 'self';"
    ),
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
}
```

### Rationale

| Header | Choice | Why Not Stricter |
|--------|--------|------------------|
| CSP `style-src 'unsafe-inline'` | Required for existing design system (CSS custom properties in `<style>` tags, inline component styles) | Refactoring to non-inline styles is out of scope |
| CSP `img-src 'self' data:` | Required for SVG data-URIs used in themes and icons | Can be tightened post-refactor |
| CSP `font-src 'self'` | Self-hosted fonts only | No external font CDN |
| CSP `script-src 'self'` | No external scripts, no inline event handlers | `'unsafe-inline'` not needed — JS is in separate `.js` files |
| HSTS `includeSubDomains` | Covers any subdomain that might be configured | Safe for single-domain deployments |
| HSTS `max-age=31536000` | 1 year — standard recommendation | No reason to use shorter duration |
| X-Frame-Options `DENY` | App is not designed for embedding | Strongest option |
| X-Content-Type-Options `nosniff` | Prevents MIME confusion | Standard for all modern apps |

---

## 3. CORS Configuration

### Default (Local-Only Mode)

```python
CORS_CONFIG = {
    "enabled": False,          # No CORS needed for same-origin
}
```

### LAN-Accessible Mode (when bound to `0.0.0.0`)

```python
CORS_CONFIG = {
    "enabled": True,
    "allow_origins": [],       # Must be explicitly configured
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "X-API-Key", "Idempotency-Key"],
    "allow_credentials": True,
}
```

**Configuration source**: `ANVIL_CORS_ORIGINS` env var (comma-separated origin list). If set, CORS is enabled with those origins. If not set, CORS is disabled (same-origin only).

---

## 4. ReDoS Protection Policy

### Configuration

```python
REGEX_TIMEOUT_SECONDS = 2  # wall-clock execution timeout (NOT a re.compile arg)
```

> **IMPORTANT**: Python's stdlib `re` module has **no `timeout=` parameter**. That parameter exists only in the third-party `regex` package. Passing `timeout=` to `re.compile` raises `TypeError`. To honor the zero-new-dependency constraint, the timeout MUST wrap regex *execution* using a stdlib mechanism.

### Mechanism (stdlib, zero-dependency)

Run the regex operation (`pattern.sub` / `pattern.search`) in a worker thread and `join` with the timeout:

```python
import re, threading

def run_with_timeout(fn, timeout: float):
    result: list = []
    error: list = []
    def _target():
        try:
            result.append(fn())
        except Exception as exc:  # noqa: BLE001 - re-raised on main thread
            error.append(exc)
    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError("regex execution exceeded time budget")
    if error:
        raise error[0]
    return result[0]
```

> **Caveat**: a daemon thread cannot be force-killed in CPython, so a truly catastrophic pattern keeps a thread spinning until it completes; the *request* returns promptly (fail-safe for the client) but the worker still consumes CPU. On Unix, `signal.SIGALRM` (main-thread only) can interrupt actual execution and is the preferred mechanism when the call runs on the main thread. The implementation SHOULD prefer `SIGALRM` where available and fall back to the thread approach elsewhere. This tradeoff MUST be recorded in the ADR.

### Rules

| Pattern Source | Protection |
|---------------|------------|
| User-supplied regex in `curate_replace` (`anvil/services/datasets/dataset_curation.py`) | Compile normally; execute under `run_with_timeout(..., REGEX_TIMEOUT_SECONDS)` |
| Gitignore patterns in `CorpusLoader` | Already pre-compiled internal patterns — no user input at this stage |
| Any new user-supplied regex endpoint | MUST apply the execution timeout |

### Behavior on Timeout

Return `422` with `{"detail": "Pattern too complex or invalid"}`. Log the pattern hash (not the pattern itself) server-side for debugging.

---

## 5. File Upload Limits

### Configuration

```python
UPLOAD_LIMITS = {
    "dataset_upload_mb": 100,        # POST /datasets/upload
    "content_stage_mb": 50,          # POST /content/sessions/{id}/stage
    "max_request_body_mb": 10,       # General JSON body size (non-upload)
}
```

### Implementation

- File upload endpoints: Check `file.size` or stream up to limit then reject
- FastAPI: `max_request_body_mb` via custom middleware or `LimitRequestBodySize` pattern

---

## 6. Idempotency Configuration

```python
IDEMPOTENCY_TTL_HOURS = 1
```

**Scope**: `POST /v1/training/start` and any other mutating POST endpoints that could create duplicate resources.

---

## 7. Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANVIL_API_KEY` | *(auto-generated)* | Override the auto-generated API key. Read once at startup, then popped from `os.environ` (FR-026). Never written to logs. |
| `ANVIL_MLFLOW_INTERNAL_URI` | `http://127.0.0.1:5001` | Upstream MLflow target for the authenticated reverse proxy (ADR-034). Loopback locally; Cloud Map DNS in SaaS. |
| `ANVIL_RATE_LIMIT` | *(none — uses defaults)* | JSON config for rate limiting |
| `ANVIL_RATE_LIMIT_DISABLE` | `false` | Disable rate limiting entirely |
| `ANVIL_CORS_ORIGINS` | *(none — CORS disabled)* | Comma-separated origins for CORS allowlist |
| `ANVIL_LOG_LEVEL` | `INFO` | Logging level (set in app lifespan, FR-017) |

### API-Key Handling Rules (FR-026 / review C-4)

- Generated with `secrets.token_urlsafe(32)`; validated with `secrets.compare_digest` (constant-time).
- Persisted to a `0600` state file or the app DB — survives restarts, retrievable via `--show-api-key`.
- **Never written to log files or printed in full to the console.** First-run console output shows only a prefix hint.
- When supplied via `ANVIL_API_KEY`, read once then `os.environ.pop` to limit `/proc/<pid>/environ` exposure.