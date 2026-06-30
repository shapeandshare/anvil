# Data Model: Degraded Mode Recovery

## Entity: `DegradedState`

Replaces the boolean `_degraded` flag with a typed state machine.

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `status` | `Status` enum | Current tracking health: `active` or `degraded` |
| `reason` | `Reason \| None` | Why degraded, or `None` if active |
| `message` | `str` | Human-readable description of the failure |
| `last_attempt` | `float \| None` | Unix timestamp of last reconnection attempt |
| `retry_count` | `int` | Consecutive retry attempts (reset to 0 on recovery) |

**State Transitions**:

```
active ──(MlflowException/ConnectionError/TimeoutError/OSError)──▶ degraded
degraded ──(exponential backoff retry succeeds)──▶ active
degraded ──(permanent failure: version mismatch/auth)──▶ degraded (no retry)
degraded ──(consecutive failures, backoff)──▶ degraded (retry_count++, delay increases)
```

**Internal states** (not exposed to API/UI):
- `recovering` — during the brief window between retry attempt and success confirmation. UI still shows `degraded`.

## Entity: `DegradedReason` (StrEnum)

```python
class DegradedReason(StrEnum):
    UNREACHABLE = "unreachable"           # ConnectionError, TimeoutError, OSError on connect → retry
    INCOMPATIBLE_VERSION = "incompatible_version"  # MlflowException with version mismatch → no retry
    AUTH_FAILURE = "auth_failure"         # MlflowException with 401/403 → no retry
    PERMANENT_ERROR = "permanent_error"   # Other non-retryable MlflowException → no retry
    UNKNOWN = "unknown"                   # Unexpected exception during retry → no retry
```

**Retry Policy**:
- `UNREACHABLE` — retry with exponential backoff + jitter
- All others — no retry (permanent degraded)

## Entity: `TrackingStatus` (Pydantic BaseModel)

Response block embedded in `GET /v1/health/detailed`:

```python
class TrackingStatus(BaseModel):
    status: Literal["active", "degraded"]
    reason: DegradedReason | None = None
    message: str = ""
    last_attempt: float | None = None
```

**Serialized example (active)**:
```json
{
  "tracking": {
    "status": "active",
    "reason": null,
    "message": "",
    "last_attempt": null
  }
}
```

**Serialized example (degraded — unreachable)**:
```json
{
  "tracking": {
    "status": "degraded",
    "reason": "unreachable",
    "message": "MLflow server at http://127.0.0.1:5001 is unreachable (Connection refused). Automatic retry in progress.",
    "last_attempt": 1719690000.0
  }
}
```

**Serialized example (degraded — permanent)**:
```json
{
  "tracking": {
    "status": "degraded",
    "reason": "auth_failure",
    "message": "MLflow server rejected credentials (HTTP 403). Manual intervention required.",
    "last_attempt": 1719690000.0
  }
}
```

## Validation Rules

- State transitions are guarded by `asyncio.Lock` — only one thread can mutate state at a time
- `reason` MUST be `None` when `status == "active"`
- `reason` MUST be non-`None` when `status == "degraded"`
- `retry_count` resets to 0 on successful reconnection
- `last_attempt` updates on every retry attempt, regardless of success/failure