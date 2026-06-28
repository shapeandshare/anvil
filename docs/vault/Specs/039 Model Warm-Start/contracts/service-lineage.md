# Contract: Lineage Recording

**Spec**: 039 Model Warm-Start | **FR**: FR-003

## Purpose

Record warm-start lineage as MLflow **run tags** in the existing `on_complete` flow in
`anvil/api/v1/training.py`. The anvil model registry is MLflow-backed (no SQL model table), so lineage
is stored as tags on the training run via the **existing** `TrackingService.set_tag()` method — no new
service method is required.

## Integration Point (existing code)

In `anvil/api/v1/training.py`, the `on_complete(result, _config)` callback already sets tags on the
MLflow run after training completes (e.g. the `architectures` tag at ~line 656). Lineage tags are added
at the same site. The endpoint closure has `config` (the `TrainConfig`) in scope:

```python
async def on_complete(result: ComputeResult, _config: dict[str, Any]) -> None:
    ...
    if mlflow_run_id:
        await tracking_svc.finish_run(mlflow_run_id)
        await tracking_svc.log_final_metric(mlflow_run_id, "final_loss", final_loss)
        await tracking_svc.set_tag(mlflow_run_id, "architectures", "LlamaForCausalLM")

        # NEW: warm-start lineage tags (only when base_model_ref is set)
        if config.base_model_ref is not None:
            await tracking_svc.set_tag(mlflow_run_id, "anvil.warm_start", "true")
            await tracking_svc.set_tag(
                mlflow_run_id, "anvil.base_model_ref", str(config.base_model_ref)
            )
            await tracking_svc.set_tag(
                mlflow_run_id, "anvil.specialization_corpus", specialization_corpus_name
            )
```

`specialization_corpus_name` is resolved from `dataset_id`/`corpus_id` the same way `registry_name` is
resolved later in the same function (lines ~793-807).

## Tags Written

| Tag Key | Value | Condition |
|---------|-------|-----------|
| `anvil.warm_start` | `"true"` | Only when `base_model_ref` is set |
| `anvil.base_model_ref` | Experiment ID as string | Only when `base_model_ref` is set |
| `anvil.specialization_corpus` | Dataset/corpus name | Only when `base_model_ref` is set |

## Read Path (minimal change)

`TrackingService.list_registered_models()` and `GET /v1/registry/models/{model_id}` already read
`run.data.tags` via `client.get_run(run_id)`. Surfacing lineage requires only mapping the three
`anvil.*` tags into the response dict (see `api-warm-start.md`).

## Error Handling

- `set_tag()` already no-ops in degraded mode (`if self._degraded or not run_id: return`) and swallows
  MLflow exceptions — lineage recording cannot fail the training run
- No new method, no new error type

## Why NOT a new `record_warm_start_lineage()` method

The original plan proposed a new `TrackingService.record_warm_start_lineage()` method. Rejected on
review (YAGNI / Reuse-first, Constitution Article XI): `set_tag()` already exists, is already called in
`on_complete`, and already handles degraded mode. Three `set_tag()` calls are simpler than a new method
that wraps them.