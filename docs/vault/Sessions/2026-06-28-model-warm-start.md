---
title: 'Session Log: 2026-06-28 Model Warm-Start Implementation'
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/core
status: canonical
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - model-warm-start-2026-06-28
source: agent
---

# Session Log: 2026-06-28 — Model Warm-Start & Run Lineage

## Summary

Full feature lifecycle for [[Specs/039 Model Warm-Start/039 Model Warm-Start|039 Model Warm-Start]]:
**specify → clarify → plan → tasks → analyze → implement** (26 tasks) with a subsequent critical review that found and fixed 5 real bugs.

The feature adds an optional `base_model_ref` (experiment ID) to training runs, enabling warm-start from a previously trained anvil checkpoint — with vocab/dims inheritance, OOV rejection, lineage recorded as MLflow run tags, and a "Continue Training" UI button.

## Decisions made during session

- **Lineage storage**: MLflow **run tags** (`anvil.warm_start`, `anvil.base_model_ref`, `anvil.specialization_corpus`), set via existing `set_tag()` in `on_complete` — NOT new SQL table or new service method (the model registry is MLflow-backed, not a SQL table).
- **`base_model_ref` type**: `int` (experiment ID), matching the existing `model_id` convention used by `InferenceService.load_model()`.
- **Vocabulary inheritance**: warm-start reuses the base model's exact `model.chars` order (no re-sort). OOV characters in new docs are rejected with `ValueError` — no auto-grow (deferred).
- **UI affordance**: Action button on model detail page → navigates to training page with `base_model_ref` URL param → pre-fills latest version's hyperparameters.
- **Checkpoint resolution**: Reuses `InferenceService.load_model()` / `data/models/experiment_{id}.json` path — did NOT reinvent.

## Architecture review (Oracle)

Three Oracle consultations resolved correctness issues:

1. **Stdlib engine `train(model=...)` latent bug** — the engine rebuilt `uchars`/`BOS`/`vocab_size` from new docs even when a model was passed, causing token-ID drift + matrix overflow. Oracle confirmed the spec's "already supports warm-start" claim was false. **Fix**: FR-002a added; vocab/dims inherited from base model; from-scratch path byte-for-byte unchanged.

2. **Torch warm-start fake weight transfer** — the torch backend created a `TorchLlamaModel` with base dims but random weights. Oracle: *"misleading behavior, not a reasonable v1 simplification"* ranking: fix-with-weight-transfer > fail-closed > accept. **Fix**: added `load_torch_weights_from_lists()` with key/shape validation, wired into backend; 2 tests proving exact weight round-trip.

3. **Vocabulary growth** — confirmed OOV-reject is the only safe v1 behavior; char-level vocab growth (new chars → matrix resize) is a separate future feature.

## Key files created/modified

**Engine fixes**:
- `anvil/core/engine.py` — fix stdlib `train()` warm-start vocab/dims inheritance (FR-002a)
- `anvil/services/training/torch_engine.py` — add `model=` param to `train_torch()` + `load_torch_weights_from_lists()` for real weight transfer

**Service layer**:
- `anvil/services/compute/local_stdlib_backend.py` — resolve `base_model_ref`, pass `model=` to `engine.train()`
- `anvil/services/compute/local_torch_backend.py` — resolve `base_model_ref`, construct TorchLlamaModel from base dims, load weights via `load_torch_weights_from_lists()`, pass `model=` to `train_torch()`

**API + Registry**:
- `anvil/api/v1/training.py` — `TrainConfig.base_model_ref` field + dim-validation + lineage `set_tag()` in `on_complete`
- `anvil/api/v1/registry.py` — surface `anvil.*` lineage tags in version dict

**UI**:
- `anvil/api/templates/archetypes/model_detail.html` — "Continue Training" button
- `anvil/api/templates/archetypes/training.html` — URL-param pre-fill + POST payload

**Tests**: 8 unit tests (vocab, OOV, initial-loss, parity, weight transfer) + 2 e2e validation tests

## Bugs discovered during session

1. **Stdlib engine `train(model=...)` latent bug**: the spec claimed it "already supports warm-start" — Oracle proved this false (vocab/dims NOT inherited). Fixed via FR-002a.
2. **Torch warm-start weight transfer gap**: backend created random-weight TorchLlamaModel — training did not actually continue from base weights. Fixed via `load_torch_weights_from_lists()`.
3. **e2e test placement**: agent placed test in wrong directory with broken fixture. Rewritten with deterministic validation-only tests.
4. **UI pre-fill double bug**: `apiFetch()` returns Response (needs `.json()`) AND hyperparameters are nested under `versions[]`. Both fixed.
5. **Registry loop-variable shadowing**: comprehension re-used `v` as tag value while outer loop used `v` for version objects. Fixed.

## Vault changes

- New: [[Specs/039 Model Warm-Start/039 Model Warm-Start - spec|Feature Spec]] (clarified), [[Specs/039 Model Warm-Start/plan|Plan]], [[Specs/039 Model Warm-Start/tasks|Tasks]], [[Specs/039 Model Warm-Start/data-model|Data Model]], [[Specs/039 Model Warm-Start/research|Research Notes]], [[Specs/039 Model Warm-Start/quickstart|Quickstart]], [[Specs/039 Model Warm-Start/contracts/api-warm-start|API Contract]], [[Specs/039 Model Warm-Start/contracts/service-lineage|Lineage Contract]]
- ADR-043: [[Decisions/ADR-043-warm-start-vocabulary-inheritance|Warm-Start Vocabulary Inheritance]]

## References

- [[Specs/039 Model Warm-Start/039 Model Warm-Start]]
- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions]]
