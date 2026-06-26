---
title: Progressive Walkthroughs (train0 → train5)
type: reference
tags:
  - type/reference
  - domain/content
created: 2026-06-15
updated: 2026-06-15
aliases:
  - progressive-examples
  - train-scripts
  - walkthrough-progression
related:
  - '[[Reference/Hyperparameters]]'
---

# Progressive Walkthroughs: train0 → train5

## Overview

The `examples/` directory contains 6 progressively complex Python scripts (`train0.py`–`train5.py`) that teach the Llama architecture from first principles to full implementation. Each script is self-contained, runnable, and builds on concepts from the previous one.

**Location**: `examples/train0.py` through `examples/train5.py`

## The Progression

```
train0:  Bigram count table              (no neural net, no gradients)
train1:  2-layer MLP + backprop by hand  (manual chain rule, numerical gradients)
train2:  RMSNorm + Value autograd        (learned scale, Adam optimizer)
train3:  Single-head RoPE attention      (no MLP, pure causal attn)
train4:  Full single-block transformer   (RMSNorm + RoPE attention + SwiGLU MLP)
train5:  Full LlamaModel + safetensors   (multi-layer, export)
```

---

## train0: Bigram Count Table

**File**: `examples/train0.py` (16 lines)

The simplest possible "language model" — a bigram transition count table. No neural network, no gradients, no backpropagation. It simply counts how often character X is followed by character Y in the training data.

**Concepts introduced**:
- Character-level tokenization (sorted unique chars)
- Building a "vocabulary" from data
- Reading input text files
- The idea of predicting the next character given the current one

**Key code**:
```python
counts = {}
for doc in docs:
    tokens = [BOS] + [uchars.index(ch) for ch in doc] + [BOS]
    for i in range(len(tokens) - 1):
        key = (tokens[i], tokens[i + 1])
        counts[key] = counts.get(key, 0) + 1
```

**What it teaches**: The fundamental problem — predicting the next token — without any of the machinery. Establishes the baseline: even a dumb count table "learns" something from data.

---

## train1: 2-Layer MLP + Backprop By Hand

**File**: `examples/train1.py` (203 lines)

A 2-layer MLP (ReLU hidden, softmax output) trained on character prediction. The critical innovation: it implements **both** analytic gradients (chain rule by hand) and numerical gradients (finite differences), then **verifies they match**.

**Concepts introduced**:
- One-hot encoding
- Matrix multiplication for neural net forward pass
- Softmax + cross-entropy loss
- **Manual backpropagation**: writing out `dL/dW`, `dL/db` formulas by hand
- **Gradient verification**: `|analytic - numerical| < 1e-4` proves the math is correct
- SGD training loop

**Key verification**:
```python
max_diff = 0.0
for layer_idx, (a, n) in enumerate(zip(ana, num)):
    for i in range(len(a)):
        for j in range(len(a[i])):
            diff = abs(a[i][j] - n[i][j])
            max_diff = max(max_diff, diff)
print(f"Max |analytic - numerical| = {max_diff:.6e}")
```

**What it teaches**: Backpropagation is not magic — it's just the chain rule. Writing it by hand demystifies what `loss.backward()` does. The gradient verification is the "smoking gun" that proves your math matches reality.

---

## train2: RMSNorm + Value Autograd

**File**: `examples/train2.py` (80 lines)

Introduces the `Value` autograd system and RMSNorm normalization. The model becomes: **embed → RMSNorm → learned scale → lm_head**. No position encoding yet (single token prediction, no sequence).

**Concepts introduced**:
- `anvil.core.autograd.Value` — automatic differentiation via computation graph
- `rmsnorm()` — Root Mean Square normalization: `x / sqrt(mean(x²) + ε)`
- **Learned RMSNorm scale** (`rms_1`) — initialized to 1.0, learns feature importance
- `linear()` and `matrix()` helpers for weight management
- **Adam optimizer** — manual implementation with bias-corrected m/v + linear LR decay
- No more manual gradient formulas — `loss.backward()` handles everything

**Key code**:
```python
def forward(token_id: int) -> list[Value]:
    x = wte[token_id]
    n = rmsnorm(x)
    scaled = [s * xi for s, xi in zip(rms_1, n)]
    logits = linear(scaled, lm_head)
    return logits
```

**What it teaches**: Autograd eliminates manual gradient bookkeeping. RMSNorm stabilizes training. Learned scale parameters let the model decide which features are important. The transition from explicit SGD to Adam shows how optimizer design matters.

---

## train3: Single-Head RoPE Attention

**File**: `examples/train3.py` (108 lines)

A pure attention model with RoPE position encoding and no MLP. Introduces the autoregressive forward pass with KV cache.

**Concepts introduced**:
- **RoPE** (Rotary Position Encoding) via `precompute_rope()` and `apply_rope()`
- **Half-split** convention: dim i paired with dim i + head_dim/2
- **KV cache**: per-layer lists appended at each autoregressive step
- **Causal self-attention**: each position attends to itself and predecessors
- **Autoregressive training**: predict next token at each position

**Key code**:
```python
def forward(token_id, pos_id, keys_cache, values_cache):
    x = wte[token_id]
    q = linear(x, attn_wq)
    k = linear(x, attn_wk)
    v = linear(x, attn_wv)
    q = apply_rope(q, pos_id, cos_table, sin_table)
    k = apply_rope(k, pos_id, cos_table, sin_table)
    keys_cache.append(k)
    values_cache.append(v)
    # causal dot-product attention
    attn_logits = [sum(q[j] * keys_cache[t][j] for j in range(n_embd)) / d
                   for t in range(len(keys_cache))]
    attn_weights = softmax(attn_logits)
    attn_out = [sum(attn_weights[t] * values_cache[t][j] ...)]
    x = linear(attn_out, attn_wo)
    logits = linear(x, lm_head)
    return logits
```

**What it teaches**: Position encoding as rotation (not addition). The KV cache avoids recomputing previous positions. The dot-product attention mechanism is only ~10 lines of code. Values are NOT rotated — only Q and K.

---

## train4: Single Llama Transformer Block

**File**: `examples/train4.py` (140 lines)

Combines everything into one complete transformer block: **token embed → RMSNorm → multi-head RoPE attention → residual → RMSNorm → SwiGLU MLP → residual → lm_head**.

**Concepts introduced**:
- **Multi-head attention**: splitting Q/K/V per head, applying RoPE per head
- **SwiGLU MLP**: SiLU-gated gate/up/down projection with `intermediate_size = int(8 × n_embd / 3)`
- **Residual connections**: `x = attention_output + x` and `x = mlp_output + x`
- **Pre-norm architecture**: RMSNorm applied BEFORE each sublayer (attention/MLP)
- **Two RMSNorm scales**: `rms_1` (pre-attention) and `rms_2` (pre-MLP)

**Key architecture**:
```
pre-attention:  x = x_residual → rmsnorm × rms_1 → attn → + residual
pre-MLP:        x = x_residual → rmsnorm × rms_2 → SwiGLU → + residual
```

**What it teaches**: How the modern transformer block is assembled. Each component was introduced separately (train1–3) and now composes into the full block. The residual connections enable gradients to flow through without vanishing.

---

## train5: Full LlamaModel + Safetensors Export

**File**: `examples/train5.py` (45 lines)

Uses the full `LlamaModel` class and `train()` function from `anvil.core.engine`, then exports via `SafetensorsExportService`.

**Concepts introduced**:
- **Multi-layer model**: `LlamaModel(vocab_size, n_embd, n_head, n_layer, block_size)`
- **train() function**: complete training loop with Adam, LR decay, and sampling
- **Safetensors export**: converting trained weights to HuggingFace-compatible format
- **Artifact generation**: `model.safetensors`, `config.json`, `tokenizer.json`

**Key code**:
```python
from anvil.core.engine import LlamaModel, train
from anvil.services.training.export import SafetensorsExportService

model, final_loss, samples, uchars = train(docs, num_steps=200,
    n_embd=16, n_head=4, n_layer=2, block_size=16, learning_rate=0.01)

export_service = SafetensorsExportService()
result = export_service.export(model, tmpdir, uchars)
```

**What it teaches**: The culmination — everything composes into a real Llama-model training pipeline. The safetensors export means the model can be loaded by HuggingFace tools. The 45-line script hides ~700 lines of engine code that the previous 5 exercises demystified.

## Design Philosophy

The progression follows a deliberate pedagogical curve:

```
train0:    No neural net — just counting
train1:    Neural net — but NO autograd
                ↓ "autograd saves us from manual derivative hell"
train2:    Autograd — but NO position encoding
                ↓ "position is essential for sequences"
train3:    Position encoding — but NO MLP
                ↓ "MLP adds expressivity per position"
train4:    MLP — single block complete
                ↓ "stack blocks for more capacity"
train5:    Multi-layer + export — production-ready
```

Each script introduces exactly ONE new concept beyond the previous one, making it clear what each component contributes.

## See Also

- [[Decisions/ADR-007-llama-engine-evolution|ADR-007]] — Migration from GPT-2 to Llama architecture
- [[TrainingDataFlow]] — How the train() function connects to the web UI
- [[SafetensorsExport]] — Details on the export pipeline