# Tasks — 069 Replace Module-Level Service Singletons with DI

**TDD order. Depends on Decision 2 (workbench-centric DI).**

## Phase 0 — Prerequisites
- [ ] T001 Confirm `shared-decisions.md` Decision 2 (workbench-centric).
- [ ] T002 Verify `TrainingService`/`TrackingService`/`InferenceService` are stateless (workbench creates without session). Re-verify singleton locations (context.md commands).
- [ ] T003 Inventory tests that monkeypatch singletons: `grep -rn "monkeypatch.setattr.*\(svc\|_svc\|tracking\)" tests/`.

## Phase 1 — Add dependency providers (Red-Green)
- [ ] T010 **[Red]** Write `tests/unit/api/test_service_deps.py::test_get_training_service_returns_workbench_training` — asserts `get_training_service` delegates to workbench. Confirm FAILS.
- [ ] T011 **[Green]** Add `get_training_service`, `get_tracking_service`, `get_inference_service` to `anvil/api/deps.py`, each delegating to `AnvilWorkbench`. Make tests pass.

## Phase 2 — Migrate routes (per file, Red-Green)
- [ ] T020 training.py — remove `svc`/`tracking_svc` module globals (lines 126-127); inject via `Depends`. Update `_call_or_400`-style helpers.
- [ ] T021 inference.py — remove `_svc` (line 33); inject; update `_call_or_400` (line 36) to take the service as a param.
- [ ] T022 corpora.py — remove `tracking_svc` (line 54); inject.
- [ ] T023 eval_datasets.py — remove `_tracking_svc` (line 21); inject.
- [ ] T024 experiments.py — replace 5 inline `TrackingService()` with injected dep (coordinate with spec 070).

## Phase 3 — Migrate tests
- [ ] T030 Convert `test_training_validation.py:95` and all other monkeypatch-of-singleton tests to `app.dependency_overrides[get_*_service] = ...`.
- [ ] T031 Ensure `app.dependency_overrides` is cleaned up per-test (fixture teardown).

## Phase 4 — Gates
- [ ] T040 `grep -rn "^\(svc\|_svc\|tracking_svc\|_tracking_svc\)\s*=" anvil/api/v1/` returns nothing.
- [ ] T041 `make lint && make typecheck && make test`.

## Verification (Success Criteria)
- SC-001: zero module-level service instantiations in `anvil/api/v1/`.
- SC-002: all route tests use `app.dependency_overrides`, not monkeypatch of singletons.
- SC-003: `make test` passes with no service-layer test changes.
- SC-004: mypy --strict clean.
