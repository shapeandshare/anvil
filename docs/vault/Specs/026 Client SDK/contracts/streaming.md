# Contract: SSE Streaming Client

**Feature**: 026-client-sdk | Typed event streaming for training (and P3 content) streams.

---

## Stream command shape

```python
class TrainingStreamCommand(AbstractCommand):
    """Subscribe to a training run's Server-Sent Events stream."""

    async def execute(self, run_id: str) -> AsyncIterator[StreamEvent]:
        async for event in self._transport.stream_sse(f"/v1/training/stream/{run_id}"):
            yield event
```

Exposed on the domain client as an async generator:

```python
async for event in client.training.stream(run_id):
    if event.type is StreamEventType.METRICS:
        step = event.data["step"]; loss = event.data["loss"]
    elif event.type is StreamEventType.COMPLETE:
        break
    elif event.type is StreamEventType.ERROR:
        raise ServerError(message=event.data.get("message", "training failed"))
```

---

## Wire format (verified against `anvil/api/v1/training.py`)

The server emits frames of the form:

```
event: <type>\n
data: <json>\n
\n
```

Observed event names: `metrics`, `complete`, `error`, `divergence`, `heartbeat`, `export_error`
(emitted via `event: error`, `event: heartbeat`, and dynamic `event: {msg['event']}`).

### Parser contract (`Transport.stream_sse`)
1. Open with `httpx` `client.stream("GET", url)`; assert `200`, else map status → exception.
2. Iterate `response.aiter_lines()`:
   - line starts `event: ` → capture current event type.
   - line starts `data: ` → parse JSON payload, emit `StreamEvent(type=<type>, data=<payload>)`.
   - blank line → frame boundary (reset current event).
3. Unknown event names → still yielded with `type` coerced via `StreamEventType(value)`;
   if the value is not a known member, raise nothing — instead surface as a generic event
   ONLY if it parses; otherwise skip malformed frames defensively.
4. Generator completes when the server closes the stream OR after a terminal event
   (`complete` / `error`) is consumed and the caller stops iterating.

### `StreamEvent` / `StreamEventType`
Defined in `data-model.md`. `StreamEventType` is a `StrEnum`; `StreamEvent.data` is
`dict[str, Any]` (the per-event payload shape varies by type and is documented inline).

---

## Behavioral guarantees & non-goals (v1)
- **No data loss** for well-formed frames during a run (SC-005): every `event:`/`data:` pair the
  server sends is yielded in order.
- **Heartbeats surfaced**: `HEARTBEAT` events are yielded (not swallowed) so callers can detect liveness.
- **No auto-reconnect** in v1 (spec edge case allows either; explicit is simpler). A dropped
  connection raises `ConnectionError` from the generator; the caller may re-subscribe.
- **Backpressure**: the async generator is pull-based; the caller controls consumption rate.
- **Timeout**: stream open respects `config.timeout`; the open phase is bounded, the stream phase
  is long-lived (no idle timeout beyond the server's heartbeats).

## Acceptance mapping
- US-3 scenario 2 → typed `metrics`/`complete`/`error` events via `client.training.stream`.
- US-3 scenario 5 → metrics events expose `step` and `loss`.
- FR-006 → SSE client yields typed event objects.
- SC-005 → all six event types delivered with no loss over a 1000-step run.
