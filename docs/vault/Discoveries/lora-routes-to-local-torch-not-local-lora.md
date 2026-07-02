---
title: LoRA Jobs Route to local-torch Not local-lora
type: discovery
status: draft
source: agent
related:
  - '[[Decisions/ADR-015-pluggable-compute-backends|ADR-015]]'
  - '[[Specs/044 Local LoRA Fine-Tuning/044 Local LoRA Fine-Tuning - spec]]'
  - '[[Specs/046 Fine-Tune Compute Routing/046 Fine-Tune Compute Routing - spec]]'
code-refs:
  - anvil/services/training/training.py
  - anvil/services/compute/resolve.py
  - anvil/services/compute/local_lora_backend.py
  - anvil/services/compute/registry_backend.py
session: '2026-07-01'
created: '2026-07-01'
updated: '2026-07-01'
summary: The training orchestrator maps ComputeBackendResult.LOCAL to
  "local-{engine}" (local-stdlib/local-torch), so LoRA/QLoRA jobs never reach the
  registered LocalLoraBackend ("local-lora"). Pre-dates spec 046; introduced with
  the spec-044 lora branch. Documented here as a separate fix, out of 046 scope.
tags:
  - type/discovery
  - domain/training
  - domain/operations
  - status/draft
aliases:
  - LoRA Routes to local-torch Not local-lora
---

## The gap

`LocalLoraBackend` auto-registers in the compute registry under the name
`RegistryBackend.LOCAL_LORA = "local-lora"` (`local_lora_backend.py:570`). But the
training orchestrator never looks it up by that name.

The dispatch chain in `TrainingService.start_training()`:

```python
resolved = resolve_backend(config)                 # training.py:518
backend_name = resolved["backend"]                  # ComputeBackendResult.LOCAL
engine_name = resolved["engine"]                    # TrainingEngine.TORCH (fine-tunes)

if backend_name == ComputeBackendResult.LOCAL:      # training.py:527
    backend_name = f"local-{engine_name}"           # training.py:528 → "local-torch"

backend = get_backend(backend_name)                 # training.py:544 → LocalTorchBackend
```

For a LoRA/QLoRA job:

1. `resolve_backend()` delegates to `resolve_fine_tune()` (the spec-046 delegation),
   which returns `backend = ComputeBackendResult.LOCAL`, `engine = TrainingEngine.TORCH`.
2. `training.py:528` remaps `LOCAL` → `f"local-{engine}"` = **`"local-torch"`**.
3. `get_backend("local-torch")` returns `LocalTorchBackend`, **not** `LocalLoraBackend`.

So `LocalLoraBackend` — the PEFT/`transformers` adapter backend from spec 044 — is
registered but structurally unreachable through the normal training dispatch path.
The `"local-{engine}"` remap only ever produces `"local-stdlib"` or `"local-torch"`.

## Why it pre-dates spec 046

Before spec 046, the lora/qlora branch of `resolve_backend()`
(`resolve.py:111-119`, added by spec 044) already returned
`{"engine": TORCH, "device": ..., "backend": ComputeBackendResult.LOCAL}`. The
same `training.py:528` remap therefore already produced `"local-torch"` for LoRA
jobs. Spec 046 only refactored that branch to delegate to `resolve_fine_tune()` —
it preserved the `backend = LOCAL` return value, so the misrouting is unchanged,
not introduced by 046.

This was left out of spec-046 scope deliberately (bugfix discipline: do not expand
a routing spec into a training-dispatch fix).

## Options for the eventual fix

1. **Distinct result enum**: give `resolve_fine_tune()` a dedicated
   `ComputeBackendResult.LOCAL_LORA` (or similar) and teach `training.py` to map it
   to `"local-lora"`. Cleanest, but adds an enum member and a mapping branch.
2. **Method-aware remap in training.py**: when `config["method"]` is `lora`/`qlora`
   and `backend_name == LOCAL`, set `backend_name = RegistryBackend.LOCAL_LORA`
   instead of `f"local-{engine}"`. Smallest change, keeps the enum surface stable.
3. **Verify it even matters**: confirm whether `LocalTorchBackend` silently
   mishandles a LoRA config (wrong artifact shape, no adapter) or errors. If it
   errors loudly, severity is lower; if it silently trains a full model, it is a
   correctness bug that produces the wrong artifact.

Recommended: option 2 (smallest, method-aware) plus a regression test asserting
`get_backend` resolves to `LocalLoraBackend` for a lora/qlora config.

## References

- `anvil/services/training/training.py:518-544` — dispatch + `local-{engine}` remap
- `anvil/services/compute/resolve.py` — `resolve_fine_tune()` returns `LOCAL`
- `anvil/services/compute/local_lora_backend.py:570` — registers as `"local-lora"`
- `anvil/services/compute/registry_backend.py` — `LOCAL_LORA`, `LOCAL_TORCH`
