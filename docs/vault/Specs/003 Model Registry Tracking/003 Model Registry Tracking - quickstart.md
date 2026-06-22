---
title: 003 Model Registry Tracking - quickstart
type: quickstart
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/003 Model Registry Tracking/
related:
  - '[[003 Model Registry Tracking]]'
created: ~
updated: ~
---
# Quickstart: Model Registry

**Date**: 2026-06-11 | **Feature**: Model Registry Tracking

## What This Feature Does

Adds a local model registry to anvil so users can:
1. Register trained models from completed experiments
2. Browse and search registered models
3. View version history and training metadata
4. Select registered models (not raw experiments) for inference
5. Delete models or specific versions

## How to Use

### Register a Model

1. Complete a training experiment
2. Go to **Experiments** page
3. Find the completed experiment in the list
4. Click **Register Model** button
5. Enter a name (e.g., "shakespeare-gpt") and optional description
6. The model is registered as version 1

### View Registered Models

1. Navigate to **Models** tab (new, in top navigation bar)
2. Browse the chronological list with name search
3. Click a model to see its version history

### Run Inference with a Registered Model

1. Go to **Inference** page
2. Select a registered model from the dropdown (no experiment checkpoints shown)
3. If the model has multiple versions, choose the desired version
4. Configure sampling parameters and run

### Delete a Model or Version

1. On a model's detail page, click **Delete Version** next to a specific version
2. Or click **Delete Model** to remove the entire model (all versions)
3. Confirm in the dialog — if the model is in use for inference, a warning is shown

## What Changed

| Component | What Changed |
|-----------|-------------|
| Database | New `registered_models` and `model_versions` tables |
| API | New `/v1/registry/*` endpoints; `/v1/inference/models` now queries registry |
| UI | New **Models** navigation tab; Inference model selector uses registry |
| Training | Model artifacts now also saved to registry storage on registration |
| CLI | `MicroGPTWorkbench` god class exposes `ModelRegistryService` |

## Migration

Run `alembic upgrade head` to create the new tables.