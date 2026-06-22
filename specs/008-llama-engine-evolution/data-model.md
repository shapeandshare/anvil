# Data Model: Llama Engine Evolution

**Feature**: 006-llama-engine-evolution  
**Phase**: 1 — Design & Contracts  
**Date**: 2026-06-14  

---

## Entity: GPT Model (Internal)

The in-memory representation of the trained model. Lives in `anvil/core/engine.py`.

### Hyperparameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vocab_size` | `int` | derived | Character vocabulary + BOS token |
| `n_embd` | `int` | 16 | Embedding dimension (hidden_size) |
| `n_head` | `int` | 4 | Number of attention heads |
| `n_layer` | `int` | 1 | Number of transformer layers |
| `block_size` | `int` | 16 | Maximum sequence length |
| `head_dim` | `int` | `n_embd // n_head` | Dimensions per attention head |
| `intermediate_size` | `int` | `int(8 * n_embd / 3)` | SwiGLU intermediate dimension |

### State Dict Keys (New Llama Architecture)

| Key | Shape | Description |
|-----|-------|-------------|
| `wte` | `[vocab_size, n_embd]` | Token embedding weights |
| `lm_head` | `[vocab_size, n_embd]` | Output projection |
| `rms_final` | `[n_embd]` | Final RMSNorm learned scale |
| `layer{i}.attn_wq` | `[n_embd, n_embd]` | Query projection |
| `layer{i}.attn_wk` | `[n_embd, n_embd]` | Key projection |
| `layer{i}.attn_wv` | `[n_embd, n_embd]` | Value projection |
| `layer{i}.attn_wo` | `[n_embd, n_embd]` | Attention output projection |
| `layer{i}.mlp_gate` | `[intermediate_size, n_embd]` | SwiGLU gate projection |
| `layer{i}.mlp_up` | `[intermediate_size, n_embd]` | SwiGLU up projection |
| `layer{i}.mlp_down` | `[n_embd, intermediate_size]` | SwiGLU down projection |
| `layer{i}.rms_1` | `[n_embd]` | Pre-attention RMSNorm scale |
| `layer{i}.rms_2` | `[n_embd]` | Pre-MLP RMSNorm scale |

### REMOVED Keys (from GPT-2)

| Key | Reason |
|-----|--------|
| `wpe` | Replaced by RoPE (no learned position embeddings) |
| `layer{i}.mlp_fc1` | Replaced by `mlp_gate` + `mlp_up` |
| `layer{i}.mlp_fc2` | Replaced by `mlp_down` |

### RoPE Cache (not in state dict)

| Field | Type | Description |
|-------|------|-------------|
| `cos_table` | `list[list[float]]` | `[block_size][head_dim//2]` — precomputed cos values |
| `sin_table` | `list[list[float]]` | `[block_size][head_dim//2]` — precomputed sin values |

Precomputed in `GPT.__init__()` using `block_size` and `head_dim`.

---

## Entity: Training Checkpoint (Safetensors — Primary Artifact)

The primary model delivery format. Generated automatically on every training completion.

### Files

| File | Purpose | Format |
|------|---------|--------|
| `model.safetensors` | Model weights | safetensors (float32, no biases) |
| `config.json` | Architecture configuration | JSON (LlamaConfig schema) |
| `tokenizer.json` | Character vocabulary | JSON (anvil custom format) |

### Storage Path

```
data/models/<experiment_id>/<run_id>/
├── model.safetensors
├── config.json
├── tokenizer.json
└── model.json  (secondary/internal)
```

### Versioning

- One immutable version per training run
- Keyed by experiment/run ID
- Re-training produces a new version (no mutation)

---

## Entity: Internal Model State (JSON — Secondary)

A secondary representation in native anvil JSON format. Used for in-platform operations (inference, introspection).

### JSON Structure

```json
{
  "vocab_size": 27,
  "n_embd": 16,
  "n_head": 4,
  "n_layer": 1,
  "block_size": 16,
  "intermediate_size": 42,
  "chars": ["a", "b", ...],
  "state_dict": {
    "wte": [[...], ...],
    "rms_final": [...],
    "layer0.attn_wq": [[...], ...],
    "layer0.attn_wk": [[...], ...],
    "layer0.attn_wv": [[...], ...],
    "layer0.attn_wo": [[...], ...],
    "layer0.mlp_gate": [[...], ...],
    "layer0.mlp_up": [[...], ...],
    "layer0.mlp_down": [[...], ...],
    "layer0.rms_1": [...],
    "layer0.rms_2": [...],
    "lm_head": [[...], ...]
  }
}
```

### Loading Old Format

- Old format contains `wpe` and `mlp_fc1`/`mlp_fc2` keys
- `GPT.load()` detects old keys and raises `ValueError` with clear message (FR-011)

---

## Entity: Transformer Layer (Logical, 1 per `n_layer`)

| Component | Description |
|-----------|-------------|
| Pre-attention RMSNorm | `layer{i}.rms_1` — learned scale, applied to residual input |
| Multi-head self-attention | Q/K/V projections + RoPE + causal attention + O projection |
| Post-attention residual | `x = x + attn_output` |
| Pre-MLP RMSNorm | `layer{i}.rms_2` — learned scale, applied to residual input |
| SwiGLU MLP | `gate_proj` (SiLU) ⊗ `up_proj` → `down_proj` |
| Post-MLP residual | `x = x + mlp_output` |
| Final RMSNorm | `rms_final` — learned scale, applied before lm_head |

---

## State Transitions

```
Training Start → Training Complete → Safetensors Export → Storage + Tracking
                                         │
                                    [failure]
                                         │
                                         ▼
                              (training still successful)
                              failure flagged in UI/logs
                              user can retry export later
```

## Validation Rules

| Rule | Description | Violation |
|------|-------------|-----------|
| head_dim even | `n_embd % (2 * n_head) == 0` (head_dim is an even integer) | RoPE pairs dimensions; odd head_dim breaks rotation — reject with clear error (FR-017) |
| Export zero-synthesis | Every safetensors tensor maps to a trained parameter | FR-009 violation |
| Old format detection | `wpe` or `mlp_fc1` in state dict keys | Must raise clear error |
| Export format | All tensors float32, written `[out_features, in_features]` row-major, C-contiguous | safetensors write failure / wrong logits on load |
| RoPE convention | half-split (rotate_half): dim `i` paired with `i + head_dim/2` | Interleaved pairing silently breaks HF-loaded logits (FR-003) |
| KV cache rotation | each key rotated once at its own position before caching | Double-rotation produces wrong attention (FR-018) |
| No embedding norm | state dict has no embedding-level norm parameter | Extra norm has no HF tensor; breaks equivalence (FR-005a) |