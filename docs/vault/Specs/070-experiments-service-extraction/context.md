# Context — 070 Extract Business Logic from experiments.py

> Cross-references: `../066-codebase-remediation/data-inventory.md` §4/§5.

## Current State (verified line refs, `anvil/api/v1/experiments.py`, 864 lines)

Business-logic helpers that belong in a service:
- `_hyperparams_from_mlflow(params)` — lines 57-83 (type coercion)
- `_get_mlflow_experiment_id()` — lines 86-103 (MLflow query + exception handling)
- `_enrich_experiments(experiments)` — lines 106-128 (DB session + lookups)
- `_resolve_experiment_name(exp, ds_repo, corp_repo)` — lines 130-144
- `_resolve_name_from_ds(exp, ds_repo)` — lines 146-155
- `_resolve_name_from_corpus(exp, corp_repo)` — lines 158-167
- `_set_artifact_flag(exp)` — lines 170-176 (filesystem check)

Worst offender — `get_experiment` handler (lines 277-400+) instantiates `LlamaModel` and reads JSON:
```python
# experiments.py:322-341
model_data = await loop.run_in_executor(None, lambda: json.loads(model_path.read_text()))
vocab_size = model_data["vocab_size"]
...
gpt = LlamaModel(vocab_size, n_embd, n_head, n_layer, block_size)
model_architecture = {..., "num_params": gpt.num_params()}
```
Plus direct `MlflowClient` usage (lines 355-379) and memory estimation (lines 396-400+).

## What Stays in Route Layer

- `_build_mlflow_url(request, mlflow_exp_id)` (lines 179-199) — depends on the HTTP `Request` object for host derivation. Keep in route.

## Target Service

Add methods to `TrackingService` (or a new `ExperimentService`):
- `get_experiment_detail(id) -> ExperimentDetail` — encapsulates model architecture extraction, MLflow data, memory estimate, duration.
- `list_experiments_enriched() -> list[ExperimentSummary]` — encapsulates enrichment (name resolution, artifact flags).

## Dependencies

- Spec 069 (route DI) — the extracted service should be injected, not created inline.
- Spec 067 (response_model) — `ExperimentDetail`/`ExperimentSummary` become the route response models.

## Gotchas

- `estimate_training_memory()` is imported from `services/training/memory_estimator.py` — move the call into the service, keep the util where it is.
- Preserve exact response shape — write a characterization test capturing current JSON output BEFORE refactoring (legacy-code TDD per AGENTS.md).
- `LlamaModel` import moves from the route to the service module.
