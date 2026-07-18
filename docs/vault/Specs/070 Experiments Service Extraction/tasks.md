# Tasks — 070 Extract Business Logic from experiments.py

**TDD order — legacy code: write CHARACTERIZATION tests first (capture current behavior).**

## Phase 0 — Characterize
- [ ] T001 **[Characterization]** Write `tests/e2e/test_experiments_parity.py` capturing exact JSON for `GET /v1/experiments` and `GET /v1/experiments/{id}` for a seeded experiment. This MUST pass before AND after refactor.
- [ ] T002 Re-verify helper line refs in context.md against current file.

## Phase 1 — Extract enrichment (Red-Green-Refactor)
- [ ] T010 **[Red]** Write `test_list_experiments_enriched` on the service — asserts name resolution + artifact flags.
- [ ] T011 **[Green]** Move `_enrich_experiments`, `_resolve_experiment_name`, `_resolve_name_from_ds`, `_resolve_name_from_corpus`, `_set_artifact_flag` into `TrackingService.list_experiments_enriched()`. Make it pass.
- [ ] T012 **[Green]** Update `list_experiments` route to call the service method.

## Phase 2 — Extract experiment detail
- [ ] T020 **[Red]** Write `test_get_experiment_detail` — asserts architecture extraction (`num_params`), hyperparams coercion, memory estimate.
- [ ] T021 **[Green]** Create `ExperimentDetail` model + `TrackingService.get_experiment_detail(id)`. Move `_hyperparams_from_mlflow`, `LlamaModel` instantiation, `MlflowClient` usage, memory estimation into it.
- [ ] T022 **[Green]** Update `get_experiment` route to call the service; keep `_build_mlflow_url` in the route.
- [ ] T023 **[Refactor]** Remove `LlamaModel` and `MlflowClient` imports from `experiments.py`.

## Phase 3 — Response models (coordinate with 067)
- [ ] T030 Add `response_model=ExperimentDetail` / `list[ExperimentSummary]` to the routes.

## Phase 4 — Gates
- [ ] T040 Characterization tests (T001) still pass — response shape unchanged.
- [ ] T041 `grep -n "LlamaModel\|MlflowClient" anvil/api/v1/experiments.py` returns nothing.
- [ ] T042 `make lint && make typecheck && make test`.

## Verification (Success Criteria)
- SC-001: experiments.py reduced ≥50% (target ~430 lines from 864).
- SC-002/003: zero `LlamaModel`/`MlflowClient` refs in the route file.
- SC-004: extraction helpers unit-tested on the service.
- SC-005: parity tests green.
