---
aliases:
  - 'Session: Demo Bootstrap Verification'
  - demo-bootstrap-verification
created: '2026-06-20'
source: agent
status: draft
tags:
  - type/session-log
  - domain/architecture
  - domain/ui
  - domain/operations
title: 'Session: Demo Bootstrap Verification'
type: session-log
updated: '2026-06-20'
---
# Session: Demo Bootstrap Verification

**Date**: 2026-06-20
**Trigger**: User requested verification that demo data only bootstraps on first startup or via ops page button.

## What was done

### Verification pass: End-to-end trace of demo bootstrap guard chain

Traced the full demo bootstrap chain to confirm first-run guard and manual re-trigger are correctly implemented:

1. **FastAPI lifespan** (`anvil/api/app.py:91-122`) — Verified `count_by_origin("bundled")` guard. On startup, checks DB for existing bundled entities; if found (corpus_count > 0 or dataset_count > 0), skips bootstrap entirely without instantiating `DemoBootstrapService`.

2. **Ops page button** — Verified the HTML button at `anvil/api/templates/operations.html:35`:
   ```html
   <button class="btn btn-secondary" onclick="ops.rebootstrapDemo()" id="btn-rebootstrap-demo">↻ Re-bootstrap Demo</button>
   ```

3. **JavaScript handler** (`operations.html:140-156`) — Verified `rebootstrapDemo()` POSTs to `/v1/demo/bootstrap` and shows toast with created/skipped counts.

4. **Endpoint** (`anvil/api/v1/health_ops.py:34-62`) — Verified `POST /v1/demo/bootstrap` with `asyncio.Lock` concurrency protection (returns HTTP 409 if already in progress).

5. **Router wiring** (`anvil/api/v1/router.py:40`) — Verified `health_ops_router` is included in v1 router.

6. **Service** (`anvil/services/demo/demo_bootstrap.py:121`) — Verified `bootstrap_all()` is idempotent (checks `get_by_name()` for each item before creating).

### Test results

- Bootstrap tests: 13/14 pass (1 pre-existing isolation issue when run as suite — test passes in isolation)
- CI tests: 2 pre-existing collection errors (unrelated import path issues in `scripts/ci/`)
- Coverage: 23.22% (meets 23% threshold)

### AGENTS.md check

Already up to date:
- Line 3: `Last updated: 2026-06-19`
- Line 311: `014-demo-data-bootstrap` entry documents the first-run guard, ops endpoint, and CLI banner conditional
- No update needed

## Key findings

| Component | File | Status |
|-----------|------|--------|
| Lifespan guard (count_by_origin) | `anvil/api/app.py:91-122` | ✓ Correct |
| Ops page button | `anvil/api/templates/operations.html:35` | ✓ Present |
| JS handler | `anvil/api/templates/operations.html:140-156` | ✓ Correct |
| POST endpoint | `anvil/api/v1/health_ops.py:34-62` | ✓ Correct, with lock |
| Router wire | `anvil/api/v1/router.py:40` | ✓ Connected |
| Bootstrap service | `anvil/services/demo/demo_bootstrap.py:121` | ✓ Idempotent |

No changes needed — all guard and re-trigger mechanisms are correctly implemented and verified.
