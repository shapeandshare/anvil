# Context — 069 Replace Module-Level Service Singletons with DI

> Cross-references: `../066-codebase-remediation/data-inventory.md` §4, `shared-decisions.md` Decision 2.

## Current State (verified line refs)

Module-level singletons in `anvil/api/v1/`:
```python
# training.py:126-127
svc = TrainingService()
tracking_svc = TrackingService()

# corpora.py:54
tracking_svc = TrackingService()

# eval_datasets.py:21
_tracking_svc = TrackingService()

# inference.py:33
_svc = InferenceService()
```
Plus `experiments.py` creates `TrackingService()` inline in 5 handlers (lines 99, 355, 518, 604, 769).

Re-verify: `grep -rn "TrackingService()\|InferenceService()\|TrainingService()" anvil/api/v1/`

## Reference Implementation

`anvil/api/deps.py` — existing DI pattern:
```python
async def get_workbench() -> AsyncGenerator[AnvilWorkbench]:
    async for session in get_db():
        yield AnvilWorkbench(session)
```
`AnvilWorkbench` already exposes `.training`, `.tracking`, `.inference` as lazy properties (`workbench.py:200-219`).

## Decision Reference

Per `shared-decisions.md` Decision 2: **Option A — workbench-centric**. Route-level `Depends()` functions delegate to `AnvilWorkbench`. Do NOT create parallel independent providers (violates Principle 13).

## Approach

Add thin dependency functions to `deps.py`:
```python
async def get_training_service(
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> TrainingService:
    return wb.training
```
Then routes use `svc: Annotated[TrainingService, Depends(get_training_service)]`.

**Note**: `TrainingService`, `TrackingService`, `InferenceService` are currently stateless (workbench creates them without a session). Confirm they don't need per-request session binding. If stateless, a single instance per workbench is fine.

## Test Migration

Tests currently monkeypatch module singletons — e.g. `tests/unit/api/test_training_validation.py:95`:
```python
monkeypatch.setattr(training_module, "svc", MockTrainingService())
```
These MUST migrate to:
```python
app.dependency_overrides[get_training_service] = lambda: MockTrainingService()
```
Find all such tests: `grep -rn "monkeypatch.setattr.*svc\|monkeypatch.setattr.*_svc\|monkeypatch.setattr.*tracking" tests/`

## Gotchas

- `inference.py` has `_call_or_400(svc_method, *args)` helper (line 36) that wraps `_svc` methods. It must receive the injected service, not read the module global.
- SSE endpoints that reference `svc` for queue management (`svc.get_queue`, `svc.release_queue`) — these also need the injected service. But SSE handlers may run outside the normal DI lifecycle; verify the queue state (spec 074 moves `_tasks` to app.state — coordinate).
- `experiments.py` inline `TrackingService()` calls are also touched by spec 070 (business logic extraction) — coordinate.
