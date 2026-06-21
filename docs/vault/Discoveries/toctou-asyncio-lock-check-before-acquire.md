---
created: '2026-06-21T00:00:00.000Z'
source: agent
tags:
  - type/discovery
  - domain/architecture
title: TOCTOU Race on asyncio.Lock Check-Before-Acquire
type: discovery
aliases:
  - TOCTOU Race on asyncio.Lock Check-Before-Acquire
  - asyncio.Lock check-before-acquire race
updated: '2026-06-21T00:00:00.000Z'
code-refs:
  - anvil/api/v1/health_ops.py
---
# TOCTOU Race on asyncio.Lock Check-Before-Acquire

## Problem

A TOCTOU (time-of-check-time-of-use) race exists in `anvil/api/v1/health_ops.py:60-67` where `_bootstrap_lock.locked()` is checked before `async with _bootstrap_lock:`. Two concurrent requests can both pass the initial check, and the lock only serializes the second request rather than returning HTTP 409.

## Pattern

```python
# WRONG — TOCTOU race:
if not _bootstrap_lock.locked():      # check (passes for both concurrent requests)
    async with _bootstrap_lock:        # acquire (second request blocks here)
        result = await workbench.demo.bootstrap_all()
        return result.model_dump()
raise HTTPException(status_code=409, ...)  # only reached if lock was already held

# CORRECT — just use the lock directly:
async with _bootstrap_lock:
    result = await workbench.demo.bootstrap_all()
    return result.model_dump()
```

## Why It Happens

The developer wanted to return HTTP 409 ("already in progress") when a bootstrap was already running. The `.locked()` check seemed natural but creates a window between check and acquire.

## Proper Fix Options

1. **Remove the check** — just use `async with` which serializes naturally. Drops the 409 feedback.
2. **Use a flag** — `_bootstrap_in_progress` boolean guarded by a separate lock or set atomically before/after.
3. **Use `asyncio.Lock.acquire()` with a timeout** — `await asyncio.wait_for(lock.acquire(), timeout=0)` to attempt a non-blocking acquire, catching `TimeoutError` to return 409.

## Related

- TMR-019 in thread model review
- Classical lock anti-pattern documented in Go `sync.Mutex` and Python `threading.Lock` best practices
