---
title: Duplicated Forward Pass in core/engine.py
type: discovery
status: draft
source: agent
session: 2026-06-19-lint-sweep
code-refs:
  - anvil/core/engine.py
created: '2026-06-19'
updated: '2026-06-19'
tags:
  - type/discovery
  - domain/core
  - status/draft
aliases:
  - Duplicated Forward Pass in engine.py
---
# Duplicated Forward Pass in `core/engine.py`

`anvil/core/engine.py` contains two complete copies of the transformer forward pass:

1. **`LlamaModel.forward()`** (~lines 110-210) — the primary forward method used by the inference service and most training paths. Uses 8-space indentation for method-level code.

2. **Embedded forward pass inside `train()`** (~lines 280-480) — a second copy of essentially the same logic, duplicated inline within the `train()` function. Uses 12-space indentation for the nested function body.

Both copies implement the same RoPE-attention + SwiGLU-MLP + RMSNorm + residual stream + final RMSNorm + lm_head pipeline. The duplication means every B905 (`zip()` without `strict=`) fix, every formatting change, and every logic update must be applied to both copies — they diverge easily.

## Implications

- Maintenance burden: ~2x effort for any change to the forward pass logic.
- Bug risk: the two copies can drift silently (e.g., one gets `strict=True` on zip calls while the other doesn't).
- The `train()` function's embedded copy exists because the stdlib engine's `train()` needs direct access to the forward pass internals (Value graph, gradient tracking). A refactor should extract the shared forward pass into a method both paths can call, or parameterize the single forward pass for training vs inference mode.

## References

- `anvil/core/engine.py` — `LlamaModel.forward()` (first copy) and `train()` (second copy)
