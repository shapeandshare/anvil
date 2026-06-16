---
title: Hyperparameter Interaction Guide
type: reference
tags:
  - type/reference
  - domain/core
created: 2026-06-15
updated: 2026-06-15
aliases:
  - hyperparameters
  - parameter-guide
  - hyperparameter-tuning
---

# Hyperparameter Interaction Guide

## Overview

This document explains how anvil's hyperparameters interact — how changing one affects model capacity, training dynamics, and output quality. It bridges the gap between the defaults in the training UI and intuition about what to adjust when things aren't working.

## Architecture Parameters

### `n_embd` — Embedding Dimension (default: 16)

The width of every hidden vector in the model. All internal representations — token embeddings, attention outputs, MLP hidden states — are vectors of this size.

**Effects**:
- **Capacity**: Larger `n_embd` = more information per token position. Each dimension can encode a different feature.
- **Parameter count**: Scales as **O(n_embd²)** — doubling `n_embd` quadruples parameters.
- **Head count constraint**: `n_embd` must be divisible by `n_head`.

**When to adjust**:
- Loss plateaus above random baseline → increase `n_embd`
- Training is fast but loss stays high → increase `n_embd`
- Training is slow but loss is already low → decrease `n_embd`

### `n_head` — Attention Heads (default: 4)

Number of parallel attention computations. Each head sees `head_dim = n_embd / n_head` dimensions of each token.

**Effects**:
- **Representational diversity**: More heads = more relationship patterns learned simultaneously (e.g., one head tracks adjacent chars, another tracks word boundaries).
- **Per-head resolution**: `head_dim` must be even (RoPE constraint). Smaller `head_dim` = fewer dimensions per head = potentially less expressive per-head patterns.
- **Parameter cost**: Attention Q/K/V/O projection matrices are `n_embd × n_embd` regardless of `n_head` — the cost is in the per-head split and recombine, not extra parameters.

**When to adjust**:
- Attention heatmaps show all heads attending identically → heads may be underutilized (try fewer)
- Attention patterns look random across all positions → `head_dim` may be too small (try fewer heads with larger `head_dim`)
- Must satisfy: `n_embd % n_head == 0` and `(n_embd / n_head) % 2 == 0`

### `n_layer` — Transformer Depth (default: 1)

Number of sequential transformer blocks. Each block = one attention + one SwiGLU MLP with residual connections.

**Effects**:
- **Hierarchical patterns**: More layers enable the model to build progressively more abstract representations. Layer 1 might learn character patterns; layer 2 would learn syllable patterns on top of that.
- **Parameter count**: Each layer adds attention (4 × `n_embd²`) + SwiGLU (~2.67 × `n_embd²`) + RMSNorm (2 × `n_embd`) parameters.
- **Learning difficulty**: Deeper models are harder to train — gradients must flow through more layers (mitigated by residual connections and RMSNorm).

**When to adjust**:
- Training loss decreases smoothly but slower than expected for the data complexity → try more layers
- Loss diverges or oscillates with 2+ layers → try fewer layers or lower learning rate
- Cross-entropy loss > 3.0 (worse than random) with 1 layer on complex data → definitely increase layers or `n_embd`

### `block_size` — Context Window (default: 16)

Maximum number of tokens the model can attend to at once. Also the length of training subsequences.

**Effects**:
- **Long-range patterns**: Larger `block_size` lets the model learn dependencies across more characters.
- **Training speed**: Longer sequences = more forward passes per step (one per position within the block).
- **Quadratic attention**: Attention cost is O(block_size²) in the forward pass (each position attends to all previous).
- **RoPE table size**: Precomputed cos/sin tables are `block_size × head_dim/2`.

**When to adjust**:
- Generated text shows no long-range coherence → increase `block_size`
- Training is too slow with large `block_size` → decrease it
- Training documents are very short → `block_size` can be small

## Training Parameters

### `num_steps` — Training Iterations (default: 1000)

Total number of parameter update steps.

**Effects**:
- **Convergence**: More steps = more updates = lower potential loss.
- **Overfitting risk**: Too many steps on small data can cause memorization rather than generalization.
- **Learning rate decay**: The LR decays linearly from `learning_rate` to 0 over `num_steps`. More steps means gentler decay per step.

**When to adjust**:
- Loss is still decreasing sharply at step 1000 → increase
- Loss flattened 500 steps ago → decrease (wasted computation)
- Default 1000 works for demo data; real training may need 5000+

### `learning_rate` — Step Size (default: 0.01)

Controls how much each parameter changes per update.

**Interactions**:
- **With `n_embd`**: Wider models often need lower LR (more parameters, more variance in updates).
- **With `n_layer`**: Deeper models are more sensitive to LR — what works for 1 layer may cause divergence for 4 layers.
- **With `num_steps`**: More steps can compensate for lower LR (gentler, longer training).

**When to adjust**:
- Loss oscillates or spikes → decrease (2-5x)
- Loss decreases very slowly → increase (2-5x), but watch for divergence
- Sweet spot for anvil's small models: 0.005 – 0.05

### `beta1` / `beta2` — Adam Momentum Decay (default: 0.85 / 0.99)

Adam's exponential moving average decay rates for the first moment (gradient mean) and second moment (gradient variance).

| Value | Effect |
|-------|--------|
| `beta1` high (0.95+) | Strong momentum — smooths noisy gradients but may overshoot |
| `beta1` low (0.8) | Weak momentum — reacts faster but noisier updates |
| `beta2` high (0.999) | Long variance memory — stable for sparse gradients |
| `beta2` low (0.95) | Short variance memory — adapts faster to gradient scale changes |

**When to adjust**:
- Defaults (0.85, 0.99) work well for anvil's small models
- For noisy/chaotic loss curves → increase `beta1` (smoother momentum)
- For plateaus → decrease `beta1` (less momentum hangover)

### `temperature` — Sampling Creativity (default: 0.5)

Scales logits before softmax during generation: `p = softmax(logits / temperature)`.

| Value | Effect |
|-------|--------|
| 0.0 | Deterministic: always picks the most likely token (greedy) |
| ~0.5 | Focused: favors likely tokens, some variation |
| 1.0 | Neutral: samples according to learned probabilities |
| > 1.0 | Chaotic: flattens distribution, more random outputs |

## Parameter Count Formula

The total parameter count for an anvil Llama model is:

```
Params = vocab_size × n_embd          # wte
       + vocab_size × n_embd          # lm_head
       + n_layer × [
           4 × n_embd²                # attn: Wq + Wk + Wv + Wo
           + 3 × int(8n_embd/3) × n_embd  # SwiGLU: gate + up + down
           + 2 × n_embd               # rms_1 + rms_2
         ]
       + n_embd                       # rms_final
```

For default config (vocab_size=27, n_embd=16, n_layer=1, n_head=4):
```
Params = 27·16 + 27·16 + 1·[4·256 + 3·42·16 + 2·16] + 16
       = 432 + 432 + [1024 + 2016 + 32] + 16
       = 3,952  (≈4K parameters)
```

## Quick Reference Table

| Parameter | Effect on Capacity | Effect on Speed | Common Range |
|-----------|-------------------|-----------------|--------------|
| `n_embd` | **High** (quadratic params) | **High** (more compute) | 8–64 |
| `n_head` | Medium (per-head dim) | Low-Medium (head loop) | 2–8 |
| `n_layer` | **High** (linear params) | **High** (sequential) | 1–4 |
| `block_size` | Medium (context length) | Medium (quadratic attn) | 8–32 |
| `num_steps` | Low (convergence) | **High** (linear) | 200–5000 |
| `learning_rate` | Low (optimization) | None | 0.001–0.1 |
| `temperature` | None (inference only) | None | 0.0–1.5 |

## See Also

- [[TrainingDataFlow]] — How parameters enter the training loop
- [[Glossary]] — Definitions of Adam, BOS, RMSNorm
- [[ProgressiveWalkthroughs]] — Each progressive example uses different hyperparameter configurations