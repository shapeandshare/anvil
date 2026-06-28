---
title: Global Engine Singleton Causes Cross-Test Contamination
type: discovery
tags:
  - type/discovery
  - domain/testing
  - domain/database
status: draft
created: '2026-06-27'
updated: '2026-06-27'
---

# Global Engine Singleton Causes Cross-Test Contamination

The FastAPI ``app`` module is a process-level singleton.  Its lifespan
runs once at module import.  Other test modules may set
``app.state.boot_snapshot``, ``app.state.workspace_paths``, or call
``reinit_engine()`` which redirects the global ``async_engine``.
Subsequent tests that rely on a clean ``app.state`` or the default
engine path see stale values.

## Mitigation

- The config endpoint test file (`tests/e2e/test_config_endpoints.py`)
  clears ``app.state.boot_snapshot`` at module import time so
  pending-restart fallback logic is used.
- Tests that call ``reinit_engine()`` should restore the engine when
  done, or the fixture should create a fresh engine per test.

## References

- Feature 028 Concurrent Isolated Instances
- ``anvil/db/session.py`` — ``async_engine`` module-level variable
- ``anvil/api/app.py`` — lifespan sets ``app.state.boot_snapshot``