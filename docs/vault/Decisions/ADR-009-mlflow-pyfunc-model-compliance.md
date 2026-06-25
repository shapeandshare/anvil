---
created: '2026-06-14'
tags:
- type/decision
- domain/operations
- domain/export
title: ADR-009 — MLflow Pyfunc Model Compliance
type: decision
aliases:
- ADR-009 — MLflow Pyfunc Model Compliance
source: agent
updated: '2026-06-18'
code-refs:
- anvil/_pyfunc_model.py
- anvil/services/training/export.py
- anvil/services/tracking/tracking_service.py
---
# ADR-009: MLflow Pyfunc Model Compliance for Safetensors Export

**Status**: Accepted

## Context

The safetensors export pipeline produces three HuggingFace-compatible files (model.safetensors, config.json, tokenizer.json) that are logged as MLflow run artifacts. The MLflow Model Registry was configured to point at model.json (the legacy anvil internal format) via register_source_model(artifact_path="model.json").

This created two problems:

1. No MLmodel descriptor — mlflow.pyfunc.load_model("models:/...") failed because no pyfunc flavor was defined
2. Wrong registry target — the Model Registry pointed at the legacy model.json instead of the safetensors artifact root

Two approaches were considered.

## Decision

Adopt Option B: Generate an MLmodel YAML file and conda.yaml alongside the safetensors artifacts, and implement a PythonModel wrapper (anvil._pyfunc_model.AnvilPyfuncModel) as the pyfunc loader. Change register_source_model to default to artifact_path="" (the run artifact root).

### Option A (rejected) — Fix only the registry pointer

Change artifact_path from "model.json" to "" so the registry points at the full artifact directory. This would make models:/ downloads work, but mlflow.pyfunc.load_model() and mlflow models serve would still fail because no MLmodel file exists.

### Option B (accepted) — Full MLflow Model compliance

In addition to the registry pointer fix, generate an MLmodel file with a python_function flavor backed by a custom PythonModel wrapper. This makes the model fully compatible with:
- mlflow.pyfunc.load_model("models:/...")
- mlflow models serve
- mlflow models build-docker
- MLflow Model Registry UI (shows a known flavor)

The wrapper handles:
- Loading LlamaForCausalLM from config.json + model.safetensors
- Character-level tokenizer encode/decode from tokenizer.json
- Text generation via greedy decoding
- Automatic CPU/CUDA device selection

## Consequences

Positive:
- mlflow.pyfunc.load_model("models:/...") works out of the box
- Model Registry shows a proper pyfunc flavor
- mlflow models serve can serve anvil-trained models
- The model artifact directory is self-describing

Negative:
- The pyfunc loader depends on the anvil package being importable at inference time
- The character-level tokenizer is non-standard (wrapper handles it manually)
- Users who want to use transformers directly still can — raw files are unchanged

## Compliance

- Every safetensors export MUST produce MLmodel and conda.yaml
- The MLmodel MUST reference loader_module: anvil._pyfunc_model
- The conda.yaml MUST list anvil, transformers, torch, safetensors, numpy, and pandas
- register_source_model MUST default to artifact_path=""

## See Also

- [[Decisions/README|Decisions]]
