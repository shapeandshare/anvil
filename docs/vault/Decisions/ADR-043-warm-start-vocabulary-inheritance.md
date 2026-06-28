---
title: 'ADR-043: Native Model Warm-Start — Vocabulary Inheritance and MLflow Run Tag Lineage'
type: decision
tags:
  - type/decision
  - domain/training
  - domain/core
status: draft
code-refs:
  - anvil/core/engine.py
  - anvil/services/training/torch_engine.py
  - anvil/services/compute/local_stdlib_backend.py
  - anvil/services/compute/local_torch_backend.py
  - anvil/api/v1/training.py
  - anvil/api/v1/registry.py
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - ADR-043
  - warm-start-vocabulary-inheritance
source: 'Spec 039 Model Warm-Start'
---

# ADR-043: Native Model Warm-Start — Vocabulary Inheritance and MLflow Run Tag Lineage

## Status

Draft

## Context

Spec 039 introduces native warm-start: continuing training of anvil's own char-level `LlamaModel` checkpoints on a new corpus. This requires resolving several architecture questions about vocabulary handling, weight transfer, and lineage storage.

### Key constraints

1. **Zero new dependencies** — the stdlib engine (`anvil/core/engine.py`) keeps its stdlib-only guarantee (Article I).
2. **From-scratch path unchanged** — a training run without `base_model_ref` is byte-for-byte today's pretraining flow (FR-027).
3. **The model registry is MLflow-backed** — there is no anvil SQL table for models.
4. **Simplicity First (Article XI)** — choose the simplest viable solution; defer speculative generality.

## Decision: Fix stdlib engine warm-start (FR-002a)

**The stdlib engine `train(docs, model=...)` is NOT warm-start-safe today.** It reuses the model's weights but rebuilds `uchars`, `BOS`, `vocab_size`, and `block_size` from the NEW corpus, causing token-ID drift and possible matrix overflow.

**Fix**: In the `model is not None` branch, derive `uchars` from `model.chars` (exact order, no re-sort), `vocab_size` from `model.vocab_size`, `BOS` from `len(uchars)`, and `block_size` from `model.block_size`. Pre-scan docs for out-of-vocabulary characters; raise `ValueError` on OOV. The `model is None` path is unchanged.

**Rationale**: This is the minimal change that makes warm-start correct. OOV-reject (rather than auto-grow) is chosen because vocab growth is a separate feature with matrix-resize semantics, heavier testing requirements, and no present consumer. Per YAGNI and Simplicity First, it is deferred.

## Decision: Torch warm-start with real weight transfer (FR-002)

The torch backend (`LocalTorchBackend`) must support warm-start at parity with the stdlib engine. This requires transferring the base `LlamaModel`'s trained weights (plain Python lists of floats in the JSON checkpoint) into `TorchLlamaModel`'s `nn.Parameter` tensors.

A new module-level function `load_torch_weights_from_lists()` in `anvil/services/training/torch_engine.py` handles this: it maps checkpoint keys to `TorchLlamaModel` parameters (no transpose needed — stdlib matrix layout matches `nn.functional.linear`), validates keys and shapes, and copies tensor data under `torch.no_grad()`. Rejects mismatches with `ValueError`.

**Rationale**: The alternative (constructing TorchLlamaModel with random init and calling it "warm-start") is misleading. Oracle confirmed this ranking: fix-with-weight-transfer ≫ fail-closed ≫ current-fake ≫ accept-as-is. The fix is ~50 lines, well-tested, and satisfies FR-002 parity.

## Decision: Lineage as MLflow run tags (FR-003)

The anvil model registry is MLflow-backed (no SQL table). Lineage information (`anvil.warm_start`, `anvil.base_model_ref`, `anvil.specialization_corpus`) is stored as **MLflow run tags**, set via the existing `TrackingService.set_tag()` in the `on_complete` callback in `anvil/api/v1/training.py`.

**Rationale**: Run tags (not version tags) because the existing read path (`list_registered_models`, `get_model`) reads `run.data.tags` via `client.get_run(run_id)`. No new `TrackingService` method needed — `set_tag()` already exists and handles degraded mode. No new schema or migration.

**Alternatives considered**: (a) New `ModelLineage` SQL table — adds a table/repo/service for a key-value store MLflow already provides (YAGNI). (b) A new `record_warm_start_lineage()` service method — three `set_tag()` calls are simpler (Reuse-first, Article XI).

## Decision: Checkpoint resolution reuses `InferenceService.load_model()`

`InferenceService.load_model(model_id)` is the canonical resolver: it loads `data/models/experiment_{id}.json` (primary) or downloads `model.json` from the MLflow registry (fallback). The backends reuse this path rather than reinventing file-path logic.

## Consequences

1. **Stdlib engine fix is corrective**: the `model is not None` branch's "already works" claim was false. The fix is guarded so `model=None` produces identical output (FR-027).
2. **No anvil DB schema change**: lineage is purely in MLflow.
3. **OOV characters in new corpus → fail-fast**: users who want to "teach the model new characters" must wait for a future vocab-growth feature. This is the safe default; silent character dropping would corrupt training.
4. **Torch warm-start weight transfer verified**: 2 new tests prove exact weight round-trip and shape-mismatch rejection.
5. **ADR-016 (MLflow as Primary Lineage Source of Truth)** and **ADR-015 (Pluggable Compute Backends)** are unchanged — this feature extends them rather than modifying them.
