# Research: Llama Engine Evolution & Safetensors Export

**Phase**: 0 — Unknown Resolution  
**Date**: 2026-06-14  
**Feature**: [spec.md](./spec.md)

---

## 1. Safetensors Format Specification

- **Decision**: Use `safetensors` Python package (service layer only, not core)
- **Rationale**: Core engine is stdlib-only (Constitution Article I). Safetensors export runs in the service layer where pip deps are available.
- **Alternatives considered**: Pure Python safetensors writer (rejected — reinventing the wheel), JSON-only export (rejected — primary artifact must be safetensors per spec)

### Implementation

```python
from safetensors.numpy import save_file
import numpy as np

# Convert internal list-of-lists to numpy arrays, then write
np_tensors = {}
for name, data in tensors.items():
    arr = np.array(data, dtype=np.float32)
    if not arr.flags["C_CONTIGUOUS"]:
        arr = np.ascontiguousarray(arr)
    np_tensors[name] = arr

save_file(np_tensors, "model.safetensors", metadata={"format": "anvil"})
```

### File Format Structure
```
┌─ 8 bytes: N (uint64 LE)  ─┐  header size in bytes
├─ N bytes: JSON UTF-8       ─┤  header: {"name": {"dtype":"F32","shape":[...],"data_offsets":[b,e]}}
├─ byte-buffer               ─┤  raw tensor data (C-contiguous float32)
└──────────────────────────────┘
```

### API Functions
- `safetensors.numpy.save_file(tensor_dict, filename, metadata=None)` — write to disk
- `safetensors.numpy.save(tensor_dict, metadata=None)` — serialize to bytes
- dtype mapping: `np.float32` → `"F32"`

- **deps**: `safetensors>=0.4` in service layer

---

## 2. Rotary Position Embedding (RoPE)

- **Decision**: Replace learned `wpe` position embeddings with RoPE. Precompute cos/sin tables once, apply to Q and K vectors in forward pass.
- **Rationale**: RoPE enables relative position encoding (unbounded), is the standard for modern decoder-only architectures, and eliminates learned position parameters.
- **Alternatives considered**: ALiBi (rejected — not standard for Llama), sinusoidal (rejected — not Llama-compatible), keep learned wpe (rejected per spec)

### Formula

**Frequencies** (for head_dim, base=10000.0):
```
θ_i = 1 / (base^(2i/head_dim))   for dimension pair i = 0, 1, ..., head_dim/2 - 1
```

**Rotation** at position m, pair (x_even, x_odd):
```
x'_even = x_even * cos(m·θ_i) - x_odd * sin(m·θ_i)
x'_odd  = x_even * sin(m·θ_i) + x_odd * cos(m·θ_i)
```

### ⚠️ CRITICAL: Pairing Convention — half-split (rotate_half), NOT interleaved

HuggingFace Llama uses the **half-split / `rotate_half`** convention: dimension `i` is paired with dimension `i + head_dim/2`. The vector is split into two halves `[0 : d/2]` and `[d/2 : d]`, and those halves are rotated against each other. This is the convention the engine MUST use (FR-003).

The interleaved/consecutive convention (pairing `(v[0],v[1]), (v[2],v[3])`) is GPT-J style and is **WRONG** for HF Llama export. Training with interleaved RoPE and exporting to a standards-compatible Llama loader produces silently mismatched logits (the model loads but generates wrong output) — breaking SC-002 and SC-004. **Do not use interleaved pairing.**

### Implementation (pure Python, stdlib) — half-split convention

```python
def precompute_rope(seq_len, head_dim, theta=10000.0):
    """Returns (cos_table, sin_table) each [seq_len][head_dim//2].

    head_dim MUST be even (validated upstream per FR-017).
    """
    half = head_dim // 2
    inv_freq = [1.0 / (theta ** (2.0 * i / head_dim)) for i in range(half)]
    cos_table, sin_table = [], []
    for pos in range(seq_len):
        cos_table.append([math.cos(pos * f) for f in inv_freq])
        sin_table.append([math.sin(pos * f) for f in inv_freq])
    return cos_table, sin_table

def apply_rope(vector, pos, cos_table, sin_table):
    """Apply half-split RoPE rotation to a single Q/K vector.

    Pairs dimension i with dimension i + head_dim/2 (rotate_half / HF Llama).
    """
    d = len(vector)
    half = d // 2
    cos_row, sin_row = cos_table[pos], sin_table[pos]
    result = [0.0] * d
    for i in range(half):
        x1 = vector[i]          # first half
        x2 = vector[i + half]   # second half
        c, s = cos_row[i], sin_row[i]
        # rotate_half: [x1, x2] -> [x1*c - x2*s, x2*c + x1*s]
        result[i] = x1 * c - x2 * s
        result[i + half] = x2 * c + x1 * s
    return result
```

### Key Points
- RoPE applied to Q and K only (V is not rotated — it's used in weighted sum, not dot product)
- Applied after QKV projection, before attention score computation
- All heads share the same frequency schedule (determined by head_dim)
- **head_dim must be even** (FR-017 — validated upstream)
- **KV cache**: rotate each key at its own absolute position exactly once before caching; never double-rotate cached keys (FR-018)

---

## 3. SwiGLU Gated MLP

- **Decision**: Replace ReLU-based fc1/fc2 MLP with SwiGLU gated MLP using SiLU activation
- **Rationale**: Matches Llama architecture, provides better representational power per parameter
- **Alternatives considered**: GELU (rejected — not Llama standard), keep ReLU (rejected per spec)

### Formula

```
FFN_SwiGLU(x) = (SiLU(x · W_gate) ⊗ x · W_up) · W_down
```

### Parameter Count Parity

| MLP | Projections | Params |
|-----|------------|--------|
| ReLU | fc1: n→4n, fc2: 4n→n | 8n² |
| SwiGLU | gate: n→I, up: n→I, down: I→n | 3n·I |

With `intermediate_size = I = int(8 * n_embd / 3)`:
- 3n · (8n/3) = 8n² — **identical parameter count**

### SiLU Activation (for Value class)

```python
def silu(x):
    """SiLU (Swish): f(x) = x * sigmoid(x)"""
    s = 1 / (1 + math.exp(-x.data))
    return Value(
        x.data * s,
        (x,),
        (s * (1 + x.data * (1 - s)),),  # gradient: σ(x) + x·σ(x)·(1-σ(x))
    )
```

---

## 3b. Normalization Structure (CRITICAL)

- **Decision**: Three norm positions only — pre-attention (`rms_1`), pre-MLP (`rms_2`), and final pre-output (`rms_final`). NO embedding-level norm.
- **Rationale**: This matches the target decoder-only architecture exactly. The current GPT-2 engine applies an extra RMSNorm immediately after the token+position embedding sum — this has NO corresponding tensor in the target architecture and MUST be removed (FR-005a).
- **Alternatives considered**: Keeping the embedding-level norm (rejected — makes the graph non-equivalent to the target architecture, no HF tensor to map it to, breaks SC-002/SC-004).

### Correct forward structure (per token, Llama-equivalent)

```
x = wte[token]                                    # token embedding (NO norm here)
for each layer i:
    x = x + attention( rmsnorm(x) * rms_1[i] )    # pre-attention norm + residual, RoPE inside attention
    x = x + swiglu_mlp( rmsnorm(x) * rms_2[i] )    # pre-MLP norm + residual
x = rmsnorm(x) * rms_final                         # final norm before output
logits = linear(x, lm_head)
```

| Norm position | Internal key | HF tensor | Present in old engine? |
|---------------|-------------|-----------|------------------------|
| Embedding-level | (removed) | — | YES — MUST be removed |
| Pre-attention | `rms_1` | `model.layers.{i}.input_layernorm.weight` | yes (no learned scale) |
| Pre-MLP | `rms_2` | `model.layers.{i}.post_attention_layernorm.weight` | yes (no learned scale) |
| Final | `rms_final` | `model.norm.weight` | NO — MUST be added |

---

## 4. Llama Config JSON Schema

- **Decision**: Generate `config.json` matching HuggingFace `LlamaConfig` schema
- **Rationale**: Standards-compatible export — model loads in any HF-compatible inference tool
- **Alternatives considered**: Custom format (rejected — defeats export purpose)

### Mapping: anvil → HuggingFace

| anvil | HuggingFace | Example (n_embd=16) |
|-------|-------------|---------------------|
| `n_embd` | `hidden_size` | 16 |
| `n_head` | `num_attention_heads` | 4 |
| `n_layer` | `num_hidden_layers` | 1 |
| `block_size` | `max_position_embeddings` | 16 |
| `vocab_size` | `vocab_size` | (e.g., 27) |
| — | `intermediate_size` | `int(8 * 16 / 3) = 42` |
| — | `rms_norm_eps` | 1e-5 |
| — | `hidden_act` | `"silu"` |

### Example config.json
```json
{
  "model_type": "llama",
  "vocab_size": 27,
  "hidden_size": 16,
  "intermediate_size": 42,
  "num_hidden_layers": 1,
  "num_attention_heads": 4,
  "num_key_value_heads": 4,
  "max_position_embeddings": 16,
  "hidden_act": "silu",
  "rms_norm_eps": 1e-5,
  "bos_token_id": 1,
  "eos_token_id": 2
}
```

---

## 5. State Dict Naming — HuggingFace Convention

- **Decision**: Export with standard HF Llama tensor names
- **Rationale**: Model loads directly in transformers inference tools without name mapping

### Complete Mapping: anvil internal → HF export

| Component | anvil Internal Key | HF Export Key |
|-----------|-------------------|---------------|
| Token embeddings | `wte` | `model.embed_tokens.weight` |
| Attn Q proj | `layer{i}.attn_wq` | `model.layers.{i}.self_attn.q_proj.weight` |
| Attn K proj | `layer{i}.attn_wk` | `model.layers.{i}.self_attn.k_proj.weight` |
| Attn V proj | `layer{i}.attn_wv` | `model.layers.{i}.self_attn.v_proj.weight` |
| Attn O proj | `layer{i}.attn_wo` | `model.layers.{i}.self_attn.o_proj.weight` |
| MLP gate | `layer{i}.mlp_gate` | `model.layers.{i}.mlp.gate_proj.weight` |
| MLP up | `layer{i}.mlp_up` | `model.layers.{i}.mlp.up_proj.weight` |
| MLP down | `layer{i}.mlp_down` | `model.layers.{i}.mlp.down_proj.weight` |
| Pre-attn norm | `layer{i}.rms_1` | `model.layers.{i}.input_layernorm.weight` |
| Post-attn norm | `layer{i}.rms_2` | `model.layers.{i}.post_attention_layernorm.weight` |
| Final norm | `rms_final` | `model.norm.weight` |
| LM head | `lm_head` | `lm_head.weight` |

### Weight Tying
- `lm_head.weight` is tied to `model.embed_tokens.weight` in HF Llama
- Either omit `lm_head.weight` from export (HF ties on load) or include both
- **Decision**: Include both in safetensors for compatibility (anvil doesn't tie weights)

### Biases
- Llama uses **bias-free** linear layers (`attention_bias=False`, `mlp_bias=False`)
- Safetensors export omits bias keys entirely (no `model.layers.{i}.self_attn.q_proj.bias`)
