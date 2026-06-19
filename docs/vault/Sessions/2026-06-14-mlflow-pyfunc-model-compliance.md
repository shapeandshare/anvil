---
created: '2026-06-14'
tags:
- type/session-log
- domain/operations
- domain/export
title: MLflow Pyfunc Model Compliance for Safetensors Export
type: session-log
aliases:
- MLflow Pyfunc Model Compliance for Safetensors Export
source: agent
updated: '2026-06-18'
---
## Summary

Made anvil-trained models fully MLflow-compliant by adding `MLmodel` + `conda.yaml` to the safetensors export, and pointing the Model Registry at the full artifact root. Users can now `mlflow.pyfunc.load_model("models:/...")` to get a working inference model.

## Files changed

| File | Change |
|---|---|
| `anvil/_pyfunc_model.py` | **New** — `AnvilPyfuncModel(PythonModel)` wrapper: loads `LlamaForCausalLM` from artifact dir, implements `predict()` with character-level tokenizer, auto device detection |
| `anvil/services/export.py` | Added `_generate_mlmodel_yaml()`, `_generate_conda_yaml()`. `export()` writes `MLmodel` + `conda.yaml` alongside safetensors/config/tokenizer. Return dict includes `mlmodel_path` and `conda_path` |
| `anvil/services/tracking.py` | `log_artifacts()` accepts and logs `mlmodel_path` + `conda_path`. `register_source_model()` defaults to `artifact_path=""` (run root) instead of `"model.json"` |
| `anvil/api/v1/experiments.py` | Retry export path passes `mlmodel_path` + `conda_path` to `log_artifacts()` |
| `anvil/api/v1/training.py` | Training completion logs `MLmodel` + `conda.yaml` via `client.log_artifact()` |
| `tests/unit/services/test_export.py` | `test_export_produces_files` validates MLmodel/conda content, pyfunc flavor reference, and dependency listing |
| `tests/unit/api/test_experiment_failure.py` | `test_download_artifact_not_found` now mocks `TrackingService.get_safetensors_artifacts` to avoid MLflow network dependency |

## What changed and why

### The problem

Before this session, the safetensors export created three files (`model.safetensors`, `config.json`, `tokenizer.json`) but no `MLmodel` descriptor. The MLflow Model Registry pointed at `model.json` (the old format) via `artifact_path="model.json"` default. This meant:

- `mlflow.pyfunc.load_model("models:/...")` would fail — no pyfunc flavor defined
- `mlflow models serve` and `mlflow models build-docker` wouldn't work
- The Model Registry UI showed an "unknown flavor" model
- Users had to download artifacts individually and load manually with `transformers`

### The fix

**`MLmodel` file** — YAML descriptor with `python_function` flavor pointing at `anvil._pyfunc_model.AnvilPyfuncModel` as the loader. This is the MLflow-standard way to make a model loadable via `pyfunc.load_model()`.

**`conda.yaml`** — minimal conda environment listing `anvil`, `transformers`, `torch`, `safetensors`, `numpy`, `pandas` so the model can be deployed to a clean environment.

**`_pyfunc_model.py`** — the `PythonModel` subclass that:
- `load_context()`: reads `config.json`, loads `LlamaForCausalLM` from `model.safetensors` via `safetensors.torch`, loads the character-level tokenizer from `tokenizer.json`
- `predict()`: accepts a DataFrame with text, generates continuations using greedy decoding

**`register_source_model` default** — changed from `artifact_path="model.json"` to `artifact_path=""` so the Model Registry points at the full artifact root (where `MLmodel`, `config.json`, `model.safetensors`, `tokenizer.json`, `conda.yaml` all live).

### How it works now

```python
# After training or retry-export, the MLflow run has:
#   model.safetensors  config.json  tokenizer.json  MLmodel  conda.yaml

# Load via Model Registry:
model = mlflow.pyfunc.load_model("models:/dataset-1/1")
result = model.predict(pd.DataFrame({"text": ["hello"]}))

# Load via transformers directly (still works):
from transformers import LlamaForCausalLM
model = LlamaForCausalLM.from_pretrained("./my-model/")
```

### Per-file download refactoring (earlier in session)

In a prior turn, the download endpoint was refactored from a single hardcoded `GET .../download/safetensors` to a generic per-file `GET .../download?path=<filename>`, with a new `GET .../artifacts` endpoint listing all available files. This was already vault-enriched in a prior session log — included here for completeness since it's part of the same session.

## Key decisions

- **Option B over Option A** — chose full MLflow Model compliance (write `MLmodel` + wrapper) over simply fixing the artifact path pointer. The additional complexity of the pyfunc wrapper is worth it for `models:/` URI support and `mlflow models serve` compatibility.
- **`anvil` package as dependency** — the pyfunc loader module (`anvil._pyfunc_model`) is importable only when `anvil` is installed. This is acceptable since the model was trained using anvil.
- **Character-level tokenizer handled in wrapper** — the tokenizer is anvil's custom format, not a standard HF tokenizer. The wrapper handles encode/decode internally using the vocab map from `tokenizer.json`.

## Discovery

- `register_source_model` was defaulting to `artifact_path="model.json"`, meaning the Model Registry pointed at the legacy format only. This was a silent design gap — the safetensors were logged as run artifacts but the registry didn't reference them.
- The `mlflow.pyfunc.PythonModel` interface requires `predict()` to return a `pd.DataFrame`. The wrapper converts input strings → token IDs → model forward pass → argmax decoding → output strings.
