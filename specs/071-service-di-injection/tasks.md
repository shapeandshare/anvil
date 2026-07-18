# Tasks — 071 Inject Cross-Service Dependencies

**TDD order. This blocks spec 068 — do this first.**

## Phase 0 — Investigate
- [ ] T001 Re-verify the full offender list (context.md grep). Note `demo_model_provider.py` and `demo_bootstrap.py` — decide per-case whether they're in scope.
- [ ] T002 Check `EvaluationService.__init__` (accepts inference/tracking) vs lines 517-518 (creates them) — determine if 517-518 is a fallback path or dead code.

## Phase 1 — TrainingService deps (Red-Green)
- [ ] T010 **[Red]** `test_training_service_uses_injected_dataset_service` — pass a mock DatasetService, assert it's used.
- [ ] T011 **[Green]** Add `dataset_service`/`corpus_service`/`demo_bootstrap` optional params to `TrainingService.__init__`; use them in `_load_docs` (lines 333/343/344). Default `None` → lazy create.
- [ ] T012 **[Green]** Update `AnvilWorkbench.training` property to pass explicit instances.

## Phase 2 — InferenceService deps
- [ ] T020 **[Red]** `test_inference_service_uses_injected_tracking`.
- [ ] T021 **[Green]** Add `tracking: TrackingService | None` to `InferenceService.__init__`; replace the 3 inline `TrackingService()` (lines 414/734/1251) with `self._tracking`.
- [ ] T022 **[Green]** Update `AnvilWorkbench.inference` to pass tracking.

## Phase 3 — TrainingRunService & EvaluationService
- [ ] T030 **[Green]** Add `inference: InferenceService | None` to `TrainingRunService.__init__`; replace line 397. Wire in workbench.
- [ ] T031 **[Green]** Fix `EvaluationService` lines 517-518 to use injected `self._inference`/`self._tracking`.

## Phase 4 — Demo bootstrap/provider (evaluate)
- [ ] T040 Decide scope for `demo_model_provider.py` (module functions) and `demo_bootstrap.py` (owns its services). Refactor or document exception.

## Phase 5 — Gates
- [ ] T050 `grep -rn "TrackingService()\|InferenceService()" anvil/services/` — only lazy-default fallbacks remain (or zero).
- [ ] T051 `make lint && make typecheck && make test`.

## Verification (Success Criteria)
- SC-001: zero services creating other services in method bodies (only `None`-default constructor fallbacks).
- SC-002: all service constructors declare their service deps.
- SC-003: workbench is the single wiring point.
- SC-004: mypy --strict clean, no circular imports.
