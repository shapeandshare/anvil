# Contract: SSE Connection Lifecycle

## Purpose
Manage a single EventSource connection for live training metrics, exposing a 6-state state machine with automatic reconnection.

## Interface

```javascript
// SSESession manages one EventSource connection through its lifecycle
class SSESession {
  constructor(runId: number);
  
  // State: 'idle' | 'connecting' | 'streaming' | 'done' | 'errored' | 'reconnecting'
  get state(): string;
  
  // Start the connection (idle → connecting)
  start(): void;
  
  // Manually stop the connection (streaming → done)
  stop(): void;
  
  // Manually retry after errored (errored → connecting)
  retry(): void;
  
  // Cleanup — close EventSource, remove listeners
  destroy(): void;
  
  // Events
  onstatechange: (state: string) => void;
  onmetrics: (data: MetricsEvent) => void;
  oncomplete: (data: CompleteEvent) => void;
  onerror: (data: ErrorEvent) => void;
}
```

## Event Types (from backend)

```typescript
interface MetricsEvent {
  step: number;
  loss: number;
}

interface CompleteEvent {
  final_loss: number;
  samples_seen?: number;
  duration?: number;
}

interface ErrorEvent {
  message: string;
}
```

## Reconnect Strategy

```
backoff[5] = [1000, 2000, 4000, 8000, 16000]  // milliseconds
maxRetries = 5
```

On EventSource error:
1. Increment retryCount
2. If retryCount <= maxRetries:
   - State: 'reconnecting'
   - setTimeout(() => new EventSource(url), backoff[retryCount - 1])
3. If retryCount > maxRetries:
   - State: 'errored'
   - Close old EventSource
   - Dispatch onerror with { message: 'Connection lost after 5 retries' }

## Cleanup

- `destroy()` calls `eventSource.close()` and removes all event listeners
- Must be called on page navigation away from the live training page
- Prevents orphan connections and duplicate event handlers

## Acceptance

- [ ] All 6 states render with distinct token-driven treatment
- [ ] Reconnect backoff follows 1s/2s/4s/8s/16s timing with visual 'reconnecting' state
- [ ] After 5 failed retries, transitions to 'errored' with manual 'Retry' button
- [ ] Manual stop transitions from 'streaming' to 'done'
- [ ] `destroy()` called on navigation — verified via DevTools Network tab