---
title: Dual Backend Architecture (CPU vs GPU)
type: reference
tags:
  - type/reference
  - domain/core
created: 2026-06-15
updated: 2026-06-15
aliases:
  - cpu-gpu-bridge
  - dual-backend
  - torch-bridge
---

# Dual Backend Architecture: CPU vs GPU Bridge

## Overview

anvil has two complete training backends: a **pure Python CPU engine** (zero dependencies) and a **PyTorch GPU engine** (optional, for CUDA/MPS acceleration). Both implement identical Llama architecture — they must produce the same logits for the same weights. The dual-backend architecture is a design constraint driven by two goals:

1. **Zero-dependency education**: Anyone can `pip install anvil` and train a real Llama-model transformer using nothing but Python stdlib.
2. **GPU acceleration**: When PyTorch is available, training runs 10-100x faster on CUDA or MPS.

## Architecture

```
TrainingService.start_training()
    │
    ├── resolve_device(use_gpu, preferred)
    │     └── auto-detect: CUDA > MPS > CPU
    │
    ├── is GPU and torch_available()?
    │     YES → train_torch()        (GPU backend)
    │     NO  → train()              (CPU backend)
    │
    └── Result:
          GPU: raw_weight_dict + loss + samples + uchars
          CPU: LlamaModel object + loss + samples + uchars
                │
                └── GPU → CPU bridge:
                      Create CPU LlamaModel
                      _load_weights_into_model(cpu_model, gpu_weights)
```

**File**: `anvil/services/training.py` — `TrainingService.start_training()`, lines 224-268

## Backend Comparison

| Aspect | CPU Backend (`engine.py`) | GPU Backend (`torch_engine.py`) |
|--------|--------------------------|--------------------------------|
| **Dependencies** | None (stdlib: `random`, `math` only) | `torch`, `torch.nn.functional` |
| **Tensor type** | `Value` objects (autograd graph) | `torch.Tensor` (CUDA/MPS) |
| **Autograd** | Custom `Value.backward()` (topological sort) | `torch.autograd` (native) |
| **Optimizer** | Manual Adam: bias-corrected m/v + linear LR decay | `torch.optim.Adam` + `LambdaLR` scheduler |
| **Speed** | ~100 token/sec (single core) | ~10,000+ token/sec (GPU) |
| **Model export** | `LlamaModel.state_dict` → JSON | `export_weights()` → plain dict → bridge to CPU model |
| **Forward signature** | Same: `(token_id, pos_id, keys, values)` | Same: `(token_id, pos_id, keys, values)` |
| **RoPE** | Precomputed cos/sin lists | Precomputed cos/sin tensors (same math) |

## The Weight Bridge

GPU training produces raw weight lists (Python `list[list[float]]`), not `Value` objects. The bridge function `_load_weights_into_model()` copies these into a freshly created CPU `LlamaModel`:

```python
def _load_weights_into_model(model: LlamaModel, weights: dict) -> None:
    for k, data in weights.items():
        mat = model.state_dict[k]
        if isinstance(mat[0], list):
            for i, row in enumerate(data):
                for j, val in enumerate(row):
                    mat[i][j].data = val
        else:
            for i, val in enumerate(data):
                mat[i].data = val
```

**Constraint**: Both backends use IDENTICAL architecture — every weight key, every shape, every norm position, every activation function. If the architectures diverge, the bridge silently produces wrong logits. This is enforced by code review (see ADR-007: "GPU consistency — torch_engine.py migrated to match; no separate architecture allowed").

## Architecture Parity Checklist

| Component | CPU (`engine.py`) | GPU (`torch_engine.py`) |
|-----------|-------------------|------------------------|
| Token embedding | `wte[token_id]` | `wte[token_id]` |
| Learned RMSNorm scale | `rms_1[layer][i] * rmsnorm(x)[i]` | `F.rms_norm(x) * rms_1[layer]` |
| Position encoding | `apply_rope()` half-split | Manual half-split rotation |
| KV cache | `keys[li].append(k)`, same for values | Identical append pattern |
| Attention scaling | `/ head_dim**0.5` | `/ (head_dim**0.5)` |
| Softmax | Custom `softmax()` | `F.softmax()` |
| Post-attn residual | `x = [a + b for a, b in ...]` | `x = x + x_residual` |
| SwiGLU gate | `.silu()` on Value | `F.silu()` on Tensor |
| SwiGLU combined | `[g * u for g, u in zip(gate, up)]` | `gate * up` |
| Post-MLP residual | Same as attention | Same as attention |
| Final norm | `rmsnorm(x) * rms_final` | `F.rms_norm(x) * rms_final` |
| Output | `linear(n, lm_head)` | `F.linear(x, lm_head)` |

## Compute Backend Registry

Training no longer selects backends via a simple `use_gpu` boolean. The ADR-015 pluggable compute backend abstraction uses a **string-key registry** (`anvil/services/compute/registry.py`) with composite names:

| Registry name | Engine | Registering module |
|---|---|---|
| `"local-stdlib"` | Stdlib (`engine.py`) | `anvil/services/compute/local.py` |
| `"local-torch"` | PyTorch (`torch_engine.py`) | `anvil/services/compute/local.py` |
| `"modal"` | PyTorch (remote) | `anvil/services/compute/modal_backend.py` |

### Naming Layer Gap

**`resolve_backend()`** (in `anvil/services/compute/resolve.py`) returns human-facing category names: `"local"` for both local-stdlib and local-torch, `"modal"` for cloud GPU. The registry expects the composite name.

**`TrainingService.start_training()`** is the bridge layer that must translate:

```python
resolved = resolve_backend(config)
backend_name = resolved["backend"]  # "local" | "modal"
engine_name = resolved["engine"]    # "stdlib" | "torch"

if backend_name == "local":
    backend_name = f"local-{engine_name}"  # "local-stdlib" | "local-torch"

backend = get_backend(backend_name)
```

**`"modal"`** matches 1:1 in both layers — no translation needed. But for `"local"`, the translation was missing, causing `get_backend("local")` to raise `ComputeBackendUnavailable`. This silently killed training in the background task before any SSE metrics were emitted (see [[Sessions/2026-06-18-backend-registry-orphaned-name]]).

## Device Resolution

Device selection happens in `anvil/gpu.py` via `resolve_device()`:

```python
def resolve_device(use_gpu: bool = False, preferred: str | None = None) -> str:
    # Priority: preferred > CUDA > MPS > CPU
```

- **CUDA**: NVIDIA GPU, Linux only (CUDA toolkit + `nvidia-ml-py` for metrics)
- **MPS**: Apple Silicon Mac (Metal Performance Shaders)
- **CPU**: Fallback, no accelerator

## When to Use Each Backend

| Scenario | Backend | Rationale |
|----------|---------|-----------|
| Learning / education | CPU | Zero deps, inspectable Value graph, no GPU needed |
| Quick experiments | CPU | Fast startup, no CUDA init overhead |
| Large training runs (1000+ steps) | GPU | 10-100x speed improvement |
| Apple Silicon Mac | GPU | MPS auto-detected, excellent perf |
| CI / testing | CPU | No GPU dependency in CI pipelines |
| Production deployment | GPU | Inference via TorchLlamaModel on GPU |

## See Also

- [[TrainingDataFlow]] — How training is dispatched via the service layer
- [[Decisions/ADR-002-sync-core-async-bridge|ADR-002]] — Why core engine runs in a thread pool
- [[Decisions/ADR-007-llama-engine-evolution|ADR-007]] — Architecture consistency requirements
- [[Glossary]] — Value, Autograd, KV Cache definitions