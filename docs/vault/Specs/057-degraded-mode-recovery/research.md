# Research: Degraded Mode Recovery

## Phase 0 — Research Findings

### 1. MLflow Exception Hierarchy

**Decision**: Catch `MlflowException`, `ConnectionError`, `TimeoutError` for degraded-mode entry. Let all other exceptions propagate.

**Rationale**:

`MlflowException` is the base class for all MLflow-specific errors (API errors, REST errors, invalid state). Its MRO is: `MlflowException` → `Exception` → `BaseException`. Subclasses include `RestException` (HTTP-level errors from the MLflow REST API), `ExecutionException`, `InvalidUrlException`, and error code classes like `BAD_REQUEST`, `ENDPOINT_NOT_FOUND`, `INTERNAL_ERROR`, `RESOURCE_EXHAUSTED`, `TEMPORARILY_UNAVAILABLE`.

Transport-level failures (connection refused, DNS failure, timeout) raise stdlib exceptions:
- `ConnectionError` — TCP connection failures
- `TimeoutError` — request timeout
- `OSError` — socket-level failures (wrapped by urllib/requests)

These three categories cover the known failure modes for an unreachable or temporarily broken MLflow server. Unexpected exceptions (`TypeError`, `AttributeError`, `ValueError`, `ZeroDivisionError`) indicate genuine programming bugs and MUST propagate.

**Alternatives considered**:
- Catching `Exception` broadly (current approach) — hides real bugs
- Catching only `MlflowException` — misses transport-level failures (ConnectionError, TimeoutError come from urllib/httpx, not MLflow)

### 2. Exception Narrowing Pattern per Method

**Decision**: Split into two tiers:
- **`start_run()`** — catches `(MlflowException, ConnectionError, TimeoutError, OSError)`, enters degraded mode with reason classification
- **All other methods** (`log_metric`, `log_artifacts`, `set_tag`, etc.) — catches only `(MlflowException, ConnectionError, TimeoutError, OSError)`, silently skips (already degraded or transient). Unexpected exceptions propagate.

**Rationale**: Only `start_run()` enters degraded mode. All other methods should simply no-op if a transient error occurs while already degraded. But neither should swallow `TypeError` or `AttributeError`.

### 3. Exponential Backoff with Jitter

**Decision**: Exponential backoff with jitter, configurable defaults:
- Initial delay: 1s
- Multiplier: 2×
- Max delay: 30s
- Jitter: random ±25% of the current delay

**Rationale**: Standard industry pattern for retrying network services. Fast recovery after brief blips (1-2s), self-limiting during extended outages (30s cap). Jitter prevents thundering herd when multiple operations retry simultaneously after MLflow comes back.

**Alternatives considered**:
- Fixed interval (30s) — slow recovery
- Immediate retry on every call — hammers MLflow during extended outage
- No retry (current behavior) — permanent data loss

### 4. `asyncio.Lock` for Thread Safety

**Decision**: Use `asyncio.Lock` (not `threading.Lock`) to synchronize state mutations.

**Rationale**: `TrackingService` methods are called from `asyncio` event loop context via `run_in_executor`. The `asyncio.Lock` is already used in 3 places in the codebase (`backup_lock.py`, `local_versioned_content_store.py`, `health_ops.py`). Since all callers are in the same event loop, `asyncio.Lock` is the correct choice — `threading.Lock` would be needed only for true thread-level contention.

### 5. Failure Mode Classification

**Decision**: Use a `StrEnum` for `DegradedReason` with the following values:

| Reason | Trigger | Retry? |
|--------|---------|--------|
| `unreachable` | ConnectionError, TimeoutError, OSError on connect | Yes |
| `incompatible_version` | MlflowException with version mismatch error code | No |
| `auth_failure` | MlflowException with 401/403 error code | No |
| `permanent_error` | Non-retryable MlflowException | No |
| `unknown` | Unexpected exception type during retry attempt | No |

**Rationale**: Transient vs permanent distinction is critical for FR-002. Connection failures should retry; version/auth failures should not.

### 6. UI Banner Patterns

**Decision**: Reuse `section-card--banner` warning pattern from `config.html` (lines 35-48). Add a shared `{% block degraded_banner %}` to `base.html` rather than copy-pasting across 4 pages.

**Rationale**: The existing `section-card--banner` with `--accent-warn` color and `&#9888;` icon is the closest existing pattern to what we need. It supports `display:none/block` toggling and appears at the top of page content — appropriate for a persistent status indicator.

**Existing patterns**:
- `section-card--banner` in `archetypes.css` — page-level info/warning banners
- Toast system (`toast toast-error/info/success`) — ephemeral, auto-dismisses (not suitable for persistent)
- `.et-degraded` CSS class — only affects the experiment-tracking widget (not page-level)
- `didyouknow` banner — dismissible contextual info, purple accent (wrong color)

### 7. MLflow Exception MRO (Verified)

```
MlflowException
  → Exception
    → BaseException
      → object
```

Subclass `RestException` adds HTTP status code handling. The `mlflow.exceptions` module exports error codes (`BAD_REQUEST`, `ENDPOINT_NOT_FOUND`, `INTERNAL_ERROR`, `RESOURCE_EXHAUSTED`, `TEMPORARILY_UNAVAILABLE`, `UNAUTHENTICATED`, etc.) that can be used to distinguish permanent vs transient failures.