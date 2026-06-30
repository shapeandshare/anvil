# Quickstart: Degraded Mode Recovery

## Priority Order

1. **Refactor `TrackingService` internals** (backbone — all other work depends on this)
2. **Add `tracking` block to `/v1/health/detailed`**
3. **Add UI degraded indicators** (training, experiments, model registry, operations pages)
4. **Write tests** (unit + e2e)

## Step-by-Step

### Step 1: Create `tracking_status.py` (new file)

Path: `anvil/services/tracking/tracking_status.py`

Extract the DegradedReason enum, DegradedState data class, and TrackingStatus Pydantic model into a new file. This keeps `tracking.py` focused on orchestration.

### Step 2: Refactor `TrackingService` in `tracking.py`

- Replace `self._degraded: bool` with `self._state: DegradedState`
- Add `self._lock: asyncio.Lock`
- Rewrite `_lazy_init()` to catch only `(MlflowException, ConnectionError, TimeoutError, OSError)` and classify the failure
- Replace all `if self._degraded or not run_id: return` gates — split into separate checks:
  - `if self._state.status == "degraded": return ""` (degraded gate)
  - `if not run_id: raise ValueError("run_id must not be empty")` (validation gate)
- All other methods: narrow `except Exception: pass` to `except (MlflowException, ConnectionError, TimeoutError, OSError): pass`

### Step 3: Add retry logic in `_lazy_init()`

```python
async def _maybe_reconnect(self) -> bool:
    """Try to reconnect if degraded. Returns True if recovered."""
    if self._state.status == "active":
        return True
    if self._state.reason not in (DegradedReason.UNREACHABLE, None):
        return False  # permanent failure, don't retry

    async with self._lock:
        if self._state.status == "active":
            return True  # another coroutine already recovered us
        delay = min(1 * (2 ** self._state.retry_count), 30)
        jitter = delay * random.uniform(-0.25, 0.25)
        await asyncio.sleep(delay + jitter)
        try:
            client = self._client_factory(self._tracking_uri)
            # test connection...
            self._state = DegradedState.active()
            return True
        except (MlflowException, ConnectionError, TimeoutError, OSError):
            self._state.retry_count += 1
            self._state.last_attempt = time.time()
            return False
```

### Step 4: Update `health_ops.py`

Add tracking status resolution to the `health_detailed()` endpoint. The TrackingService is accessed via the workbench dependency. Add a `tracking` block to the response dict.

### Step 5: Add banner to `base.html`

Add a `{% block degraded_banner %}` block to `base.html` (alongside `didyouknow_banner`), with the `section-card--banner` warning pattern. Each page can override with JS toggling or leave the default that reads from health data.

### Step 6: Wire degraded banner JS per page

Each target page (training, experiments, models, operations) fetches `GET /v1/health/detailed` and toggles the banner visibility:
```javascript
fetch('/v1/health/detailed').then(function(r) {
  return r.json();
}).then(function(data) {
  var banner = document.getElementById('degraded-banner');
  if (data.tracking && data.tracking.status === 'degraded') {
    banner.querySelector('.degraded-banner__msg').textContent = data.tracking.message;
    banner.style.display = '';
  } else {
    banner.style.display = 'none';
  }
});
```

### Step 7: Write tests

**Unit tests** (`tests/unit/services/test_tracking_degraded.py`):
- Test state transitions (active → degraded → recovered)
- Test retry backoff (verify delay with mocked sleep)
- Test exception classification (each exception type produces correct DegradedReason)
- Test thread safety (concurrent calls with asyncio.gather)
- Test empty run_id raises ValueError
- Test unexpected exceptions propagate (TypeError not swallowed)

**E2E tests** (`tests/e2e/test_tracking_degraded.py`):
- Start app, verify health endpoint shows tracking: active
- Simulate MLflow outage, verify health endpoint shows tracking: degraded
- Restart MLflow, verify recovery