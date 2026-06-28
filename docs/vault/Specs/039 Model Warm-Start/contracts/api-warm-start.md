# Contract: Warm-Start API

**Spec**: 039 Model Warm-Start | **FR**: FR-001, FR-003a

## POST /v1/training/start — Extended Request Body

### TrainConfig (Pydantic — modified)

New field added to the existing `TrainConfig` model in `anvil/api/v1/training.py`:

```python
class TrainConfig(BaseModel):
    # ... existing fields ...
    base_model_ref: int | None = Field(
        default=None,
        description="Experiment ID to warm-start from. When set, training resumes from the "
                    "identified checkpoint instead of random initialization. Architecture "
                    "dimensions (n_embd, n_head, n_layer, block_size) AND vocabulary are "
                    "inherited from the base checkpoint; incompatible explicit overrides are "
                    "rejected with HTTP 422.",
    )
```

> **Note**: `base_model_ref` is `int` (experiment ID), matching the existing `model_id` convention
> used by `InferenceService.load_model()` and the registry routes. `TrainConfig` uses
> `ConfigDict(extra="forbid")`, so the field MUST be added explicitly.

### Validation

- When `base_model_ref` is set and explicit `n_embd`/`n_head`/`n_layer`/`block_size` differ from the base checkpoint's stored dims → HTTP 422 with a clear error message
- When `base_model_ref` points to a non-existent or corrupt checkpoint (`InferenceService.load_model` raises `ValueError`) → HTTP 422 with "Base checkpoint not found or invalid"
- When the training corpus contains characters absent from the base model's `model.chars` → HTTP 422 listing a sample/count of unsupported chars (surfaced from the engine's `ValueError`)
- When `base_model_ref` is None → existing from-scratch behavior, unchanged

### Checkpoint resolution

The endpoint resolves `base_model_ref` (int experiment ID) to a `LlamaModel` by reusing
`InferenceService.load_model(model_id=base_model_ref)` — which loads `data/models/experiment_{id}.json`
(primary) or downloads `model.json` from the MLflow registry (fallback). Validation reads
`model.n_embd`, `model.n_head`, `model.n_layer`, `model.block_size`, and `model.chars` from the loaded
model.

## GET /v1/registry/models/{model_id} — Extended Response

Model detail response surface lineage tags. The response already includes an MLflow-backed model object. Add:

```python
# Fields on model detail response:
lineage: dict[str, str] | None = None
# Example: { "warm_start": "true", "base_model_ref": "model-123", "specialization_corpus": "my-corpus" }
```

## Training Page — URL Parameter

**Route**: `GET /v1/training-page?base_model_ref={model_id}`

### Behavior

1. Training page detects `base_model_ref` URL parameter on load
2. Fetches model details from `GET /v1/registry/models/{model_id}`
3. Pre-fills hyperparameter form from the base model version's stored hyperparameters
4. Hides or marks `base_model_ref` field as "Warm-starting from [model name]"
5. `startTraining()` includes `base_model_ref` in the JSON payload
6. Architecture dimension fields (`n_embd`, `n_layer`, `n_head`, `block_size`) become read-only with a note "Inherited from base model"

## Model Detail Page — Action Button

**Route**: `GET /v1/model-detail/{model_id}`

### Affordance

Add a "Continue Training" button with CSS class `btn-accent` alongside the existing "Play" button:

```html
<a href="/v1/training-page?base_model_ref={{ model_id }}" class="btn btn-accent btn-sm"
   style="margin-top: var(--space-2);">
  Continue Training
</a>
```

### Visibility

- Always visible on model detail page (every registered anvil checkpoint can be warm-started)
- Hidden if the model was imported from HuggingFace (external models — out of scope for this spec, see spec 040+)