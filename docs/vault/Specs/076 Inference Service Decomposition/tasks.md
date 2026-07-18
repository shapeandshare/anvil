# Tasks — 076 Split InferenceService

**TDD order. Highest-effort spec — do AFTER spec 071 (DI). Facade preserves public API.**

## Phase 0 — Characterize
- [ ] T001 `wc -l anvil/services/inference/inference.py` (confirm ~2028).
- [ ] T002 List public methods: `grep -n "    async def \|    def " anvil/services/inference/inference.py | grep -v "^.*def _"`.
- [ ] T003 Map consumers: `grep -rn "InferenceService" anvil/ tests/`.
- [ ] T004 **[Characterization]** Golden-output tests for key public methods (tokenize, generate, load_model) — must pass before AND after.

## Phase 1 — ModelLoadingService (Red-Green-Refactor)
- [ ] T010 **[Red]** Unit test for `ModelLoadingService.load(...)` independent of tokenization/sampling.
- [ ] T011 **[Green]** Extract model loading + HF key mapping + warmup + optional-dep flags into `model_loading_service.py`. Inject `TrackingService` (spec 071).
- [ ] T012 **[Refactor]** Facade `InferenceService.load_model` delegates.

## Phase 2 — TokenizationService
- [ ] T020 **[Red]** Unit test for tokenize/embeddings/attention without model-loading side effects.
- [ ] T021 **[Green]** Extract into `tokenization_service.py`; facade delegates.

## Phase 3 — SamplingService
- [ ] T030 **[Red]** Unit test for generate/sampling.
- [ ] T031 **[Green]** Extract into `sampling_service.py`; facade delegates.

## Phase 4 — LossService
- [ ] T040 **[Red]** Unit test for loss/logits.
- [ ] T041 **[Green]** Extract into `loss_service.py`; facade delegates.

## Phase 5 — Facade & wiring
- [ ] T050 `InferenceService` becomes a thin facade injecting the 4 sub-services (spec 071 pattern). Update `AnvilWorkbench.inference`.
- [ ] T051 Characterization tests (T004) pass unchanged.

## Phase 6 — Gates
- [ ] T060 Facade <300 lines; each sub-service <400 lines.
- [ ] T061 Each sub-service has its own test file.
- [ ] T062 `make lint && make typecheck && make test`.

## Verification (Success Criteria)
- SC-001: facade <300 lines.
- SC-002: each sub-service <400 lines.
- SC-003: dedicated test file per sub-service.
- SC-004: existing tests pass unmodified.
- SC-005: gates green.
