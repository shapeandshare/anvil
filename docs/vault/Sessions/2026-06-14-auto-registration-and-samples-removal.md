---
title: Auto-Registration and Samples Removal
type: session-log
tags:
  - type/session-log
  - domain/training
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - auto-registration-and-samples-removal
source: agent
---
## Summary
Two changes to the training pipeline:

1. **Verified auto-registration** — Confirmed that on successful training completion, both the API (`POST /v1/training/start`) and CLI (`anvil train`) paths already auto-register the model with the MLflow model registry. The dataset name is used as the MLflow registered model name, with fallback chain: `dataset.name` → `corpus.name` → `"dataset-{id}"` → `"corpus-{id}"` → `"default-source"`.

2. **Removed "Generated Samples" from training page** — The training page UI no longer displays generated samples on completion. The HTML card, JS display logic, backend storage (`generated_samples=json.dumps(samples)` in `mark_finished()`), and experiments API responses were all cleaned up. The DB column and repository parameter remain for backward compatibility with existing records. Samples are still logged as `samples.txt` artifacts in MLflow, and the CLI still prints them.

## Files changed
- `anvil/api/templates/archetypes/training.html` — Removed Generated Samples card HTML, JS variables (`samplesPanel`, `samplesDisplay`), samples display loop in `handleTrainingComplete`, `samplesPanel.style.display` reset in `startTraining`
- `anvil/api/v1/training.py` — Removed `generated_samples=json.dumps(samples)` from `mark_finished()` call
- `anvil/api/v1/experiments.py` — Removed `generated_samples` from compare endpoint response, removed `json.loads(exp.generated_samples)` parsing block, removed from single experiment response dict
- `tests/unit/db/test_experiment_lifecycle.py` — Removed `generated_samples` args from `mark_finished` calls
- `tests/integration/test_orphan_reconciliation.py` — Same
- `tests/unit/api/test_experiment_failure.py` — Same
- `docs/vault/Reference/TrainingDataFlow.md` — Updated completion flow to reflect no samples display in browser

## Key decisions
- Auto-registration is fully automatic — the manual `POST /v1/registry/models` endpoint exists only as a fallback/retry. The `on_complete` callback in both API and CLI paths handles registration using the dataset's name as the MLflow model name.
- Generated samples are no longer stored in the experiment DB record. The `generated_samples` column remains for existing data but is no longer written to or returned by the API.
- Samples are still generated and logged as `samples.txt` artifacts in MLflow — the removal is only from the training page UI and associated storage/API paths.

## Related

- [[Reference/TrainingDataFlow|Training Data Flow]] — training completion flow documentation
- [[Reference/MlflowIntegration|MLflow Tracking]] — MLflow model registration integration
- [[Specs/Specs|Specs]] — feature specification index